#!/usr/bin/env python3
"""
scripts/ops/send_outbound_campaign.py — Motor de Despacho de Campaña Outbound
Envía la plantilla oficial de Meta `propuesta_web_comercio` a comercios prospectados.
Incluye:
- Pacing de seguridad configurable (delay entre envíos).
- Filtro estricto de exclusión para números en `opt_outs`.
- Prevención de duplicados mediante columna `enviado_fecha`.
- Soporte para simulación con `--dry-run`.
"""

import os
import sys
import re
import csv
import time
import datetime
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

from sender import send_whatsapp_template
from bot_engine import is_opted_out
from scripts.ops.generate_demos_from_csv import normalizar_telefono, detectar_columnas

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] OUTBOUND_CAMPAIGN: %(message)s"
)

def normalizar_texto(texto):
    if not texto:
        return ""
    texto_str = str(texto).strip()
    return unicodedata.normalize('NFKD', texto_str).encode('ASCII', 'ignore').decode('utf-8').lower()

def extraer_localidad(direccion):
    """
    Extrae un nombre amigable de barrio o localidad a partir de una dirección.
    Ej: "Av. Santa Fe 1234, Palermo, CABA" -> "Palermo"
        "Rivadavia 5678, Haedo" -> "Haedo"
        "Belgrano" -> "Belgrano"
    """
    if not direccion:
        return "tu zona"
    
    partes = [p.strip() for p in str(direccion).split(",") if p.strip()]
    if len(partes) >= 2:
        segunda = partes[1]
        # Si la segunda parte no es puramente numérica (ej. no es código postal)
        if not re.match(r'^\d+$', segunda) and len(segunda) > 2:
            return segunda
    
    primera = partes[0] if partes else ""
    # Si la primera parte parece solo una calle con número, devolver "tu zona"
    if re.search(r'\d+', primera) and len(partes) == 1:
        return "tu zona"
        
    return primera if primera else "tu zona"

def detectar_columna_link(fieldnames):
    """Detecta la columna que contiene el link o slug de la demo."""
    patrones = ["link_demo", "link", "url", "web_demo", "url_demo", "demo", "slug"]
    for col in fieldnames:
        norm = normalizar_texto(col)
        if norm in patrones:
            return col
    return None

