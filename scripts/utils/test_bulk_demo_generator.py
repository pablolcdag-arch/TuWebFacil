#!/usr/bin/env python3
"""
scripts/utils/test_bulk_demo_generator.py
Suite de pruebas automatizadas para la generación masiva de demos outbound:
1. Enriquecimiento de generar_plantilla_dinamica() con lista_precios interactiva.
2. Fallback determinista en caso de indisponibilidad de IA.
3. Renderizado del banner superior aclaratorio en templates/client_template.html.
4. Normalización telefónica y mapeo tolerante de columnas CSV.
5. Ejecución End-to-End de generate_demos_from_csv.py con archivo CSV sintético.
"""

import os
import sys
import re
import csv
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import jinja2
import app
from app import generar_plantilla_dinamica, format_price, format_phone, DEMO_SITES
from scripts.ops.generate_demos_from_csv import (
    normalizar_telefono,
    detectar_columnas,
    generar_slug_unico,
    procesar_csv
)

def banner(title):
    print(f"\n{'='*70}\n🧪 TEST GENERADOR DE DEMOS: {title}\n{'='*70}")

def test_generar_plantilla_dinamica_con_lista_precios():
    banner("1. Enriquecimiento de generar_plantilla_dinamica con lista_precios")
    
    # Mockear respuesta de Gemini AI para asegurar determinismo
    ai_mock_response = {
        "servicios_sugeridos": ["Corte Clásico", "Barba Completa", "Corte + Barba VIP"],
        "descripciones_servicios": [
            "Corte tradicional a tijera o máquina.",
            "Perfilado y toalla caliente para barba.",
            "Servicio integral con lavado y peinado."
        ],
        "foto_hero_query": "modern barbershop haircut",
        "fotos_queries": ["barber haircut", "beard grooming", "barbershop chair"],
        "paleta_colores": {"primario": "#1e293b", "secundario": "#0f172a"},
        "lista_precios": {
            "titulo": "Nuestros Cortes y Servicios",
            "columnas_pago": ["Efectivo", "Transferencia", "Tarjeta"],
            "items": [
                {
                    "servicio": "Corte Clásico",
                    "precios": {"efectivo": "$8.000", "transferencia": "$9.000", "tarjeta": "$10.000"},
                    "descuento": 15
                },
                {
                    "servicio": "Barba Completa",
                    "precios": {"efectivo": "$6.000", "transferencia": "$6.800", "tarjeta": "$7.500"},
                    "descuento": 0
                },
                {
                    "servicio": "Corte + Barba VIP",
                    "precios": {"efectivo": "$12.000", "transferencia": "$13.500", "tarjeta": "$15.000"},
                    "descuento": 0
                }
            ]
        }
    }

    mock_model = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(ai_mock_response)
    mock_model.generate_content.return_value = mock_resp

    with patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch.object(app, "GEMINI_API_KEY", "test_gemini_key"):
        res = generar_plantilla_dinamica("Barbería", "Barbería La Barber", "Palermo", "10 a 20 hs")

    assert "lista_precios" in res, "Falta clave 'lista_precios' en el resultado"
    lp = res["lista_precios"]
    assert lp.get("titulo") == "Nuestros Cortes y Servicios", f"Título inesperado: {lp.get('titulo')}"
    assert lp.get("columnas_pago") == ["Efectivo", "Transferencia", "Tarjeta"], f"Columnas inesperadas: {lp.get('columnas_pago')}"
    
    items = lp.get("items", [])
    assert len(items) == 3, f"Se esperaban 3 items, se obtuvieron: {len(items)}"
    for it in items:
        assert "servicio" in it and len(it["servicio"]) > 0
        assert "precios" in it and isinstance(it["precios"], dict)
        assert "efectivo" in it["precios"] and it["precios"]["efectivo"].startswith("$")
        assert "transferencia" in it["precios"] and it["precios"]["transferencia"].startswith("$")
        assert "tarjeta" in it["precios"] and it["precios"]["tarjeta"].startswith("$")
        assert "descuento" in it and isinstance(it["descuento"], int)

    print("✅ TEST 1 PASADO: generar_plantilla_dinamica() genera lista_precios válida y estructurada con 3 columnas.")

def test_fallback_determinista_sin_ia():
    banner("2. Fallback determinista de lista_precios ante ausencia/falla de IA")
    
    with patch.object(app, "GEMINI_API_KEY", None):
        res = generar_plantilla_dinamica("Pinturería", "Pinturas del Sur", "Avellaneda", "8 a 18 hs")

    assert "lista_precios" in res, "El fallback debe incluir 'lista_precios'"
    lp = res["lista_precios"]
    assert lp.get("titulo") == "Precios y Servicios"
    assert lp.get("columnas_pago") == ["Efectivo", "Transferencia", "Tarjeta"]
    items = lp.get("items", [])
    assert len(items) == 3, f"Se esperaban 3 items en el fallback, se obtuvieron: {len(items)}"
    
    assert items[0]["descuento"] == 15, "El primer item debe tener 15% OFF inicial como gancho comercial"
    assert items[0]["precios"]["efectivo"] == "$12.000"
    assert items[0]["precios"]["transferencia"] == "$13.500"
    assert items[0]["precios"]["tarjeta"] == "$15.000"
    assert "Pintureria" in items[0]["servicio"] or "Pinturería" in items[0]["servicio"]

    print("✅ TEST 2 PASADO: Fallback determinista provee 3 items adaptados al rubro con precios argentinos coherentes.")

