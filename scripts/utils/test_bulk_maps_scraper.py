#!/usr/bin/env python3
"""
scripts/utils/test_bulk_maps_scraper.py
Suite de pruebas automatizadas para el motor de barrido masivo de Google Maps (Bulk Maps Scraper):
1. Verificación integral del catálogo geográfico argentino (arg_geo_catalog.py).
2. Verificación de ejecución con stop loss (límite de comercios) y cálculo de costos en USD.
3. Deduplicación inteligente de prospectos por teléfono en zonas limítrofes.
4. Verificación de los endpoints de control /admin/bulk_scraper/* en Flask test_client.
"""

import os
import sys
import io
import csv
import json
import tempfile
import threading
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app
from scripts.utils import arg_geo_catalog
from scripts.ops import bulk_maps_scraper
from scripts.ops.bulk_maps_scraper import (
    BulkMapsScraper,
    normalizar_telefono,
    COST_PER_TEXT_SEARCH,
    COST_PER_PLACE_DETAILS
)

def banner(title):
    print(f"\n{'='*70}\n🧪 TEST BULK MAPS SCRAPER: {title}\n{'='*70}")

def test_arg_geo_catalog_structure():
    banner("1. Verificación del Catálogo Geográfico Argentino")

    # 1. CABA
    assert len(arg_geo_catalog.CABA) == 48, f"CABA debe tener 48 barrios oficiales, tiene: {len(arg_geo_catalog.CABA)}"
    assert "Palermo, CABA" in arg_geo_catalog.CABA
    assert "Recoleta, CABA" in arg_geo_catalog.CABA
    assert "Villa Urquiza, CABA" in arg_geo_catalog.CABA

    # 2. GBA
    assert len(arg_geo_catalog.GBA) == 35, f"GBA debe tener 35 zonas/partidos, tiene: {len(arg_geo_catalog.GBA)}"
    assert "Vicente López, Buenos Aires" in arg_geo_catalog.GBA
    assert "La Matanza, Buenos Aires" in arg_geo_catalog.GBA

    # 3. Provincias clave
    assert len(arg_geo_catalog.SANTA_FE) == 20
    assert "Centro, Rosario, Santa Fe" in arg_geo_catalog.SANTA_FE
    assert len(arg_geo_catalog.CORDOBA) == 20
    assert "Nueva Córdoba, Córdoba" in arg_geo_catalog.CORDOBA
    assert len(arg_geo_catalog.MENDOZA) == 14
    assert len(arg_geo_catalog.TUCUMAN) == 8
    assert len(arg_geo_catalog.BUENOS_AIRES_INTERIOR) == 25
    assert "Centro, Mar del Plata, Buenos Aires" in arg_geo_catalog.BUENOS_AIRES_INTERIOR

    # 4. Macro-zona Argentina
    assert len(arg_geo_catalog.ARGENTINA) == 248, f"Argentina debe tener 248 zonas, tiene: {len(arg_geo_catalog.ARGENTINA)}"
    assert len(arg_geo_catalog.ARGENTINA) == len(set(arg_geo_catalog.ARGENTINA)), "Argentina no debe contener duplicados"

    # 5. Helper obtener_zonas_por_clave y aliases
    assert len(arg_geo_catalog.obtener_zonas_por_clave("caba")) == 48
    assert len(arg_geo_catalog.obtener_zonas_por_clave("CABA")) == 48
    assert len(arg_geo_catalog.obtener_zonas_por_clave("capital")) == 48
    assert len(arg_geo_catalog.obtener_zonas_por_clave("rosario")) == 20
    assert len(arg_geo_catalog.obtener_zonas_por_clave("cordoba")) == 20
    assert len(arg_geo_catalog.obtener_zonas_por_clave("toda_argentina")) == 248, "toda_argentina debe resolver a las 248 zonas de ARGENTINA"
    assert len(arg_geo_catalog.obtener_zonas_por_clave("nacional")) == 248
    assert len(arg_geo_catalog.obtener_zonas_por_clave("argentina_completa")) == 248
    assert len(arg_geo_catalog.obtener_zonas_por_clave("bsas_interior")) == len(arg_geo_catalog.BUENOS_AIRES_INTERIOR)
    assert len(arg_geo_catalog.obtener_zonas_por_clave("interior_bsas")) == len(arg_geo_catalog.BUENOS_AIRES_INTERIOR)

    # Ubicación personalizada
    custom_zone = arg_geo_catalog.obtener_zonas_por_clave("Las Cañitas, CABA")
    assert custom_zone == ["Las Cañitas, CABA"]

    # 6. Presets
    presets = arg_geo_catalog.obtener_presets()
    assert len(presets) >= 8
    preset_ids = [p["id"] for p in presets]
    assert "argentina" in preset_ids
    assert "caba" in preset_ids
    assert "gba" in preset_ids
    assert "cordoba" in preset_ids
    assert "santa_fe" in preset_ids

    print("✅ TEST 1 PASADO: Catálogo de Argentina estructurado con 48 barrios de CABA, GBA y macro-zona federal.")

