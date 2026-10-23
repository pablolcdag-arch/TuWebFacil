#!/usr/bin/env python3
"""
Motor de Ingesta Inteligente de Listas de Precios y Servicios
Soporta archivos tabulares (.xlsx, .csv), PDFs y texto libre.
Genera estructura normalizada JSON conforme al contrato de TuWebLista.
"""

import os
import io
import re
import json
import logging
import unicodedata
import warnings
import pandas as pd
from dotenv import load_dotenv

warnings.filterwarnings('ignore', category=FutureWarning)
load_dotenv()

def normalize_text(text):
    if not text:
        return ""
    text_str = str(text).strip()
    return unicodedata.normalize('NFKD', text_str).encode('ASCII', 'ignore').decode('utf-8').lower()

def is_code_keyword(col_name):
    """Detecta si un encabezado de columna indica un código o SKU explícito."""
    norm = normalize_text(col_name)
    tokens = re.findall(r'[a-z0-9]+', norm)
    for t in tokens:
        if t in {"codigo", "cod", "sku"} or t.startswith("cod") or t.startswith("sku"):
            return True
    return False

def is_article_keyword(col_name):
    """Detecta palabras clave de artículo/art sin colisionar con tarjeta, carta o departamento."""
    norm = normalize_text(col_name)
    tokens = re.findall(r'[a-z0-9]+', norm)
    for t in tokens:
        if t in {"articulo", "art"} or (t.startswith("art") and not t.startswith("arte")):
            return True
    return False

def is_identifier_col(col_name):
    """
    Detecta si una columna es un identificador secuencial o numérico (ej: Nº de producto, ID, Nro, etc.)
    que no debe ser seleccionado como nombre o descripción comercial.
    """
    raw_lower = str(col_name).strip().lower()
    if any(m in raw_lower for m in ["nº", "n°"]):
        return True
    norm = normalize_text(col_name)
    id_substrings = ["no de", "no.", "n de ", "id_", "id producto", "id articulo", "num de", "nro de"]
    if any(m in norm for m in id_substrings):
        return True
    tokens = re.findall(r'[a-z0-9]+', norm)
    if tokens and tokens[0] in {"id", "nro", "num", "numero"}:
        return True
    return False

def select_best_service_col(candidate_cols):
    """
    Selecciona la mejor columna para el nombre del servicio o producto.
    Descarta identificadores secuenciales/numéricos y prioriza nombres comerciales explícitos
    sobre palabras genéricas como 'producto' o 'item'.
    """
    if not candidate_cols:
        return None

    # 1. Filtrar identificadores numéricos y columnas auxiliares (moneda, stock, etc.)
    valid_cols = [c for c in candidate_cols if not is_identifier_col(c)]
    aux_keywords = ["moneda", "stock", "utilidad", "alicuota", "tasa", "iva", "margen", "controla"]
    clean_cols = [c for c in valid_cols if not any(aux in normalize_text(c) for aux in aux_keywords)]
    
    candidates_to_use = clean_cols if clean_cols else (valid_cols if valid_cols else candidate_cols)

    # 2. Prioridad 1: Denominaciones comerciales explícitas
    primary_name_keywords = ["nombre", "descripcion", "detalle", "servicio", "articulo"]
    for c in candidates_to_use:
        norm = normalize_text(c)
        if any(k in norm for k in primary_name_keywords):
            return c

    # 3. Prioridad 2: Palabras genéricas
    generic_name_keywords = ["producto", "item", "concepto", "zona", "tratamiento"]
    for c in candidates_to_use:
        norm = normalize_text(c)
        if any(k in norm for k in generic_name_keywords):
            return c

    # 4. Fallback: Primera columna disponible
    return candidates_to_use[0]