def test_banner_aclaratorio_demo_en_template():
    banner("3. Renderizado y comportamiento del Banner Superior Aclaratorio en client_template.html")
    
    loader = jinja2.FileSystemLoader(os.path.join(BASE_DIR, "templates"))
    env = jinja2.Environment(loader=loader, autoescape=True)
    env.filters["format_phone"] = format_phone
    tmpl = env.get_template("client_template.html")

    base_content = {
        "titulo_web": "Heladería Artesanal Vivaldi",
        "subtitulo": "Helados de pura fruta y crema",
        "paleta_colores": {"primario": "#0284c7", "secundario": "#0369a1"},
        "servicios_sugeridos": ["1 Kg Helado", "Cucurucho Gigante", "Postre Almendrado"],
        "descripciones_servicios": ["Sabores a elección.", "Con baño de chocolate.", "Para compartir en familia."],
        "fotos_servicios": [
            "https://images.unsplash.com/photo-test1",
            "https://images.unsplash.com/photo-test2",
            "https://images.unsplash.com/photo-test3"
        ],
        "foto_hero": "https://images.unsplash.com/photo-hero",
        "horario": "Todos los días 12:00 a 00:00",
        "ubicacion_detectada": "San Telmo, CABA",
        "whatsapp_contacto": "5491134710787",
        "email_contacto": "",
        "instagram": "vivaldihelados",
        "mapa": {"lat": -34.61, "lon": -58.37, "zoom": 15},
        "lista_precios": {
            "titulo": "Precios de Helados",
            "columnas_pago": ["Efectivo", "Transferencia", "Tarjeta"],
            "items": [
                {"servicio": "1 Kg Helado", "precios": {"efectivo": "$14.000", "transferencia": "$15.500", "tarjeta": "$17.000"}, "descuento": 10}
            ]
        }
    }

    # Caso A: Modo Demo con cliente con nombre específico
    ctx_demo_con_nombre = {
        "web_content": base_content,
        "client": {"name": "Franco Vivaldi", "phone": "5491134710787"},
        "web_status": "demo",
        "is_preview": False,
        "bot_phone": "5491134710787"
    }
    html_demo_1 = tmpl.render(**ctx_demo_con_nombre)
    assert "Demo Interactiva" in html_demo_1, "Debe contener la etiqueta 'Demo Interactiva'"
    assert "Muestra preparada para <strong>Franco Vivaldi</strong>" in html_demo_1, "Debe nombrar al titular del comercio"
    assert "mismo abono mensual de $2.000" in html_demo_1, "Debe contener la propuesta de valor de $2.000/mes"
    assert "sticky top-0 z-[160]" in html_demo_1, "El banner debe tener z-[160] sticky top-0"
    assert "border-b border-indigo-700/50" in html_demo_1

    # Caso B: Modo Demo sin nombre de cliente (fallback a titulo_web)
    ctx_demo_sin_nombre = {
        "web_content": base_content,
        "client": {"phone": "5491134710787"},
        "web_status": "demo",
        "is_preview": False,
        "bot_phone": "5491134710787"
    }
    html_demo_2 = tmpl.render(**ctx_demo_sin_nombre)
    assert "Muestra preparada para <strong>Heladería Artesanal Vivaldi</strong>" in html_demo_2

    # Caso C: Web Publicada (status == 'published') -> El banner NO debe mostrarse
    ctx_publicada = {
        "web_content": base_content,
        "client": {"name": "Franco Vivaldi", "phone": "5491134710787"},
        "web_status": "published",
        "is_preview": False,
        "bot_phone": "5491134710787"
    }
    html_pub = tmpl.render(**ctx_publicada)
    assert "Demo Interactiva" not in html_pub, "El banner demo NO debe figurar en webs publicadas"
    assert "Muestra preparada para" not in html_pub
    assert "z-[160]" not in html_pub

    print("✅ TEST 3 PASADO: Banner superior aclaratorio se renderiza en 'demo' con z-[160] y no se muestra en 'published'.")

