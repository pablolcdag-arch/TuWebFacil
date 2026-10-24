#!/usr/bin/env python3
"""
Test Suite: Rutas de Catálogo y Archivos Estáticos en Subdominios (Backend)
Verifica:
1. Entrega de archivos estáticos (/static/<path:filename>) en subdominios (*.tuweblista.com.ar).
2. Ruteo de /catalogo y /tienda en subdominios con is_catalog_route=True en el contexto de plantilla.
3. Ruteo de / y /precios en subdominios con is_catalog_route=False.
4. Fallback resiliente a DEMO_SITES ante demoras o indisponibilidad de Supabase.
"""

import os
import sys
from contextlib import contextmanager
from unittest.mock import patch, MagicMock
from flask import template_rendered

# Ajustar PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app import app, DEMO_SITES


@contextmanager
def captured_templates(app_instance):
    recorded = []
    def record(sender, template, context, **extra):
        recorded.append((template, context))
    template_rendered.connect(record, app_instance)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app_instance)


def run_tests():
    print("=" * 70)
    print("🚀 INICIANDO TEST SUITE: RUTAS DE CATÁLOGO Y ARCHIVOS ESTÁTICOS")
    print("=" * 70)

    # Configurar mock demo site en memoria para disgraf-demo
    mock_demo_content = {
        "titulo_web": "Disgraf Demo",
        "subtitulo": "Insumos gráficos y cartelería",
        "paleta_colores": {"primario": "#1e3a8a", "secundario": "#f59e0b"},
        "servicios_sugeridos": ["Vinilos de Corte", "Lonas Frontlight"],
        "descripciones_servicios": ["Oracal 651 calandrado", "Lona 440g brillante"],
        "fotos_queries": ["vinyl", "banner"],
        "fotos_servicios": ["", ""],
        "foto_hero": "",
        "lista_precios": {
            "titulo": "Catálogo General Disgraf",
            "modo_vista": "catalogo",
            "columnas_pago": ["Precio"],
            "categorias": [],
            "items": [{"tipo": "producto", "servicio": "Vinilo Oracal", "precios": {"precio": "$5.000"}}]
        }
    }

    DEMO_SITES["disgraf-demo"] = {
        "web_content": mock_demo_content,
        "client": {"phone": "5491100001111"},
        "status": "demo",
        "plan_type": "gratis"
    }

    subdomain_host = "disgraf-demo.tuweblista.com.ar"

    # Mock de Supabase para pruebas unitarias deterministas y veloces
    mock_supabase = MagicMock()
    mock_table_web = MagicMock()
    mock_table_cont = MagicMock()
    mock_table_cli = MagicMock()

    mock_table_web.select.return_value.eq.return_value.execute.return_value.data = [{
        "id": "web-disgraf-123",
        "subdomain": "disgraf-demo",
        "client_id": "cli-123",
        "status": "published"
    }]
    mock_table_cont.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{
        "content": mock_demo_content,
        "version": 2
    }]
    mock_table_cli.select.return_value.eq.return_value.execute.return_value.data = [{
        "phone": "5491100001111"
    }]

    def mock_table(table_name):
        if table_name == "websites":
            return mock_table_web
        elif table_name == "website_content":
            return mock_table_cont
        elif table_name == "clients":
            return mock_table_cli
        return MagicMock()

    mock_supabase.table.side_effect = mock_table

    with app.test_client() as client:
        # -------------------------------------------------------------
        # TEST 1: Archivo estático desde subdominio
        # -------------------------------------------------------------
        print("\n[TEST 1] Verificando entrega de archivo estático en subdominio...")
        res_static = client.get("/static/img/demo1.png", headers={"Host": subdomain_host})
        assert res_static.status_code == 200, f"Fallo estático: esperado 200, obtenido {res_static.status_code}"
        assert len(res_static.data) > 0, "El archivo estático devuelto está vacío"
        print(f"  ✅ GET /static/img/demo1.png en {subdomain_host} -> status 200 ({len(res_static.data)} bytes)")

        # -------------------------------------------------------------
        # TEST 2: Ruta /catalogo con is_catalog_route=True (Vía Supabase)
        # -------------------------------------------------------------
        print("\n[TEST 2] Verificando ruta /catalogo y flag is_catalog_route=True...")
        with patch("app.supabase", mock_supabase):
            with captured_templates(app) as templates:
                res_cat = client.get("/catalogo", headers={"Host": subdomain_host})
                assert res_cat.status_code == 200, f"Fallo /catalogo: esperado 200, obtenido {res_cat.status_code}"
                assert len(templates) > 0, "No se capturó ninguna plantilla renderizada"
                template, context = templates[0]
                assert context.get("is_catalog_route") is True, f"Fallo is_catalog_route: {context.get('is_catalog_route')}"
                print("  ✅ GET /catalogo -> status 200, is_catalog_route=True en contexto.")

        # -------------------------------------------------------------
        # TEST 3: Ruta /tienda con is_catalog_route=True (Vía Supabase)
        # -------------------------------------------------------------
        print("\n[TEST 3] Verificando ruta /tienda y flag is_catalog_route=True...")
        with patch("app.supabase", mock_supabase):
            with captured_templates(app) as templates:
                res_tienda = client.get("/tienda", headers={"Host": subdomain_host})
                assert res_tienda.status_code == 200, f"Fallo /tienda: esperado 200, obtenido {res_tienda.status_code}"
                template, context = templates[0]
                assert context.get("is_catalog_route") is True, f"Fallo is_catalog_route: {context.get('is_catalog_route')}"
                print("  ✅ GET /tienda -> status 200, is_catalog_route=True en contexto.")

        # -------------------------------------------------------------
        # TEST 4: Rutas / y /precios con is_catalog_route=False
        # -------------------------------------------------------------
        print("\n[TEST 4] Verificando rutas / y /precios con is_catalog_route=False...")
        with patch("app.supabase", mock_supabase):
            with captured_templates(app) as templates:
                res_root = client.get("/", headers={"Host": subdomain_host})
                assert res_root.status_code == 200, f"Fallo /: esperado 200, obtenido {res_root.status_code}"
                template, context = templates[0]
                assert context.get("is_catalog_route") is False, f"Fallo is_catalog_route en /: {context.get('is_catalog_route')}"
                print("  ✅ GET / -> status 200, is_catalog_route=False en contexto.")

            with captured_templates(app) as templates:
                res_precios = client.get("/precios", headers={"Host": subdomain_host})
                assert res_precios.status_code == 200, f"Fallo /precios: esperado 200, obtenido {res_precios.status_code}"
                template, context = templates[0]
                assert context.get("is_catalog_route") is False, f"Fallo is_catalog_route en /precios: {context.get('is_catalog_route')}"
                print("  ✅ GET /precios -> status 200, is_catalog_route=False en contexto.")

        # -------------------------------------------------------------
        # TEST 5: Fallback resiliente a DEMO_SITES ante falla de BD
        # -------------------------------------------------------------
        print("\n[TEST 5] Verificando fallback DEMO_SITES con /catalogo...")
        with patch("app.supabase", None):
            with captured_templates(app) as templates:
                res_mock = client.get("/catalogo", headers={"Host": subdomain_host})
                assert res_mock.status_code == 200, f"Fallo fallback: esperado 200, obtenido {res_mock.status_code}"
                template, context = templates[0]
                assert context.get("is_catalog_route") is True, f"Fallo is_catalog_route en fallback: {context.get('is_catalog_route')}"
                print("  ✅ Fallback DEMO_SITES -> status 200, is_catalog_route=True verificado.")

    print("\n" + "=" * 70)
    print("🎉 TODAS LAS PRUEBAS DE RUTAS Y ESTÁTICOS PASARON CON ÉXITO (100% PASS)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