def format_price(val):
    """
    Formatea importes como string monetario normalizado argentino:
    ej: 48089.77 -> "$48.089,77", 15000 -> "$15.000", "8900,00" -> "$8.900", "7.539,81" -> "$7.539,81"
    """
    if val is None or pd.isna(val):
        return "-"
    
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["-", "nan", "none", "null"]:
        return "-"

    # Si es numérico directamente (int o float)
    if isinstance(val, (int, float)):
        cents = int(round(float(val) * 100))
        main_part = cents // 100
        dec_part = cents % 100
        formatted_main = f"{main_part:,}".replace(",", ".")
        if dec_part > 0:
            return f"${formatted_main},{dec_part:02d}"
        else:
            return f"${formatted_main}"

    # Limpiar símbolo de moneda y espacios
    cleaned = val_str.replace("$", "").replace("ARS", "").replace("USD", "").strip()

    # Si ya tiene formato argentino exacto con centavos: ej "48.089,77"
    if re.match(r'^\d{1,3}(\.\d{3})*,\d{2}$', cleaned):
        if cleaned.endswith(",00"):
            return f"${cleaned[:-3]}"
        return f"${cleaned}"

    # Si ya tiene formato argentino entero: ej "15.000"
    if re.match(r'^\d{1,3}(\.\d{3})*$', cleaned):
        return f"${cleaned}"

    # Intentar parsear numéricamente con tolerancia a comas y puntos
    try:
        if "," in cleaned and "." in cleaned:
            # Notación argentina ej: 48.089,77 o 1.234.567,89
            num = float(cleaned.replace(".", "").replace(",", "."))
        elif "," in cleaned and "." not in cleaned:
            # Notación con coma decimal ej: 48089,77 o 8900,00
            num = float(cleaned.replace(",", "."))
        else:
            num = float(cleaned)
        
        cents = int(round(num * 100))
        main_part = cents // 100
        dec_part = cents % 100
        formatted_main = f"{main_part:,}".replace(",", ".")
        if dec_part > 0:
            return f"${formatted_main},{dec_part:02d}"
        else:
            return f"${formatted_main}"
    except Exception:
        # Fallback si no es parseable directamente
        return f"${cleaned}" if not val_str.startswith("$") else val_str

