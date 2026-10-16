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

def format_price(val):
    """
    Formatea importes como string monetario normalizado argentino:
    ej: 48089.77 -> "$48.089,77" o 15000 -> "$15.000"
    """
    if val is None or pd.isna(val):
        return "-"
    
    val_str = str(val).strip()
    if not val_str or val_str in ["-", "nan", "none", "null"]:
        return "-"

    # Si es numérico directamente (int o float)
    if isinstance(val, (int, float)):
        if isinstance(val, float) and not val.is_integer():
            main_part = int(val)
            dec_part = int(round((val - main_part) * 100))
            formatted_main = f"{main_part:,}".replace(",", ".")
            return f"${formatted_main},{dec_part:02d}"
        else:
            formatted_main = f"{int(val):,}".replace(",", ".")
            return f"${formatted_main}"

    # Limpiar símbolo de moneda y espacios
    cleaned = val_str.replace("$", "").replace("ARS", "").replace("USD", "").strip()

    # Si ya tiene formato argentino exacto: ej "$48.089,77" o "48.089,77"
    if re.match(r'^\d{1,3}(\.\d{3})*,\d{2}$', cleaned):
        return f"${cleaned}"
    # Si ya tiene formato argentino entero: ej "15.000"
    if re.match(r'^\d{1,3}(\.\d{3})*$', cleaned):
        return f"${cleaned}"

    # Intentar parsear numéricamente
    try:
        if "," in cleaned and "." in cleaned:
            # Notación argentina ej: 48.089,77
            num = float(cleaned.replace(".", "").replace(",", "."))
        elif "," in cleaned and "." not in cleaned:
            # Notación con coma decimal ej: 48089,77
            num = float(cleaned.replace(",", "."))
        else:
            num = float(cleaned)
        return format_price(num)
    except Exception:
        # Fallback si no es parseable directamente
        return f"${cleaned}" if not val_str.startswith("$") else val_str

def parse_tabular_data(df, default_title="Lista de Precios Oficial"):
    """
    Procesa un DataFrame de Pandas (de CSV o Excel) identificando
    columnas de servicios y modalidades de pago.
    """
    # 1. Limpiar filas y columnas completamente vacías
    df = df.dropna(how='all').dropna(axis=1, how='all')
    if df.empty or len(df.columns) < 2:
        raise ValueError("El archivo no contiene suficientes columnas de servicios y precios.")

    # 2. Identificar columna de nombre de servicio
    name_keywords = ["servicio", "zona", "tratamiento", "descripcion", "producto", "detalle", "item", "concepto", "nombre"]
    service_col = None

    for col in df.columns:
        norm_col = normalize_text(col)
        if any(k in norm_col for k in name_keywords):
            service_col = col
            break

    if not service_col:
        # Seleccionar la primera columna
        service_col = df.columns[0]

    # 3. Identificar columnas de precios / modalidades de pago
    payment_keywords = ["efectivo", "transferencia", "tarjeta", "precio", "contado", "valor", "debito", "cuotas", "lista", "monto", "arancel", "costo"]
    price_cols = []
    
    for col in df.columns:
        if col == service_col:
            continue
        norm_col = normalize_text(col)
        if any(k in norm_col for k in payment_keywords):
            price_cols.append(col)

    # Si ninguna columna matcheó palabras clave, tomar las columnas restantes
    if not price_cols:
        price_cols = [c for c in df.columns if c != service_col]

    if not price_cols:
        raise ValueError("No se encontraron columnas de precios en la tabla.")

    # 4. Mapear nombres de columnas de pago y sus claves normalizadas
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
        elif "precio" in norm_key or "lista" in norm_key or "valor" in norm_key:
            key = "precio"
        else:
            key = re.sub(r'[^a-z0-9]+', '_', norm_key).strip('_')
            if not key:
                key = f"precio_{len(col_to_key) + 1}"
        col_to_key[col] = key

    # 5. Iterar filas y armar items
    items = []
    for _, row in df.iterrows():
        srv_val = row[service_col]
        if pd.isna(srv_val):
            continue
        srv_name = str(srv_val).strip()
        norm_srv = normalize_text(srv_name)
        
        # Omitir filas de encabezado repetidas o vacías
        if not srv_name or norm_srv in ["nan", "none", "null", "servicio", "zona", "tratamiento", "descripcion", "producto"]:
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

        if has_valid_price:
            items.append({
                "servicio": srv_name,
                "precios": row_precios
            })

    if not items:
        raise ValueError("No se encontraron filas con servicios y precios válidos en el archivo tabular.")

    return {
        "titulo": default_title,
        "columnas_pago": columnas_pago,
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
                    "servicio": srv,
                    "precios": precios
                })

    if items:
        cols = sorted(list(detected_cols)) if detected_cols else ["Precio"]
        return {
            "titulo": default_title,
            "columnas_pago": cols,
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

        # Si no se pudo procesar tabularmente o es otro formato, intentar extraer texto y usar Gemini
        if os.getenv("GEMINI_API_KEY"):
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
