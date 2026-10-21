#!/usr/bin/env python3
"""
scripts/ops/generate_demos_from_csv.py — Generador Masivo de Demos Outbound
Procesa listas de prospectos en formato CSV (ej: Maps Scraper), genera las páginas
web en modo demo con IA, fotos de Unsplash, mapa y Lista de Precios interactiva,
y exporta un nuevo CSV con las columnas `slug` y `link_demo` listo para prospección.
"""

import os
import sys
import re
import csv
import json
import time
import uuid
import logging
import argparse
import unicodedata

# Asegurar que el directorio raíz del proyecto esté en el path de importación
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

from dotenv import load_dotenv
load_dotenv()

from app import (
    generar_plantilla_dinamica,
    buscar_foto_unsplash,
    obtener_coordenadas,
    slugify,
    supabase,
    DEMO_SITES
)

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] DEMO_GENERATOR: %(message)s"
)

def normalizar_texto(texto):
    """Elimina acentos y normaliza a minúsculas para comparaciones."""
    if not texto:
        return ""
    texto_str = str(texto).strip()
    return unicodedata.normalize('NFKD', texto_str).encode('ASCII', 'ignore').decode('utf-8').lower()

def normalizar_telefono(phone_raw):
    """
    Normaliza el número de teléfono al formato internacional de WhatsApp Argentina (549...).
    Soporta formatos tipo: +54 11 3471-0787, 011 3471-0787, 11 3471 0787, 15 3471-0787, etc.
    """
    if not phone_raw:
        return ""
    digits = re.sub(r'\D', '', str(phone_raw))
    if not digits:
        return ""
    
    # Si comienza con 01115 (13 dígitos: 0 + 11 + 15 + 8 dígitos)
    if digits.startswith("01115") and len(digits) == 13:
        return f"54911{digits[5:]}"
    # Si comienza con 1115 (12 dígitos: 11 + 15 + 8 dígitos)
    if digits.startswith("1115") and len(digits) == 12:
        return f"54911{digits[4:]}"
    # Si ya comienza con 549 y tiene longitud estándar (13 dígitos)
    if digits.startswith("549") and len(digits) >= 12:
        return digits
    # Si comienza con 54 pero le falta el 9 móvil (12 dígitos: ej 541134710787)
    if digits.startswith("54") and len(digits) == 12:
        return f"549{digits[2:]}"
    # Si comienza con 011 u otro código de área con 0 (11 dígitos)
    if digits.startswith("0") and len(digits) == 11:
        return f"549{digits[1:]}"
    # Si comienza con 15 (10 dígitos en AMBA sin código de área)
    if digits.startswith("15") and len(digits) == 10:
        return f"54911{digits[2:]}"
    # Si tiene 10 dígitos (código de área + número, ej: 1134710787)
    if len(digits) == 10:
        return f"549{digits}"
    # Si tiene 11 dígitos y empieza con 11 (ej 1115347107)
    if len(digits) == 11 and digits.startswith("1115"):
        return f"54911{digits[4:]}"

    return digits

def detectar_columnas(fieldnames):
    """
    Mapea de forma tolerante los nombres de columnas del CSV a los campos requeridos:
    nombre, telefono, direccion, rubro.
    """
    mapa = {"nombre": None, "telefono": None, "direccion": None, "rubro": None}
    
    patrones_nombre = ["nombre del local", "nombre", "name", "comercio", "business_name", "title", "local", "negocio"]
    patrones_tel = ["telefono", "phone", "celular", "tel", "whatsapp", "telefono celular", "movil", "formatted_phone_number"]
    patrones_dir = ["direccion", "address", "ubicacion", "location", "domicilio", "formatted_address"]
    patrones_rubro = ["rubro", "categoria", "category", "business_type", "tipo de negocio", "actividad", "tipo"]

    for col in fieldnames:
        norm = normalizar_texto(col)
        if not mapa["nombre"] and norm in patrones_nombre:
            mapa["nombre"] = col
        elif not mapa["telefono"] and norm in patrones_tel:
            mapa["telefono"] = col
        elif not mapa["direccion"] and norm in patrones_dir:
            mapa["direccion"] = col
        elif not mapa["rubro"] and norm in patrones_rubro:
            mapa["rubro"] = col

    return mapa