def test_bulk_scraper_stop_loss_and_costs():
    banner("2. Ejecución con límite de comercios (stop loss) y cálculo de costo")

    # Mock de Google Places API
    def mock_get(url, *args, **kwargs):
        mock_r = MagicMock()
        mock_r.status_code = 200
        if "textsearch/json" in url:
            mock_r.json.return_value = {
                "status": "OK",
                "results": [
                    {"place_id": f"p_{i}"} for i in range(1, 10)  # 9 resultados disponibles
                ]
            }
        elif "details/json" in url:
            # Extraer id
            pid = "1"
            for i in range(1, 10):
                if f"place_id=p_{i}" in url:
                    pid = str(i)
                    break
            mock_r.json.return_value = {
                "status": "OK",
                "result": {
                    "name": f"Peluquería Estilo {pid}",
                    "formatted_phone_number": f"011 4400-000{pid}",
                    "formatted_address": f"Av. Corrientes {pid}00, CABA",
                    "website": ""
                }
            }
        else:
            mock_r.json.return_value = {}
        return mock_r

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f_tmp:
        tmp_csv = f_tmp.name

    try:
        scraper = BulkMapsScraper(
            rubro="Peluquería",
            zona_clave="caba",
            max_comercios=3,  # Freno estricto a 3 comercios
            solo_sin_web=True,
            output_file=tmp_csv,
            api_key="fake_places_key"
        )

        with patch("requests.get", side_effect=mock_get):
            status = scraper.run()

        assert status["status"] == "completed"
        assert status["comercios_encontrados"] == 3, f"Debió frenar exactamente en 3, obtuvo: {status['comercios_encontrados']}"
        assert status["leads_count"] == 3
        assert status["total_leads"] == 3
        assert status["leads"] == 3
        assert status["progress_percent"] == 100
        assert "download_url" in status and status["download_url"].startswith("/admin/bulk_scraper/download/")
        assert status["estimated_cost"] == status["consumo_usd"]
        assert "estimated_cost_str" in status
        assert scraper.comercios_encontrados == 3

        # Costos: 1 text search ($0.032) + 3 place details ($0.017 * 3 = $0.051) = $0.083
        expected_min_cost = COST_PER_TEXT_SEARCH + (3 * COST_PER_PLACE_DETAILS)
        assert scraper.consumo_usd >= expected_min_cost - 0.0001, f"Costo calculado erróneo: {scraper.consumo_usd}"

        # Verificar CSV generado
        with open(tmp_csv, mode="r", encoding="utf-8") as f_read:
            rows = list(csv.reader(f_read))

        headers = rows[0]
        assert headers == ['Nombre del Local', 'Teléfono', 'Dirección', 'Sitio Web Detectado', 'Zona']
        data_rows = rows[1:]
        assert len(data_rows) == 3

    finally:
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)
        state_file = scraper.state_file
        if os.path.exists(state_file):
            os.remove(state_file)

    print("✅ TEST 2 PASADO: Freno de seguridad en 3 comercios y acumulación precisa de costos en USD.")