def test_normalizacion_telefonica_y_columnas():
    banner("4. Normalización de números telefónicos y detección tolerante de columnas")
    
    # 4.1 Teléfonos argentinos
    assert normalizar_telefono("+54 9 11 3471-0787") == "5491134710787"
    assert normalizar_telefono("011 3471-0787") == "5491134710787"
    assert normalizar_telefono("11 3471 0787") == "5491134710787"
    assert normalizar_telefono("15 3471-0787") == "5491134710787"
    assert normalizar_telefono("541134710787") == "5491134710787"
    assert normalizar_telefono("5491134710787") == "5491134710787"
    assert normalizar_telefono("") == ""
    assert normalizar_telefono(None) == ""

    # 4.2 Mapeo tolerante de columnas
    header_scraper = ["Nombre del Local", "Teléfono", "Dirección"]
    mapa_1 = detectar_columnas(header_scraper)
    assert mapa_1["nombre"] == "Nombre del Local"
    assert mapa_1["telefono"] == "Teléfono"
    assert mapa_1["direccion"] == "Dirección"
    assert mapa_1["rubro"] is None

    header_crm = ["business_name", "category", "phone", "location"]
    mapa_2 = detectar_columnas(header_crm)
    assert mapa_2["nombre"] == "business_name"
    assert mapa_2["rubro"] == "category"
    assert mapa_2["telefono"] == "phone"
    assert mapa_2["direccion"] == "location"

    print("✅ TEST 4 PASADO: Formatos de teléfonos argentinos y mapeo de encabezados CSV normalizados correctamente.")

def test_ejecucion_end_to_end_script_csv():
    banner("5. Ejecución End-to-End de generate_demos_from_csv.py con CSV sintético")
    
    # Crear archivo CSV sintético temporal
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', suffix='.csv', delete=False) as f_in:
        input_csv_path = f_in.name
        writer = csv.writer(f_in)
        writer.writerow(["Nombre del Local", "Teléfono", "Dirección"])
        writer.writerow(["Panadería San Pedro", "+54 11 3471-0787", "Av. Santa Fe 1234, CABA"])
        writer.writerow(["Ferretería El Tornillo", "011 4455-6677", "Rivadavia 5678, Haedo"])
        writer.writerow(["Estudio Jurídico Silva", "15 9988-7766", "Lavalle 432, CABA"])

    output_csv_path = input_csv_path.replace(".csv", "_out.csv")

    # Mock de cliente Supabase para pruebas aisladas
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "client_mock_1"}]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{"id": "web_mock_1"}]

    try:
        resultado = procesar_csv(
            input_path=input_csv_path,
            output_path=output_csv_path,
            limit=None,
            skip_sleep=True,
            supabase_client=mock_sb
        )

        assert resultado["total_procesados"] == 3, f"Se esperaban 3 procesados, se obtuvieron: {resultado['total_procesados']}"
        assert os.path.exists(output_csv_path), "No se generó el archivo de salida CSV"

        # Leer archivo de salida con utf-8-sig
        with open(output_csv_path, mode='r', encoding='utf-8-sig') as f_out:
            reader = csv.DictReader(f_out)
            filas_out = list(reader)

        assert len(filas_out) == 3, f"El CSV de salida debe tener 3 filas, tiene: {len(filas_out)}"
        
        # Verificar Panadería San Pedro
        fila_1 = filas_out[0]
        assert fila_1["Nombre del Local"] == "Panadería San Pedro"
        assert fila_1["slug"] == "panaderia-san-pedro"
        assert fila_1["link_demo"] == "https://panaderia-san-pedro.tuweblista.com.ar"
        assert "panaderia-san-pedro" in DEMO_SITES
        demo_1_data = DEMO_SITES["panaderia-san-pedro"]
        assert "lista_precios" in demo_1_data["web_content"]

        # Verificar Ferretería El Tornillo
        fila_2 = filas_out[1]
        assert fila_2["Nombre del Local"] == "Ferretería El Tornillo"
        assert fila_2["slug"] == "ferreteria-el-tornillo"
        assert fila_2["link_demo"] == "https://ferreteria-el-tornillo.tuweblista.com.ar"

        # Verificar Estudio Jurídico Silva
        fila_3 = filas_out[2]
        assert fila_3["Nombre del Local"] == "Estudio Jurídico Silva"
        assert fila_3["slug"] == "estudio-juridico-silva"
        assert fila_3["link_demo"] == "https://estudio-juridico-silva.tuweblista.com.ar"

        print("✅ TEST 5 PASADO: Script procesó lote CSV, agregó columnas 'slug' y 'link_demo' y guardó con utf-8-sig.")

    finally:
        # Limpieza de archivos temporales
        if os.path.exists(input_csv_path):
            os.remove(input_csv_path)
        if os.path.exists(output_csv_path):
            os.remove(output_csv_path)

def main():
    print("\n" + "="*70)
    print("🚀 INICIANDO TEST SUITE: GENERADOR MASIVO DE DEMOS (OUTBOUND)")
    print("="*70)

    test_generar_plantilla_dinamica_con_lista_precios()
    test_fallback_determinista_sin_ia()
    test_banner_aclaratorio_demo_en_template()
    test_normalizacion_telefonica_y_columnas()
    test_ejecucion_end_to_end_script_csv()

    print("\n" + "="*70)
    print("🎉 TODOS LOS TESTS DE GENERACIÓN MASIVA DE DEMOS PASARON (100% OK)")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