def procesar_campana(input_path, output_path=None, limit=None, delay=12, dry_run=False):
    """
    Lee el archivo CSV de prospectos y envía la plantilla oficial de Meta.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"El archivo de entrada no existe: {input_path}")

    # Si no se especifica salida, se actualiza el mismo archivo o se crea un archivo de progreso
    if not output_path:
        output_path = input_path

    print(f"\n📂 Leyendo archivo CSV para campaña Outbound: {input_path}")

    filas = []
    try:
        with open(input_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            filas = list(reader)
    except UnicodeDecodeError:
        with open(input_path, mode='r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            filas = list(reader)

    if not filas or not fieldnames:
        print("⚠️ El archivo CSV está vacío o sin encabezados.")
        return {"total": 0, "enviados": 0, "opt_out": 0, "ya_enviados": 0, "errores": 0}

    mapa_cols = detectar_columnas(fieldnames)
    col_link = detectar_columna_link(fieldnames)

    if not mapa_cols["nombre"] or not mapa_cols["telefono"]:
        raise ValueError(f"Faltan columnas requeridas ('nombre' y 'telefono') en el CSV. Columnas: {fieldnames}")

    # Asegurar columnas de auditoría en la salida
    salida_fieldnames = list(fieldnames)
    if "enviado_fecha" not in salida_fieldnames:
        salida_fieldnames.append("enviado_fecha")
    if "estado_envio" not in salida_fieldnames:
        salida_fieldnames.append("estado_envio")

    total_filas = len(filas)
    if limit and limit > 0:
        filas_a_procesar = filas[:limit]
        print(f"⚙️ Límite aplicado: procesando primeras {len(filas_a_procesar)} filas de {total_filas}.")
    else:
        filas_a_procesar = filas

    enviados = 0
    omitidos_opt_out = 0
    omitidos_ya_enviados = 0
    errores = 0

    print(f"\n🚀 Iniciando despacho Outbound (Plantilla: 'propuesta_web_comercio', Delay: {delay}s, Dry-run: {dry_run})...\n")

    for i, fila in enumerate(filas_a_procesar, 1):
        nombre = str(fila.get(mapa_cols["nombre"]) or "").strip()
        tel_raw = str(fila.get(mapa_cols["telefono"]) or "").strip()
        phone = normalizar_telefono(tel_raw)

        # 1. Verificar si ya fue enviado previamente
        enviado_previo = str(fila.get("enviado_fecha") or "").strip()
        if enviado_previo:
            print(f"[{i}/{len(filas_a_procesar)}] ⏭️ {nombre} ({phone}) ya fue contactado el {enviado_previo}. Saltando...")
            omitidos_ya_enviados += 1
            continue

        if not phone:
            print(f"[{i}/{len(filas_a_procesar)}] ⚠️ {nombre} no tiene un número telefónico válido. Saltando...")
            fila["estado_envio"] = "telefono_invalido"
            errores += 1
            continue

        # 2. Verificar Opt-Out
        if is_opted_out(phone):
            print(f"[{i}/{len(filas_a_procesar)}] 🛑 {nombre} ({phone}) está en lista de OPT-OUT (no contactar). Omitiendo...")
            fila["estado_envio"] = "opt_out"
            omitidos_opt_out += 1
            continue

        # 3. Extraer parámetros para la plantilla Meta
        # {{1}}: Nombre del local / comercio
        # {{2}}: Barrio / Localidad
        # {{3}}: Enlace a la demo interactiva
        direccion = str(fila.get(mapa_cols["direccion"]) or "").strip() if mapa_cols["direccion"] else ""
        localidad = extraer_localidad(direccion)

        link_demo = ""
        if col_link and fila.get(col_link):
            raw_val = str(fila.get(col_link)).strip()
            if raw_val.startswith("http"):
                link_demo = raw_val
            else:
                link_demo = f"https://{raw_val}.tuweblista.com.ar"
        elif fila.get("slug"):
            link_demo = f"https://{fila['slug']}.tuweblista.com.ar"
        else:
            link_demo = "https://tuweblista.com.ar"

        parametros = [nombre, localidad, link_demo]

        # 4. Enviar plantilla o simular en dry-run
        if dry_run:
            print(f"[{i}/{len(filas_a_procesar)}] 🧪 [DRY-RUN] Simulación de envío a {nombre} ({phone}):")
            print(f"     👉 Parámetros: {{1}}='{nombre}', {{2}}='{localidad}', {{3}}='{link_demo}'")
            fila["estado_envio"] = "dry_run"
            enviados += 1
        else:
            print(f"[{i}/{len(filas_a_procesar)}] 🚀 Enviando a {nombre} ({phone})...")
            exito = send_whatsapp_template(
                to_number=phone,
                template_name="propuesta_web_comercio",
                language_code="es_AR",
                body_parameters=parametros
            )

            if exito:
                ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fila["enviado_fecha"] = ahora_str
                fila["estado_envio"] = "enviado"
                enviados += 1
                print(f"     ✅ Plantilla entregada con éxito a {phone} ({ahora_str})")
            else:
                fila["estado_envio"] = "error_meta"
                errores += 1
                print(f"     ❌ Falló el envío a {phone}")

            # Pacing de seguridad entre llamadas
            if i < len(filas_a_procesar) and delay > 0:
                print(f"     ⏳ Esperando {delay}s por pacing de seguridad...")
                time.sleep(delay)

    # 5. Guardar CSV actualizado con marcas de tiempo
    with open(output_path, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=salida_fieldnames)
        writer.writeheader()
        writer.writerows(filas)

    print(f"\n=======================================================")
    print(f"🎉 Campaña Outbound Finalizada:")
    print(f"   - Total procesados: {len(filas_a_procesar)}")
    print(f"   - Enviados: {enviados}")
    print(f"   - Omitidos por Opt-Out: {omitidos_opt_out}")
    print(f"   - Omitidos ya enviados previamente: {omitidos_ya_enviados}")
    print(f"   - Errores: {errores}")
    print(f"💾 Archivo actualizado en: {output_path}")
    print(f"=======================================================\n")

    return {
        "total": len(filas_a_procesar),
        "enviados": enviados,
        "opt_out": omitidos_opt_out,
        "ya_enviados": omitidos_ya_enviados,
        "errores": errores,
        "output_path": output_path
    }

def main():
    parser = argparse.ArgumentParser(description="Despacho de Campaña Outbound con Plantilla Oficial de Meta Cloud API")
    parser.add_argument("-i", "--input", required=True, help="Ruta al archivo CSV con prospectos y demos generadas")
    parser.add_argument("-o", "--output", default=None, help="Ruta al archivo CSV de salida (default: actualiza el archivo de entrada)")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Límite máximo de prospectos a contactar")
    parser.add_argument("-d", "--delay", type=int, default=12, help="Segundos de espera entre cada mensaje para pacing de seguridad (default: 12)")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación: no realiza llamadas reales a la API de WhatsApp")

    args = parser.parse_args()

    try:
        procesar_campana(
            input_path=args.input,
            output_path=args.output,
            limit=args.limit,
            delay=args.delay,
            dry_run=args.dry_run
        )
    except Exception as e:
        print(f"\n❌ ERROR durante la campaña: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