def test_bulk_scraper_deduplication():
    banner("3. Deduplicación inteligente de prospectos en zonas limítrofes")

    call_count = {"p1": 0, "p2": 0}

    def mock_get(url, *args, **kwargs):
        mock_r = MagicMock()
        mock_r.status_code = 200
        if "textsearch/json" in url:
            if "Palermo" in url:
                mock_r.json.return_value = {
                    "status": "OK",
                    "results": [{"place_id": "place_palermo"}]
                }
            elif "Colegiales" in url:
                mock_r.json.return_value = {
                    "status": "OK",
                    "results": [{"place_id": "place_colegiales"}]
                }
            else:
                mock_r.json.return_value = {"status": "ZERO_RESULTS"}
        elif "details/json" in url:
            if "place_palermo" in url:
                call_count["p1"] += 1
                mock_r.json.return_value = {
                    "status": "OK",
                    "result": {
                        "name": "Barbería Flow Palermo",
                        "formatted_phone_number": "+54 11 9988-7766",  # Mismo teléfono
                        "formatted_address": "Av. Santa Fe 4000, Palermo",
                        "website": ""
                    }
                }
            elif "place_colegiales" in url:
                call_count["p2"] += 1
                mock_r.json.return_value = {
                    "status": "OK",
                    "result": {
                        "name": "Barbería Flow Sucursal",
                        "formatted_phone_number": "011 9988-7766",  # Mismo teléfono formateado local
                        "formatted_address": "Federico Lacroze 2000, Colegiales",
                        "website": ""
                    }
                }
        else:
            mock_r.json.return_value = {}
        return mock_r

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f_tmp:
        tmp_csv = f_tmp.name

    try:
        scraper = BulkMapsScraper(
            rubro="Barbería",
            zona_clave="caba",
            max_comercios=10,
            solo_sin_web=True,
            output_file=tmp_csv,
            api_key="fake_places_key"
        )

        with patch("scripts.ops.bulk_maps_scraper.obtener_zonas_por_clave", return_value=["Palermo, CABA", "Colegiales, CABA"]), \
             patch("requests.get", side_effect=mock_get):
            status = scraper.run()

        # Debe contener solo 1 prospecto porque el segundo tenía el mismo teléfono normalizado 5491199887766
        assert status["comercios_encontrados"] == 1
        assert "5491199887766" in scraper.seen_phones

        with open(tmp_csv, mode="r", encoding="utf-8") as f_read:
            rows = list(csv.reader(f_read))[1:]
            assert len(rows) == 1, f"Se esperaba 1 comercio deduplicado, se obtuvieron: {len(rows)}"
            assert rows[0][0] == "Barbería Flow Palermo"

    finally:
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)
        if os.path.exists(scraper.state_file):
            os.remove(scraper.state_file)

    print("✅ TEST 3 PASADO: Prospecto duplicado entre Palermo y Colegiales detectado y omitido.")

