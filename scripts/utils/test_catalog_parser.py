#!/usr/bin/env python3
"""
Test Suite: Motor de Ingesta Inteligente de Catálogos de Productos Físicos y Servicios
Verifica:
1. Retrocompatibilidad estricta con listas de servicios tradicionales (2 columnas).
2. Resolución de ambigüedades de nombres de columnas ('Articulo' vs 'Codigo', etc.).
3. Ingesta de catálogos comerciales estilo Disgraf (6 columnas).
4. Extracción de categorías y herencia de cartas de colores / fichas técnicas.
5. Tolerancia y normalización de importes argentinos en format_price().
6. Ingesta de archivos físicos temporales (.csv y .xlsx).
7. Texto plano y fallbacks deterministas.
8. Prevención de colisiones por substrings ('tarjeta', 'carta', 'departamento').
"""

import os
import sys
import tempfile
import pandas as pd

# Ajustar PYTHONPATH al directorio raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.utils.price_list_parser import (
    format_price,
    parse_tabular_data,
    parse_price_list,
    parse_text_fallback,
    is_code_keyword,
    is_article_keyword
)


def run_catalog_tests():
    print("=" * 75)
    print("🚀 INICIANDO TEST SUITE: MOTOR DE INGESTA DE CATÁLOGOS & SERVICIOS")
    print("=" * 75)

    # ------------------------------------------------------------------
    # TEST 1: Tolerancia de Formateo de Precios Argentinos (format_price)
    # ------------------------------------------------------------------
    print("\n[TEST 1] Verificando formateador de moneda argentina format_price()...")
    test_cases = [
        (48089.77, "$48.089,77"),
        (15000, "$15.000"),
        ("15000", "$15.000"),
        ("48089.77", "$48.089,77"),
        ("48.089,77", "$48.089,77"),
        ("$55.303,24", "$55.303,24"),
        ("8900,00", "$8.900"),
        ("7.539,81", "$7.539,81"),
        ("8900.50", "$8.900,50"),
        ("8900", "$8.900"),
        ("1.234.567,89", "$1.234.567,89"),
        (0, "$0"),
        (None, "-"),
        ("-", "-"),
        ("", "-")
    ]
    for val, expected in test_cases:
        res = format_price(val)
        assert res == expected, f"Fallo format_price({val!r}): esperado '{expected}', obtenido '{res}'"
    print("  ✅ format_price() normaliza enteros, flotantes, strings argentinos con coma/punto y ceros.")

    # ------------------------------------------------------------------
    # TEST 2: Prevención de Falsos Positivos de Substrings en Encabezados
    # ------------------------------------------------------------------
    print("\n[TEST 2] Verificando detección de palabras clave y blindaje contra falsos positivos...")
    assert not is_article_keyword("Tarjeta"), "Colisión: 'Tarjeta' no debe considerarse artículo"
    assert not is_article_keyword("Tarjeta de Crédito"), "Colisión: 'Tarjeta de Crédito' no debe considerarse artículo"
    assert not is_article_keyword("Carta"), "Colisión: 'Carta' no debe considerarse artículo"
    assert not is_article_keyword("Departamento"), "Colisión: 'Departamento' no debe considerarse artículo"
    assert not is_code_keyword("Tarjeta"), "Colisión: 'Tarjeta' no debe considerarse código"
    assert not is_code_keyword("Carta de Colores"), "Colisión: 'Carta de Colores' no debe considerarse código"

    assert is_code_keyword("Codigo"), "Fallo: 'Codigo' debe detectarse como código"
    assert is_code_keyword("Cód."), "Fallo: 'Cód.' debe detectarse como código"
    assert is_code_keyword("Cod_Articulo"), "Fallo: 'Cod_Articulo' debe detectarse como código"
    assert is_code_keyword("SKU"), "Fallo: 'SKU' debe detectarse como código"

    assert is_article_keyword("Articulo"), "Fallo: 'Articulo' debe detectarse como artículo"
    assert is_article_keyword("Art."), "Fallo: 'Art.' debe detectarse como artículo"
    print("  ✅ Palabras clave de código y artículo blindadas contra colisiones de subcadena.")

    # ------------------------------------------------------------------
    # TEST 3: Retrocompatibilidad Tradicional (2 Columnas: Servicio, Precio)
    # ------------------------------------------------------------------
    print("\n[TEST 3] Verificando retrocompatibilidad tradicional (Servicio, Precio)...")
    df_srv = pd.DataFrame({
        "Servicio": ["Corte Clásico", "Afeitado Tradicional", "Perfilado de Barba"],
        "Precio": [15000, 9500, 8000]
    })
    res_srv = parse_tabular_data(df_srv, "Barbería Don Pedro")

    assert res_srv["titulo"] == "Barbería Don Pedro"
    assert res_srv["modo_vista"] == "servicios", f"Esperado 'servicios', obtenido '{res_srv['modo_vista']}'"
    assert res_srv["columnas_pago"] == ["Precio"]
    assert res_srv["categorias"] == []
    assert len(res_srv["items"]) == 3
    assert res_srv["items"][0]["servicio"] == "Corte Clásico"
    assert res_srv["items"][0]["precios"]["precio"] == "$15.000"
    assert res_srv["items"][0]["tipo"] == "servicio"
    assert "codigo" not in res_srv["items"][0], "La lista de servicios no debe exigir 'codigo'"
    assert "unidad" not in res_srv["items"][0], "La lista de servicios no debe exigir 'unidad'"
    print("  ✅ Modo tradicional de servicios verificado con retrocompatibilidad al 100%.")

    # ------------------------------------------------------------------
    # TEST 4: Resolución de Tabla de 2 Columnas con 'Articulo' (Ferretería Básica)
    # ------------------------------------------------------------------
    print("\n[TEST 4] Verificando resolución de 'Articulo' en tabla de 2 columnas...")
    df_art_2col = pd.DataFrame({
        "Articulo": ["Tornillo Autoperforante 1/2", "Tuerca Hexagonal 3/8", "Arandela Plana"],
        "Precio": ["120,50", "85,00", "45"]
    })
    res_art_2col = parse_tabular_data(df_art_2col, "Ferretería El Tornillo")

    assert res_art_2col["modo_vista"] == "servicios", "Con solo 2 columnas 'Articulo' debe asignarse como servicio/concepto"
    assert res_art_2col["items"][0]["servicio"] == "Tornillo Autoperforante 1/2"
    assert res_art_2col["items"][0]["precios"]["precio"] == "$120,50"
    assert res_art_2col["items"][1]["precios"]["precio"] == "$85"
    assert res_art_2col["items"][2]["precios"]["precio"] == "$45"
    print("  ✅ Tabla de 2 columnas 'Articulo, Precio' resuelta como servicio sin exigir códigos.")

    # ------------------------------------------------------------------
    # TEST 5: Tabla de 3 Columnas: Codigo, Articulo, Precio
    # ------------------------------------------------------------------
    print("\n[TEST 5] Verificando resolución de 3 columnas ('Codigo', 'Articulo', 'Precio')...")
    df_3col = pd.DataFrame({
        "Codigo": ["TOR-001", "TUE-002", "ARA-003"],
        "Articulo": ["Tornillo Autoperforante", "Tuerca Hexagonal", "Arandela"],
        "Precio": [120, 85, 45]
    })
    res_3col = parse_tabular_data(df_3col, "Catálogo Rápido")

    assert res_3col["modo_vista"] == "catalogo", "Con columna 'Codigo' debe clasificarse como 'catalogo'"
    assert res_3col["items"][0]["codigo"] == "TOR-001"
    assert res_3col["items"][0]["servicio"] == "Tornillo Autoperforante"
    assert res_3col["items"][0]["tipo"] == "producto"
    print("  ✅ Precedencia 'Codigo' -> code_col y 'Articulo' -> service_col verificada.")

    # ------------------------------------------------------------------
    # TEST 6: Ingesta de Catálogo Comercial Estilo Disgraf (6 Columnas)
    # ------------------------------------------------------------------
    print("\n[TEST 6] Verificando catálogo completo de 6 columnas estilo Disgraf...")
    data_disgraf = {
        "Rubro": ["Vinilos de Corte", "Vinilos de Corte", "Lonas", "Placas Rígidas"],
        "Codigo": ["VC-OR-01", "VC-OR-02", "LN-FR-01", "PR-PA-01"],
        "Descripcion": ["Oracal 651 Brillante", "Oracal 651 Mate", "Lona Front 440g", "PAI Blanco 1mm"],
        "Unidad": ["Metro lineal", "Metro lineal", "M2", "Placa 1x1m"],
        "Precio Efectivo": [6500.0, 6800.0, 4900.5, 12500.0],
        "Precio Lista": [7800.0, 8160.0, 5880.0, 15000.0]
    }
    df_disgraf = pd.DataFrame(data_disgraf)
    res_disgraf = parse_tabular_data(df_disgraf, "Disgraf Insumos Gráficos")

    assert res_disgraf["titulo"] == "Disgraf Insumos Gráficos"
    assert res_disgraf["modo_vista"] == "catalogo"
    assert res_disgraf["columnas_pago"] == ["Precio Efectivo", "Precio Lista"]

    # Verificar categorías únicas
    categorias = res_disgraf["categorias"]
    assert len(categorias) == 3, f"Esperadas 3 categorías únicas, obtenidas {len(categorias)}"
    cat_nombres = [c["nombre"] for c in categorias]
    assert cat_nombres == ["Vinilos de Corte", "Lonas", "Placas Rígidas"]

    # Verificar items
    items = res_disgraf["items"]
    assert len(items) == 4
    primer_item = items[0]
    assert primer_item["tipo"] == "producto"
    assert primer_item["categoria"] == "Vinilos de Corte"
    assert primer_item["codigo"] == "VC-OR-01"
    assert primer_item["servicio"] == "Oracal 651 Brillante"
    assert primer_item["unidad"] == "Metro lineal"
    assert primer_item["precios"]["efectivo"] == "$6.500"
    assert primer_item["precios"]["lista"] == "$7.800"
    print("  ✅ Catálogo de 6 columnas estilo Disgraf parseado con categorías, unidades y múltiples pagos.")

    # ------------------------------------------------------------------
    # TEST 7: Catálogo con Carta de Colores / Ficha Técnica
    # ------------------------------------------------------------------
    print("\n[TEST 7] Verificando Carta de Colores y herencia a nivel de Categoría...")
    df_carta = pd.DataFrame({
        "Rubro": ["Vinilos", "Vinilos", "Telas"],
        "Codigo": ["V-01", "V-02", "T-01"],
        "Articulo": ["Vinilo Calandrado", "Vinilo Fundido", "Lienzo Canvas"],
        "Carta de Colores": ["https://tuweblista.com.ar/cartas/oracal651.pdf", "", ""],
        "Precio": [5000, 9500, 14000]
    })
    res_carta = parse_tabular_data(df_carta, "Distribuidora Gráfica")

    assert res_carta["modo_vista"] == "catalogo"
    # El primer item tiene la carta
    assert res_carta["items"][0]["carta_url"] == "https://tuweblista.com.ar/cartas/oracal651.pdf"
    assert res_carta["items"][1]["carta_url"] == ""

    # La categoría 'Vinilos' debe heredar la carta de colores de la primera fila
    cat_vinilos = next(c for c in res_carta["categorias"] if c["nombre"] == "Vinilos")
    assert cat_vinilos["carta_url"] == "https://tuweblista.com.ar/cartas/oracal651.pdf", "La categoría debe heredar la carta de colores"

    cat_telas = next(c for c in res_carta["categorias"] if c["nombre"] == "Telas")
    assert cat_telas["carta_url"] == ""
    print("  ✅ Carta de Colores asignada al producto y propagada a la categoría correspondiente.")

    # ------------------------------------------------------------------
    # TEST 8: Ingesta End-to-End con Archivos Físicos (.csv y .xlsx)
    # ------------------------------------------------------------------
    print("\n[TEST 8] Verificando parse_price_list() con archivos físicos reales (.csv y .xlsx)...")
    
    # Archivo CSV
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", encoding="utf-8", delete=False) as tf_csv:
        df_disgraf.to_csv(tf_csv.name, index=False)
        csv_path = tf_csv.name

    try:
        res_csv_file = parse_price_list(csv_path, filename="Catalogo_Disgraf_2026.csv")
        assert res_csv_file["modo_vista"] == "catalogo"
        assert len(res_csv_file["items"]) == 4
        assert res_csv_file["items"][0]["codigo"] == "VC-OR-01"
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

    # Archivo Excel (.xlsx)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf_xlsx:
        xlsx_path = tf_xlsx.name
    df_disgraf.to_excel(xlsx_path, index=False)

    try:
        res_xlsx_file = parse_price_list(xlsx_path, filename="Catalogo_Disgraf_2026.xlsx")
        assert res_xlsx_file["modo_vista"] == "catalogo"
        assert len(res_xlsx_file["items"]) == 4
        assert res_xlsx_file["items"][2]["servicio"] == "Lona Front 440g"
        assert res_xlsx_file["items"][2]["precios"]["efectivo"] == "$4.900,50"
    finally:
        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)

    print("  ✅ Ingesta de archivos temporales CSV y Excel físicos procesada con éxito.")

    # ------------------------------------------------------------------
    # TEST 9: Ingesta de Texto Plano (parse_text_fallback)
    # ------------------------------------------------------------------
    print("\n[TEST 9] Verificando parse_text_fallback y estructura uniforme...")
    raw_text = """Corte dama: $18.000
Coloración: $35.000
Nutrición capilar: $22.000"""

    res_txt = parse_text_fallback(raw_text, "Peluquería Estilo")
    assert res_txt["modo_vista"] == "servicios"
    assert res_txt["categorias"] == []
    assert len(res_txt["items"]) == 3
    assert res_txt["items"][0]["tipo"] == "servicio"
    assert res_txt["items"][0]["servicio"] == "Corte dama"
    assert res_txt["items"][0]["precios"]["precio"] == "$18.000"
    print("  ✅ Fallback determinista de texto garantiza 'modo_vista': 'servicios' y 'categorias': [].")

    print("\n" + "=" * 75)
    print("🎉 TODAS LAS PRUEBAS DE CATÁLOGOS Y SERVICIOS PASARON AL 100% (100% PASS)")
    print("=" * 75)


if __name__ == "__main__":
    run_catalog_tests()