def parse_tabular_data(df, default_title="Lista de Precios Oficial"):
    """
    Procesa un DataFrame de Pandas (de CSV o Excel) identificando
    columnas de servicios/productos, modalidades de pago y metadatos de catálogo
    (código, categoría, unidad, carta de colores/ficha técnica).
    """
    # 1. Limpiar filas y columnas completamente vacías
    df = df.dropna(how='all').dropna(axis=1, how='all')
    if df.empty or len(df.columns) < 2:
        raise ValueError("El archivo no contiene suficientes columnas de servicios y precios.")

    # 2. Identificar columnas de metadatos de catálogo
    category_keywords = ["categoria", "rubro", "familia", "linea", "grupo"]
    carta_keywords = ["carta", "colores", "ficha", "catalogo", "link"]
    unit_keywords = ["unidad", "medida", "presentacion", "envase", "unid"]
    payment_keywords = ["efectivo", "transferencia", "tarjeta", "precio", "contado", "valor", "debito", "cuotas", "lista", "monto", "arancel", "costo"]

    category_col = None
    for col in df.columns:
        norm = normalize_text(col)
        if any(k in norm for k in category_keywords):
            category_col = col
            break

    carta_col = None
    for col in df.columns:
        if col == category_col:
            continue
        norm = normalize_text(col)
        if any(k in norm for k in carta_keywords):
            carta_col = col
            break

    unit_col = None
    for col in df.columns:
        if col in [category_col, carta_col]:
            continue
        norm = normalize_text(col)
        tokens = re.findall(r'[a-z0-9]+', norm)
        if any(k in norm for k in unit_keywords) or "um" in tokens:
            unit_col = col
            break

    # 3. Identificar columnas de precios
    auxiliary_price_keywords = ["moneda", "stock", "utilidad", "alicuota", "tasa", "iva", "margen", "controla"]
    price_cols = []
    for col in df.columns:
        if col in [category_col, carta_col, unit_col]:
            continue
        norm = normalize_text(col)
        # Ignorar columnas auxiliares que no son precios de venta (ej: moneda costo, alícuota IVA, stock)
        if any(aux in norm for aux in auxiliary_price_keywords):
            continue
        if any(k in norm for k in payment_keywords):
            price_cols.append(col)

    # 4. Determinar service_col y code_col entre las columnas restantes
    remaining_cols = [c for c in df.columns if c not in [category_col, carta_col, unit_col] and c not in price_cols]

    if not price_cols:
        service_col = select_best_service_col(remaining_cols)
        if service_col:
            price_cols = [c for c in remaining_cols if c != service_col]
            code_col = None
        else:
            raise ValueError("No se encontraron columnas de precios ni de servicios en la tabla.")
    else:
        if len(remaining_cols) == 0:
            service_col = price_cols.pop(0)
            code_col = None
        elif len(remaining_cols) == 1:
            service_col = remaining_cols[0]
            code_col = None
        else:
            exp_code_col = None
            for c in remaining_cols:
                if is_code_keyword(c):
                    exp_code_col = c
                    break

            if exp_code_col:
                code_col = exp_code_col
                other_cols = [c for c in remaining_cols if c != exp_code_col]
                service_col = select_best_service_col(other_cols)
            else:
                art_col = None
                for c in remaining_cols:
                    if is_article_keyword(c):
                        art_col = c
                        break
                if art_col:
                    other_cols = [c for c in remaining_cols if c != art_col]
                    desc_col = select_best_service_col(other_cols)
                    if desc_col and any(k in normalize_text(desc_col) for k in ["descripcion", "detalle", "nombre", "concepto", "servicio"]):
                        code_col = art_col
                        service_col = desc_col
                    else:
                        service_col = art_col
                        code_col = None
                else:
                    # Detectar si alguna columna restante es un identificador secuencial o ID (ej: 'Nº de producto', 'ID')
                    id_col = None
                    for c in remaining_cols:
                        if is_identifier_col(c):
                            id_col = c
                            break
                    if id_col:
                        code_col = id_col
                        other_cols = [c for c in remaining_cols if c != id_col]
                        service_col = select_best_service_col(other_cols)
                    else:
                        service_col = select_best_service_col(remaining_cols)
                        code_col = None

    if not price_cols:
        raise ValueError("No se encontraron columnas de precios en la tabla.")

    # 5. Mapear nombres de columnas de pago y sus claves normalizadas
    columnas_pago = []
    col_to_key = {}
    for col in price_cols:
        clean_name = str(col).strip()
        columnas_pago.append(clean_name)
        norm_key = normalize_text(clean_name)
        
        if "efectivo" in norm_key or "contado" in norm_key:
            key = "efectivo"
        elif "transf" in norm_key:
            key = "transferencia"
        elif "tarjeta" in norm_key or "cuota" in norm_key or "credito" in norm_key:
            key = "tarjeta"
        elif "debito" in norm_key:
            key = "debito"
        elif "final" in norm_key:
            key = "precio_final"
        elif "lista" in norm_key:
            key = "lista"
        elif "precio" in norm_key or "valor" in norm_key:
            key = "precio"
        else:
            key = re.sub(r'[^a-z0-9]+', '_', norm_key).strip('_')
            if not key:
                key = f"precio_{len(col_to_key) + 1}"

        base_key = key
        counter = 2
        while key in col_to_key.values():
            key = f"{base_key}_{counter}"
            counter += 1
        col_to_key[col] = key

    # 6. Clasificación de Modo de Vista y extracción de items
    is_catalog = bool(code_col or category_col or unit_col or carta_col)
    modo_vista = "catalogo" if is_catalog else "servicios"
    items = []
    categorias_map = {}

    for _, row in df.iterrows():
        srv_val = row[service_col]
        if pd.isna(srv_val):
            continue
        srv_name = str(srv_val).strip()
        norm_srv = normalize_text(srv_name)
        
        # Omitir filas de encabezado repetidas o vacías
        if not srv_name or norm_srv in ["nan", "none", "null", "servicio", "zona", "tratamiento", "descripcion", "producto", "articulo", "item", "concepto", "nombre"]:
            continue

        row_precios = {}
        has_valid_price = False
        for col in price_cols:
            raw_p = row[col]
            fmt_p = format_price(raw_p)
            if fmt_p and fmt_p != "-":
                has_valid_price = True
            key = col_to_key[col]
            row_precios[key] = fmt_p

        if not has_valid_price:
            continue

        if is_catalog:
            cat_name = ""
            if category_col and pd.notna(row[category_col]):
                val_c = str(row[category_col]).strip()
                if normalize_text(val_c) not in ["nan", "none", "null"]:
                    cat_name = val_c

            cod_val = ""
            if code_col and pd.notna(row[code_col]):
                val_cod = str(row[code_col]).strip()
                if normalize_text(val_cod) not in ["nan", "none", "null"]:
                    cod_val = val_cod

            unit_val = ""
            if unit_col and pd.notna(row[unit_col]):
                val_u = str(row[unit_col]).strip()
                if normalize_text(val_u) not in ["nan", "none", "null"]:
                    unit_val = val_u

            carta_val = ""
            if carta_col and pd.notna(row[carta_col]):
                val_carta = str(row[carta_col]).strip()
                if normalize_text(val_carta) not in ["nan", "none", "null", "-"]:
                    carta_val = val_carta

            if cat_name:
                if cat_name not in categorias_map:
                    categorias_map[cat_name] = {
                        "nombre": cat_name,
                        "foto_url": "",
                        "carta_url": ""
                    }
                if carta_val and not categorias_map[cat_name]["carta_url"]:
                    categorias_map[cat_name]["carta_url"] = carta_val

            items.append({
                "tipo": "producto",
                "categoria": cat_name,
                "codigo": cod_val,
                "servicio": srv_name,
                "unidad": unit_val,
                "carta_url": carta_val,
                "foto_url": "",
                "color_dot": "",
                "precios": row_precios
            })
        else:
            items.append({
                "tipo": "servicio",
                "servicio": srv_name,
                "precios": row_precios
            })

    if not items:
        raise ValueError("No se encontraron filas con servicios y precios válidos en el archivo tabular.")

    categorias = list(categorias_map.values()) if is_catalog else []

    return {
        "titulo": default_title,
        "modo_vista": modo_vista,
        "columnas_pago": columnas_pago,
        "categorias": categorias,
        "items": items
    }

