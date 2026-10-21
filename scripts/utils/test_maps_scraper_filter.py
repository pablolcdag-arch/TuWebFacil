#!/usr/bin/env python3
"""
scripts/utils/test_maps_scraper_filter.py
Suite de pruebas automatizadas para el Filtro Inteligente de Sitios Web en Google Maps Scraper:
1. Descarte de comercios con sitio web propio cuando solo_sin_web=True.
2. Conservación de comercios con redes sociales (Instagram, Facebook, etc.) con etiqueta 'Redes (...)'.
3. Conservación de comercios sin ningún sitio web con etiqueta 'Sin web'.
4. Inclusión de comercios con web propia cuando solo_sin_web=False.
5. Verificación de encabezados y codificación UTF-8 en el archivo CSV generado.
"""

import os
import sys
import io
import csv
import json
from unittest.mock import MagicMock, patch
from werkzeug.datastructures import MultiDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import app

def banner(title):
    print(f"\n{'='*70}\n🧪 TEST MAPS SCRAPER FILTER: {title}\n{'='*70}")

def build_mock_places_responses():
    """Genera respuestas simuladas de Google Places API."""
    textsearch_resp = {
        "status": "OK",
        "results": [
            {"place_id": "pid_sin_web", "name": "Panadería San Cayetano"},
            {"place_id": "pid_con_web_propia", "name": "Clínica Dental Sonrisas"},
            {"place_id": "pid_con_instagram", "name": "Barbería Flow"},
            {"place_id": "pid_con_facebook", "name": "Ferretería El Tornillo"}
        ]
    }

    details_map = {
        "pid_sin_web": {
            "status": "OK",
            "result": {
                "name": "Panadería San Cayetano",
                "formatted_phone_number": "+54 11 3471-0787",
                "formatted_address": "Av. Santa Fe 1234, Palermo, CABA",
                "website": ""
            }
        },
        "pid_con_web_propia": {
            "status": "OK",
            "result": {
                "name": "Clínica Dental Sonrisas",
                "formatted_phone_number": "011 4455-6677",
                "formatted_address": "Av. Callao 567, Recoleta, CABA",
                "website": "https://clinicadental.com.ar"
            }
        },
        "pid_con_instagram": {
            "status": "OK",
            "result": {
                "name": "Barbería Flow",
                "formatted_phone_number": "15 9988-7766",
                "formatted_address": "Rivadavia 4321, Caballito, CABA",
                "website": "https://www.instagram.com/barberiaflow"
            }
        },
        "pid_con_facebook": {
            "status": "OK",
            "result": {
                "name": "Ferretería El Tornillo",
                "formatted_phone_number": "+54 11 5566-7788",
                "formatted_address": "Corrientes 890, Almagro, CABA",
                "website": "https://facebook.com/ferreteriaeltornillo"
            }
        }
    }

    def mock_requests_get(url, *args, **kwargs):
        mock_r = MagicMock()
        mock_r.status_code = 200
        if "textsearch/json" in url:
            mock_r.json.return_value = textsearch_resp
        elif "details/json" in url:
            for pid, d_resp in details_map.items():
                if f"place_id={pid}" in url:
                    mock_r.json.return_value = d_resp
                    return mock_r
            mock_r.json.return_value = {"status": "ZERO_RESULTS"}
        else:
            mock_r.json.return_value = {}
        return mock_r

    return mock_requests_get

def test_maps_scraper_with_solo_sin_web_true():
    banner("1. Filtrado activo (solo_sin_web=True): descarta web propia, conserva 'Sin web' y redes")

    client = app.app.test_client()
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    mock_get = build_mock_places_responses()

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_maps_key"}), \
         patch("requests.get", side_effect=mock_get):

        response = client.post("/admin/maps_scraper", data={
            "query": "comercios palermo",
            "solo_sin_web": "true"
        })

        assert response.status_code == 200, f"Error HTTP esperado 200, recibido: {response.status_code}"
        assert response.mimetype == "text/csv", f"Mimetype inesperado: {response.mimetype}"

        csv_content = response.data.decode('utf-8')
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        # 1. Verificar encabezados
        headers = rows[0]
        assert headers == ['Nombre del Local', 'Teléfono', 'Dirección', 'Sitio Web Detectado'], f"Encabezados incorrectos: {headers}"

        # 2. Verificar filas
        data_rows = rows[1:]
        assert len(data_rows) == 3, f"Se esperaban 3 prospectos (1 descartado con web propia), obtenidos: {len(data_rows)}"

        nombres = [r[0] for r in data_rows]
        assert "Clínica Dental Sonrisas" not in nombres, "El comercio con web propia (clinicadental.com.ar) debió ser descartado"
        assert "Panadería San Cayetano" in nombres
        assert "Barbería Flow" in nombres
        assert "Ferretería El Tornillo" in nombres

        # 3. Verificar etiquetas de sitio web detectado
        sitios = {r[0]: r[3] for r in data_rows}
        assert sitios["Panadería San Cayetano"] == "Sin web"
        assert sitios["Barbería Flow"] == "Redes (https://www.instagram.com/barberiaflow)"
        assert sitios["Ferretería El Tornillo"] == "Redes (https://facebook.com/ferreteriaeltornillo)"

    print("✅ TEST 1 PASADO: solo_sin_web=True descarta webs propias y conserva comercios sin web y con redes sociales.")