def test_flask_admin_bulk_scraper_endpoints():
    banner("4. Verificación de endpoints /admin/bulk_scraper/* en Flask test_client")

    client = app.app.test_client()

    # 4.1 Protección de sesión (no autorizado -> 403)
    r_unauth = client.get("/admin/bulk_scraper/presets")
    assert r_unauth.status_code == 403, f"Esperado 403 no autorizado, recibido: {r_unauth.status_code}"

    # Iniciar sesión de admin
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    # 4.2 GET /admin/bulk_scraper/presets
    r_presets = client.get("/admin/bulk_scraper/presets")
    assert r_presets.status_code == 200
    p_data = r_presets.get_json()
    assert "presets" in p_data
    assert len(p_data["presets"]) >= 8

    # 4.3 GET /admin/bulk_scraper/status (estado inicial)
    r_status = client.get("/admin/bulk_scraper/status")
    assert r_status.status_code == 200

    # 4.4 POST /admin/bulk_scraper/start (validación de campos)
    r_start_err = client.post("/admin/bulk_scraper/start", json={})
    assert r_start_err.status_code == 400

    # Mockear start_scraper_task para verificar start exitoso y 409 already_running
    with patch("app.start_scraper_task") as mock_start:
        mock_start.return_value = {
            "status": "started",
            "task_id": "test_task_123",
            "rubro": "depilación",
            "zona_clave": "caba",
            "max_comercios": 50,
            "csv_filename": "prospectos_depilacion_caba.csv"
        }
        r_start = client.post("/admin/bulk_scraper/start", json={
            "rubro": "depilación",
            "zona": "caba",
            "max_comercios": 50,
            "solo_sin_web": True
        })
        assert r_start.status_code == 200
        start_data = r_start.get_json()
        assert start_data["status"] == "started"
        assert start_data["task_id"] == "test_task_123"

        # Simular intento cuando ya está corriendo
        mock_start.return_value = {
            "status": "already_running",
            "error": "Ya hay un barrido en ejecución actualmente.",
            "task_id": "test_task_123"
        }
        r_start_conflict = client.post("/admin/bulk_scraper/start", json={"rubro": "test"})
        assert r_start_conflict.status_code == 409

    # 4.5 POST /admin/bulk_scraper/stop
    with patch("app.stop_scraper_task") as mock_stop:
        mock_stop.return_value = {
            "status": "stopping",
            "task_id": "test_task_123",
            "message": "Detención solicitada"
        }
        r_stop = client.post("/admin/bulk_scraper/stop")
        assert r_stop.status_code == 200
        assert r_stop.get_json()["status"] == "stopping"

    # 4.6 GET /admin/bulk_scraper/download/<filename>
    leads_dir = os.path.join(BASE_DIR, "leads")
    test_csv_name = "test_download_file.csv"
    test_csv_path = os.path.join(leads_dir, test_csv_name)

    try:
        with open(test_csv_path, "w", encoding="utf-8") as f_dl:
            f_dl.write("Nombre del Local,Teléfono,Dirección,Sitio Web Detectado,Zona\n")
            f_dl.write("Test Spa,5491111223344,Av. Belgrano 100,Sin web,Balvanera\n")

        # Descarga permitida
        r_dl = client.get(f"/admin/bulk_scraper/download/{test_csv_name}")
        assert r_dl.status_code == 200
        assert "text/csv" in r_dl.content_type
        assert "Test Spa" in r_dl.data.decode("utf-8")

        # Intento de path traversal o archivo no .csv -> 400 o 404
        r_invalid = client.get("/admin/bulk_scraper/download/invalido.txt")
        assert r_invalid.status_code == 400

        r_notfound = client.get("/admin/bulk_scraper/download/inexistente_123.csv")
        assert r_notfound.status_code == 404

    finally:
        if os.path.exists(test_csv_path):
            os.remove(test_csv_path)

    print("✅ TEST 4 PASADO: Endpoints de presets, start, status, stop y download certificados con sesión de admin.")

def main():
    print("\n" + "="*70)
    print("🚀 INICIANDO TEST SUITE: BARRIDO MASIVO DE GOOGLE MAPS (BULK SCRAPER)")
    print("="*70)

    test_arg_geo_catalog_structure()
    test_bulk_scraper_stop_loss_and_costs()
    test_bulk_scraper_deduplication()
    test_flask_admin_bulk_scraper_endpoints()

    print("\n" + "="*70)
    print("🎉 TODOS LOS TESTS DE BARRIDO MASIVO PASARON EXITOSAMENTE (100% OK)")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