def extract_with_gemini(text_content, default_title="Lista de Precios Oficial"):
    """
    Fallback usando Gemini Flash (gemini-flash-lite-latest) para extraer
    estructuradamente la lista de precios desde texto libre o PDF.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurada para procesar texto libre/PDF.")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-flash-lite-latest")

        prompt = f"""Sos un extractor experto de listas de precios y servicios para comercios y profesionales de Argentina.
Analizá el siguiente contenido y extraé estructuradamente la lista de precios y servicios en formato JSON exacto:
{{
  "titulo": "{default_title}",
  "columnas_pago": ["Efectivo", "Transferencia", "Tarjeta"],
  "items": [
    {{
      "servicio": "Nombre del Servicio o Producto",
      "precios": {{
        "efectivo": "$48.089,77",
        "transferencia": "$55.303,24",
        "tarjeta": "$63.478,50"
      }}
    }}
  ]
}}

Reglas estrictas:
1. "columnas_pago" es la lista de formas de pago identificadas (ej: ["Efectivo", "Transferencia", "Tarjeta"] o ["Precio"]).
2. Para cada item en "items", "servicio" es el nombre del servicio/zona/producto.
3. "precios" es un objeto cuyas claves son las formas de pago en minúsculas y sin acentos (ej: "efectivo", "transferencia", "tarjeta", "precio"), y los valores son los importes formateados con signo $ y formato argentino (ej: "$48.089,77" o "$15.000").
4. Respondé ÚNICAMENTE con el bloque JSON válido, sin texto adicional ni markdown.