def test_maps_scraper_with_solo_sin_web_false():
    banner("2. Filtrado desactivado (solo_sin_web=False): incluye todos los comercios con teléfono")

    client = app.app.test_client()
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    mock_get = build_mock_places_responses()

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_maps_key"}), \
         patch("requests.get", side_effect=mock_get):

        response = client.post("/admin/maps_scraper", data={
            "query": "comercios palermo",
            "solo_sin_web": "false"
        })

        assert response.status_code == 200
        csv_content = response.data.decode('utf-8')
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        data_rows = rows[1:]
        assert len(data_rows) == 4, f"Se esperaban los 4 comercios, obtenidos: {len(data_rows)}"

        sitios = {r[0]: r[3] for r in data_rows}
        assert "Clínica Dental Sonrisas" in sitios
        assert sitios["Clínica Dental Sonrisas"] == "https://clinicadental.com.ar"
        assert sitios["Panadería San Cayetano"] == "Sin web"

    print("✅ TEST 2 PASADO: solo_sin_web=False incluye comercios con web propia sin descartar.")

def test_csv_encoding_and_headers():
    banner("3. Validación de estructura de columnas y compatibilidad UTF-8")

    client = app.app.test_client()
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    mock_get = build_mock_places_responses()

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_maps_key"}), \
         patch("requests.get", side_effect=mock_get):

        response = client.post("/admin/maps_scraper", data={
            "query": "panaderías",
            "solo_sin_web": "true"
        })

        # Decodificación limpia sin errores
        raw_bytes = response.data
        decoded_text = raw_bytes.decode('utf-8')
        assert "Nombre del Local,Teléfono,Dirección,Sitio Web Detectado" in decoded_text
        assert "Panadería San Cayetano" in decoded_text

    print("✅ TEST 3 PASADO: Codificación UTF-8 y nombres de columnas certificados.")

def test_maps_scraper_html_form_multiple_values():
    banner("4. Simulación de formulario HTML con lista múltiple de valores ('solo_sin_web')")

    client = app.app.test_client()
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True

    mock_get = build_mock_places_responses()

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "fake_maps_key"}), \
         patch("requests.get", side_effect=mock_get):

        # 1. Simular checkbox marcado: el navegador envía el hidden ('false') y el checkbox ('true')
        response_checked = client.post("/admin/maps_scraper", data=MultiDict([
            ("query", "test comercios"),
            ("solo_sin_web", "false"),
            ("solo_sin_web", "true")
        ]))
        assert response_checked.status_code == 200
        csv_checked = response_checked.data.decode('utf-8')
        rows_checked = list(csv.reader(io.StringIO(csv_checked)))[1:]
        nombres_checked = [r[0] for r in rows_checked]
        assert "Clínica Dental Sonrisas" not in nombres_checked, "Con checkbox marcado debe descartar webs propias"
        assert len(rows_checked) == 3

        # 2. Simular checkbox desmarcado: el navegador solo envía el hidden ('false')
        response_unchecked = client.post("/admin/maps_scraper", data=MultiDict([
            ("query", "test comercios"),
            ("solo_sin_web", "false")
        ]))
        assert response_unchecked.status_code == 200
        csv_unchecked = response_unchecked.data.decode('utf-8')
        rows_unchecked = list(csv.reader(io.StringIO(csv_unchecked)))[1:]
        nombres_unchecked = [r[0] for r in rows_unchecked]
        assert "Clínica Dental Sonrisas" in nombres_unchecked, "Con checkbox desmarcado debe incluir webs propias"
        assert len(rows_unchecked) == 4

    print("✅ TEST 4 PASADO: Formulario HTML con tupla de valores resuelve correctamente a True o False.")

def main():
    print("\n" + "="*70)
    print("🚀 INICIANDO TEST SUITE: FILTRO INTELIGENTE DE SITIOS WEB EN MAPS SCRAPER")
    print("="*70)

    test_maps_scraper_with_solo_sin_web_true()
    test_maps_scraper_with_solo_sin_web_false()
    test_csv_encoding_and_headers()
    test_maps_scraper_html_form_multiple_values()

    print("\n" + "="*70)
    print("🎉 TODOS LOS TESTS DE MAPS SCRAPER FILTER PASARON (100% OK)")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