def generar_slug_unico(nombre, supabase_client=None):
    """
    Genera un slug limpio y verifica su disponibilidad en Supabase.
    Si ya existe, añade un sufijo numérico progresivo (-2, -3, etc.).
    """
    base_slug = slugify(nombre)
    if not base_slug:
        base_slug = f"demo-{uuid.uuid4().hex[:6]}"

    slug = base_slug
    if supabase_client:
        suffix = 1
        while True:
            test_slug = base_slug if suffix == 1 else f"{base_slug}-{suffix}"
            try:
                chk = supabase_client.table("websites").select("id").eq("subdomain", test_slug).execute()
                if not chk.data:
                    slug = test_slug
                    break
                suffix += 1
            except Exception as e:
                logging.warning(f"Error consultando disponibilidad de slug '{test_slug}': {e}")
                slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"
                break
    return slug

def procesar_csv(input_path, output_path=None, limit=None, skip_sleep=False, supabase_client=supabase):
    """
    Función principal de procesamiento por lotes de demos.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"El archivo de entrada no existe: {input_path}")

    if not output_path:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_con_demos.csv"

    print(f"\n📂 Leyendo archivo CSV: {input_path}")
    
    filas = []
    # Leer archivo tolerando diferentes encodings (utf-8-sig, utf-8, latin-1)
    encoding_detectado = 'utf-8-sig'
    try:
        with open(input_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            filas = list(reader)
    except UnicodeDecodeError:
        encoding_detectado = 'latin-1'
        with open(input_path, mode='r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            filas = list(reader)

    if not filas or not fieldnames:
        print("⚠️ El archivo CSV está vacío o no contiene encabezados.")
        return {"total_procesados": 0, "demos": [], "output_path": output_path}

    mapa_cols = detectar_columnas(fieldnames)
    print(f"🔍 Columnas detectadas: {mapa_cols}")

    if not mapa_cols["nombre"]:
        raise ValueError(f"No se encontró una columna de nombre comercial en el CSV. Columnas disponibles: {fieldnames}")

    total_filas = len(filas)
    if limit and limit > 0:
        filas = filas[:limit]
        print(f"⚙️ Límite aplicado: procesando primeras {len(filas)} filas de {total_filas}.")

    # Preparar campos de salida
    salida_fieldnames = list(fieldnames)
    if "slug" not in salida_fieldnames:
        salida_fieldnames.append("slug")
    if "link_demo" not in salida_fieldnames:
        salida_fieldnames.append("link_demo")

    demos_generadas = []
    total_a_procesar = len(filas)
    print(f"\n🚀 Iniciando generación masiva de {total_a_procesar} demos...\n")

    for i, fila in enumerate(filas, 1):
        nombre = str(fila.get(mapa_cols["nombre"]) or "").strip()
        if not nombre:
            print(f"[{i}/{total_a_procesar}] ⏭️ Fila sin nombre comercial, saltando...")
            fila["slug"] = ""
            fila["link_demo"] = ""
            continue

        tel_raw = fila.get(mapa_cols["telefono"]) if mapa_cols["telefono"] else ""
        phone_norm = normalizar_telefono(tel_raw)

        direccion = str(fila.get(mapa_cols["direccion"]) or "").strip() if mapa_cols["direccion"] else ""
        rubro = str(fila.get(mapa_cols["rubro"]) or "").strip() if mapa_cols["rubro"] else ""
        if not rubro:
            rubro = "Comercio"

        # 1. Generar plantilla dinámica con Gemini AI y lista de precios
        try:
            res_ia = generar_plantilla_dinamica(rubro, nombre, direccion, "Lunes a Sábado 09:00 a 19:00")
        except Exception as e:
            logging.error(f"Error generando plantilla dinámica para '{nombre}': {e}")
            res_ia = {
                "titulo_web": nombre,
                "subtitulo": rubro,
                "paleta_colores": {"primario": "#4f46e5", "secundario": "#6366f1"},
                "servicios_sugeridos": ["Servicio 1", "Servicio 2", "Servicio 3"],
                "descripciones_servicios": ["Descripción 1", "Descripción 2", "Descripción 3"],
                "foto_hero_query": rubro,
                "fotos_queries": [rubro, rubro, rubro],
                "horario": "Lunes a Sábado 09:00 a 19:00",
                "ubicacion_detectada": direccion,
                "galeria": []
            }

        # 2. Búsqueda de fotos en Unsplash
        used_image_urls = set()
        foto_hero_query = res_ia.get("foto_hero_query", rubro)
        res_ia["foto_hero"] = buscar_foto_unsplash(foto_hero_query, rubro, used_image_urls)
        res_ia["fotos_servicios"] = [
            buscar_foto_unsplash(q, rubro, used_image_urls)
            for q in res_ia.get("fotos_queries", [rubro, rubro, rubro])
        ]

        # 3. Coordenadas y mapa
        res_ia["mapa"] = obtener_coordenadas(direccion or res_ia.get("ubicacion_detectada"))
        res_ia["plan_type"] = "demo"
        if phone_norm:
            res_ia["whatsapp_contacto"] = phone_norm

        # 4. Generar slug único
        slug = generar_slug_unico(nombre, supabase_client)
        link_demo = f"https://{slug}.tuweblista.com.ar"

        # 5. Persistir en Supabase (si está disponible)
        if supabase_client:
            try:
                # Upsert de cliente (si no tiene teléfono, generar uno sintético único)
                client_phone = phone_norm if phone_norm else f"549110000{uuid.uuid4().hex[:4]}"
                cli_res = supabase_client.table("clients").upsert({
                    "phone": client_phone,
                    "name": nombre,
                    "business_type": rubro,
                    "status": "active"
                }, on_conflict="phone").execute()
                
                client_id = cli_res.data[0]["id"]
                
                web_res = supabase_client.table("websites").insert({
                    "client_id": client_id,
                    "subdomain": slug,
                    "seo_title": res_ia.get("titulo_web", nombre),
                    "status": "demo"
                }).execute()
                
                website_id = web_res.data[0]["id"]
                
                supabase_client.table("website_content").insert({
                    "website_id": website_id,
                    "content": json.dumps(res_ia),
                    "is_current": True
                }).execute()
            except Exception as se:
                logging.warning(f"Error guardando en Supabase para '{nombre}': {se}")

        # Guardar también en la caché en memoria de la app
        DEMO_SITES[slug] = {
            "web_content": res_ia,
            "client": {"phone": phone_norm, "name": nombre},
            "status": "demo",
            "plan_type": "demo"
        }

        # Actualizar fila
        fila["slug"] = slug
        fila["link_demo"] = link_demo
        demos_generadas.append({"nombre": nombre, "slug": slug, "link_demo": link_demo, "telefono": phone_norm})

        print(f"[{i}/{total_a_procesar}] ✅ {nombre} -> {link_demo}")

        # Pausa de seguridad para respetar cuotas de APIs
        if not skip_sleep and i < total_a_procesar:
            time.sleep(1)

    # 6. Escribir archivo CSV resultante con utf-8-sig (compatible con Excel)
    with open(output_path, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=salida_fieldnames)
        writer.writeheader()
        writer.writerows(filas)

    print(f"\n🎉 Lote finalizado con éxito! {len(demos_generadas)} demos generadas.")
    print(f"💾 Archivo guardado en: {output_path}\n")

    return {
        "total_procesados": len(demos_generadas),
        "demos": demos_generadas,
        "output_path": output_path
    }

def main():
    parser = argparse.ArgumentParser(description="Generador Masivo de Demos para Outbound Comercial de TuWebLista")
    parser.add_argument("-i", "--input", required=True, help="Ruta al archivo CSV con prospectos de entrada")
    parser.add_argument("-o", "--output", default=None, help="Ruta al archivo CSV de salida (default: [input]_con_demos.csv)")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Cantidad máxima de demos a generar del lote")
    parser.add_argument("--skip-sleep", action="store_true", help="Omitir la pausa de 1s entre llamadas (útil para pruebas unitarias)")

    args = parser.parse_args()

    try:
        procesar_csv(
            input_path=args.input,
            output_path=args.output,
            limit=args.limit,
            skip_sleep=args.skip_sleep
        )
    except Exception as e:
        print(f"\n❌ ERROR durante el procesamiento: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