Contenido a analizar:
{text_content}"""

        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        data = json.loads(raw_text)
        if "items" not in data or not data["items"]:
            raise ValueError("No se encontraron servicios ni precios válidos en la respuesta de la IA.")

        if "columnas_pago" not in data or not data["columnas_pago"]:
            first_precios = data["items"][0].get("precios", {})
            data["columnas_pago"] = [k.capitalize() for k in first_precios.keys()]

        if "titulo" not in data or not data["titulo"]:
            data["titulo"] = default_title

        if "modo_vista" not in data or not data["modo_vista"]:
            data["modo_vista"] = "servicios"

        if "categorias" not in data:
            data["categorias"] = []

        for it in data.get("items", []):
            if "tipo" not in it:
                it["tipo"] = "servicio"

        return data
    except Exception as e:
        logging.error(f"Error extrayendo con Gemini: {e}")
        raise ValueError(f"No se pudo extraer la lista de precios con IA: {e}")

def parse_text_fallback(text, default_title="Lista de Precios Oficial"):
    """
    Parser determinista regex para texto plano cuando Gemini no está disponible o para formato CSV en texto.
    """
    # Intentar primero como CSV en memoria si tiene delimitadores
    if any(sep in text for sep in [",", ";", "\t"]) and "\n" in text:
        try:
            df = pd.read_csv(io.StringIO(text), sep=None, engine='python')
            if len(df.columns) >= 2 and len(df) >= 1:
                return parse_tabular_data(df, default_title)
        except Exception:
            pass

    # Regex para líneas: "Servicio: $10.000" o "Servicio - Efectivo: $10.000, Tarjeta: $12.000"
    items = []
    lines = text.strip().split("\n")
    detected_cols = set()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Caso A: Servicio: $10.000
        m_simple = re.match(r'^([^:\-]+)[:\-]\s*\$?([0-9.,]+)$', line)
        if m_simple:
            srv = m_simple.group(1).strip()
            prc = format_price(m_simple.group(2))
            detected_cols.add("Precio")
            items.append({
                "tipo": "servicio",
                "servicio": srv,
                "precios": {"precio": prc}
            })
            continue

        # Caso B: Servicio con múltiples precios (ej: Abdomen: Efectivo $48.089,77 | Transferencia $55.303,24 | Tarjeta $63.478,50)
        if ":" in line or "-" in line:
            parts = re.split(r'[:\-]', line, maxsplit=1)
            srv = parts[0].strip()
            rest = parts[1].strip()

            price_matches = re.findall(r'([a-zA-ZáéíóúÁÉÍÓÚ]+)\s*[:\$]?\s*\$?([0-9.,]+)', rest)
            if price_matches:
                precios = {}
                for p_col, p_val in price_matches:
                    clean_col = p_col.capitalize()
                    detected_cols.add(clean_col)
                    key = normalize_text(clean_col)
                    if "efectivo" in key: key = "efectivo"
                    elif "transf" in key: key = "transferencia"
                    elif "tarjeta" in key: key = "tarjeta"
                    precios[key] = format_price(p_val)
                items.append({
                    "tipo": "servicio",
                    "servicio": srv,
                    "precios": precios
                })

    if items:
        cols = sorted(list(detected_cols)) if detected_cols else ["Precio"]
        return {
            "titulo": default_title,
            "modo_vista": "servicios",
            "columnas_pago": cols,
            "categorias": [],
            "items": items
        }

    raise ValueError("No se pudieron detectar servicios ni precios en el texto ingresado.")

def parse_price_list(input_data, filename=None, is_text=False):
    """
    Punto de entrada principal para la ingesta de listas de precios.
    - input_data: ruta a archivo, string con texto, o bytes
    - filename: nombre opcional del archivo original (ej: "precios.xlsx", "soteria.pdf")
    - is_text: boolean indicando si input_data es texto directo
    """
    default_title = "Lista de Precios Oficial"
    if filename:
        base_name = os.path.splitext(os.path.basename(filename))[0]
        clean_base = base_name.replace("_", " ").replace("-", " ").title()
        if len(clean_base) >= 3:
            default_title = f"Lista de Precios - {clean_base}"

    # 1. Si es texto explícito o string que no es archivo existente
    if is_text or (isinstance(input_data, str) and not os.path.isfile(input_data)):
        text_content = str(input_data).strip()
        if not text_content:
            raise ValueError("El texto proporcionado está vacío.")
        
        # Intentar con IA primero si la API key está disponible
        if os.getenv("GEMINI_API_KEY"):
            try:
                return extract_with_gemini(text_content, default_title)
            except Exception as e:
                logging.warning(f"Fallback a parser regex por fallo en Gemini: {e}")
        
        return parse_text_fallback(text_content, default_title)

    # 2. Si es archivo en disco o bytes
    filepath = None
    temp_created = False
    
    if isinstance(input_data, str) and os.path.isfile(input_data):
        filepath = input_data
        if not filename:
            filename = os.path.basename(filepath)
    elif isinstance(input_data, bytes):
        import tempfile
        ext = os.path.splitext(filename)[1] if filename else ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
            tf.write(input_data)
            filepath = tf.name
            temp_created = True

    if not filepath or not os.path.exists(filepath):
        raise ValueError("No se pudo acceder al archivo de entrada.")

    ext = (os.path.splitext(filename)[1] if filename else os.path.splitext(filepath)[1]).lower()

    try:
        # A. Archivos CSV
        if ext in [".csv", ".tsv", ".txt"]:
            # Probar encodings habituales
            df = None
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try:
                    df = pd.read_csv(filepath, sep=None, engine='python', encoding=enc)
                    if len(df.columns) >= 2:
                        break
                except Exception:
                    continue
            if df is not None and not df.empty:
                return parse_tabular_data(df, default_title)

        # B. Archivos Excel (.xlsx, .xls)
        elif ext in [".xlsx", ".xls"]:
            try:
                df = pd.read_excel(filepath)
                return parse_tabular_data(df, default_title)
            except Exception as e:
                logging.warning(f"Error leyendo Excel con Pandas: {e}")

        # C. Archivos PDF (.pdf)
        elif ext == ".pdf":
            extracted_text = ""
            try:
                from pypdf import PdfReader
                reader = PdfReader(filepath)
                for page in reader.pages:
                    extracted_text += (page.extract_text() or "") + "\n"
            except Exception as pe:
                logging.warning(f"Error extrayendo texto del PDF con pypdf: {pe}")

            if extracted_text.strip():
                if os.getenv("GEMINI_API_KEY"):
                    try:
                        return extract_with_gemini(extracted_text, default_title)
                    except Exception as ge:
                        logging.warning(f"Fallo Gemini con texto de PDF: {ge}")
                return parse_text_fallback(extracted_text, default_title)

        # Si es un archivo de texto plano adicional (.txt, .csv, .tsv sin procesar)
        if ext in [".txt", ".tsv", ".csv"] and os.getenv("GEMINI_API_KEY"):
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_content = f.read(50000)
                if raw_content.strip():
                    return extract_with_gemini(raw_content, default_title)
            except Exception:
                pass

        raise ValueError(f"No se pudo procesar el formato '{ext}' o no contiene datos legibles.")

    finally:
        if temp_created and filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
