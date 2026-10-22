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
import json
import time
import datetime
import logging
import argparse
import threading
import unicodedata
from typing import Optional, Dict, Any

# Asegurar que el directorio raíz del proyecto esté en el path de importación
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

from dotenv import load_dotenv
load_dotenv()

from sender import send_whatsapp_template
from bot_engine import is_opted_out

# Archivos de señal y persistencia de estado para sincronización multi-worker (Gunicorn)
STOP_SIGNAL_FILE = os.path.join(ROOT_DIR, "leads", ".campaign_stop")
STATE_FILE = os.path.join(ROOT_DIR, "leads", ".campaign_state.json")

def _save_campaign_state_disk(state_dict: Dict[str, Any]):
    """Persiste el estado de la campaña en disco de forma atómica para sincronización multi-worker."""
    try:
        leads_dir = os.path.join(ROOT_DIR, "leads")
        os.makedirs(leads_dir, exist_ok=True)
        temp_file = STATE_FILE + f".tmp.{os.getpid()}"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, STATE_FILE)
    except Exception as e:
        logging.error(f"Error persistiendo estado de campaña en disco: {e}")

def _load_campaign_state_disk() -> Optional[Dict[str, Any]]:
    """Lee el estado persistido de la campaña desde disco si existe."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error leyendo estado de campaña desde disco: {e}")
        return None

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

# Mapeo oficial de Códigos Postales de CABA a barrios reales
CP_CABA_BARRIOS = {
    "1419": "Villa Devoto", "1417": "Villa del Parque", "1414": "Palermo",
    "1425": "Palermo", "1426": "Belgrano", "1428": "Belgrano",
    "1429": "Núñez", "1430": "Saavedra", "1431": "Villa Urquiza",
    "1427": "Villa Ortúzar", "1424": "Caballito", "1405": "Caballito",
    "1406": "Flores", "1407": "Floresta", "1408": "Liniers",
    "1416": "La Paternal", "1418": "Villa Real", "1410": "Villa Urquiza",
    "1437": "Nueva Pompeya", "1439": "Villa Lugano", "1440": "Mataderos",
    "1409": "Monte Castro", "1420": "Coghlan", "1434": "Parque Patricios",
    "1401": "Parque Chacabuco", "1268": "Barracas", "1094": "Balvanera",
    "1291": "Barracas", "1277": "Barracas"
}

# Términos territoriales genéricos o provinciales a descartar al buscar la localidad/barrio específico
DISCARDED_GEO_TERMS = {
    "argentina", "toda argentina", "pais", "republica argentina",
    "caba", "capital federal", "capital", "ciudad autonoma de buenos aires",
    "cdad autonoma de buenos aires", "cdad. autonoma de buenos aires",
    "buenos aires", "provincia de buenos aires", "prov de buenos aires",
    "prov. de buenos aires", "pcia de buenos aires", "pcia. de buenos aires",
    "bs as", "gba", "conurbano", "gran buenos aires", "amba"
}

def extraer_localidad(fila=None, direccion=None):
    """
    Extrae un nombre amigable de barrio o localidad a partir de los datos del comercio.
    Soporta:
    1. Si 'fila' tiene columna 'Zona' o 'zona', limpiando sufijos (ej: 'Palermo, CABA' -> 'Palermo').
    2. Detección de código postal de CABA (ej: C1419, CP 1419, 1419) mapeado con CP_CABA_BARRIOS.
    3. Partes intermedias en dirección para ciudades del interior (ej: 'Calle 123, Tandil, Prov. de Buenos Aires, Argentina' -> 'Tandil').
    4. Fallback inteligente a 'Buenos Aires' o 'tu zona'.
    Retrocompatible: acepta extraer_localidad(direccion) si el primer argumento es un string.
    """
    if isinstance(fila, str) and direccion is None:
        direccion = fila
        fila = {}
    elif fila is None:
        fila = {}
    elif not isinstance(fila, dict):
        fila = {}

    # Si direccion no vino explícita, buscar en la fila
    if not direccion and isinstance(fila, dict):
        for k in ["Dirección", "Direccion", "direccion", "address", "formatted_address"]:
            if fila.get(k):
                direccion = str(fila[k]).strip()
                break

    direccion_str = str(direccion or "").strip()

    # a) Si fila tiene columna 'Zona' o 'zona' (proveniente de geo-catalog o maps scraper)
    if fila and isinstance(fila, dict):
        for col in ["Zona", "zona", "Barrio", "barrio", "Localidad", "localidad"]:
            val = fila.get(col)
            if val:
                val_str = str(val).strip()
                if val_str:
                    # Limpiar sufijos como ', CABA', ', Buenos Aires', etc.
                    cand = re.split(r'[,/|-]', val_str)[0].strip()
                    cand = re.sub(r'\(.*?\)', '', cand).strip()
                    cand_norm = normalizar_texto(cand)
                    if cand_norm and cand_norm not in DISCARDED_GEO_TERMS and len(cand) >= 3:
                        return cand

    # Si hay dirección, analizarla
    if direccion_str:
        partes = [p.strip() for p in direccion_str.split(",") if p.strip()]

        # b) Detectar código postal en dirección y mapear con CP_CABA_BARRIOS
        # 1. Búsqueda explícita con prefijo C, CP o C.P. en cualquier parte
        cp_match = re.search(r'\b(?:CP|C\.P\.|C)\s*(\d{4})\b', direccion_str, flags=re.IGNORECASE)
        if cp_match:
            cp_code = cp_match.group(1)
            if cp_code in CP_CABA_BARRIOS:
                return CP_CABA_BARRIOS[cp_code]

        # 2. Búsqueda de 4 dígitos en partes secundarias (después de la primera coma para no confundir con altura de calle)
        if len(partes) > 1:
            for p in partes[1:]:
                m = re.search(r'\b(\d{4})\b', p)
                if m:
                    cp_code = m.group(1)
                    if cp_code in CP_CABA_BARRIOS:
                        return CP_CABA_BARRIOS[cp_code]

        # c) Extraer ciudad/localidad intermedia descartando términos territoriales genéricos
        if len(partes) > 1:
            for p in partes[1:]:
                # Limpiar posibles códigos postales al inicio o fin
                cand = re.sub(r'\b[CB]?\d{4}[A-Z]{0,3}\b', '', p, flags=re.IGNORECASE).strip()
                cand = re.sub(r'^(?:CP|C\.P\.)\s*\d{4}', '', cand, flags=re.IGNORECASE).strip()
                cand = cand.strip(" ,.-")
                cand_norm = normalizar_texto(cand)
                if cand_norm and cand_norm not in DISCARDED_GEO_TERMS and len(cand) >= 3 and not re.match(r'^\d+$', cand):
                    return cand

        # Si solo tiene una parte (ej: "Belgrano" o "Haedo") y no contiene números de calle
        if len(partes) == 1:
            primera = partes[0]
            if not re.search(r'\d+', primera):
                cand_norm = normalizar_texto(primera)
                if cand_norm and cand_norm not in DISCARDED_GEO_TERMS and len(primera) >= 3:
                    return primera

        # d) Fallback a 'Buenos Aires' (si está en CABA/GBA) o 'tu zona'
        dir_norm = normalizar_texto(direccion_str)
        if any(k in dir_norm for k in ["caba", "capital", "buenos aires", "gba", "conurbano", "amba"]):
            return "Buenos Aires"

    return "tu zona"

def detectar_columna_link(fieldnames):
    """Detecta la columna que contiene el link o slug de la demo."""
    patrones = ["link_demo", "link", "url", "web_demo", "url_demo", "demo", "slug"]
    for col in fieldnames:
        norm = normalizar_texto(col)
        if norm in patrones:
            return col
    return None

def procesar_campana(
    input_path,
    output_path=None,
    limit=None,
    delay=12,
    dry_run=False,
    stop_event=None,
    progress_callback=None
):
    """
    Lee el archivo CSV de prospectos y envía la plantilla oficial de Meta.
    Soporta cancelación controlada vía stop_event y reporte reactivo de progreso vía progress_callback.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"El archivo de entrada no existe: {input_path}")

    # Si no se especifica salida, se actualiza el mismo archivo o se crea un archivo de progreso
    if not output_path:
        output_path = input_path

    msg_init = f"📂 Leyendo archivo CSV para campaña Outbound: {input_path}"
    print(f"\n{msg_init}")
    if progress_callback:
        progress_callback({"log": msg_init})

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
        msg_empty = "⚠️ El archivo CSV está vacío o sin encabezados."
        print(msg_empty)
        if progress_callback:
            progress_callback({"log": msg_empty, "total": 0})
        return {"total": 0, "enviados": 0, "opt_out": 0, "ya_enviados": 0, "errores": 0, "output_path": output_path}

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

    msg_start = f"🚀 Iniciando despacho Outbound (Plantilla: 'propuesta_web_comercio', Delay: {delay}s, Dry-run: {dry_run})..."
    print(f"\n{msg_start}\n")
    if progress_callback:
        progress_callback({
            "log": msg_start,
            "total": len(filas_a_procesar),
            "enviados": 0,
            "opt_out": 0,
            "ya_enviados": 0,
            "errores": 0
        })

    for i, fila in enumerate(filas_a_procesar, 1):
        if (stop_event and stop_event.is_set()) or os.path.exists(STOP_SIGNAL_FILE):
            msg_stop = f"🛑 Campaña detenida por solicitud de usuario tras procesar {i-1} filas."
            print(msg_stop)
            if progress_callback:
                progress_callback({"log": msg_stop, "current_contact": "", "status": "stopped"})
            break

        nombre = str(fila.get(mapa_cols["nombre"]) or "").strip()
        tel_raw = str(fila.get(mapa_cols["telefono"]) or "").strip()
        phone = normalizar_telefono(tel_raw)

        contact_label = f"{nombre} ({phone})" if phone else (nombre or f"Fila #{i}")
        if progress_callback:
            progress_callback({
                "total": len(filas_a_procesar),
                "enviados": enviados,
                "opt_out": omitidos_opt_out,
                "ya_enviados": omitidos_ya_enviados,
                "errores": errores,
                "current_contact": contact_label
            })

        # 1. Verificar si ya fue enviado previamente
        enviado_previo = str(fila.get("enviado_fecha") or "").strip()
        if enviado_previo:
            msg_skip = f"[{i}/{len(filas_a_procesar)}] ⏭️ {nombre} ({phone}) ya fue contactado el {enviado_previo}. Saltando..."
            print(msg_skip)
            omitidos_ya_enviados += 1
            if progress_callback:
                progress_callback({"ya_enviados": omitidos_ya_enviados, "log": msg_skip})
            continue

        if not phone:
            msg_err_tel = f"[{i}/{len(filas_a_procesar)}] ⚠️ {nombre} no tiene un número telefónico válido. Saltando..."
            print(msg_err_tel)
            fila["estado_envio"] = "telefono_invalido"
            errores += 1
            if progress_callback:
                progress_callback({"errores": errores, "log": msg_err_tel})
            continue

        # 2. Verificar Opt-Out
        if is_opted_out(phone):
            msg_opt = f"[{i}/{len(filas_a_procesar)}] 🛑 {nombre} ({phone}) está en lista de OPT-OUT (no contactar). Omitiendo..."
            print(msg_opt)
            fila["estado_envio"] = "opt_out"
            omitidos_opt_out += 1
            if progress_callback:
                progress_callback({"opt_out": omitidos_opt_out, "log": msg_opt})
            continue

        # 3. Extraer parámetros para la plantilla Meta
        # {{1}}: Nombre del local / comercio
        # {{2}}: Barrio / Localidad
        # {{3}}: Enlace a la demo interactiva
        direccion = str(fila.get(mapa_cols["direccion"]) or "").strip() if mapa_cols["direccion"] else ""
        localidad = extraer_localidad(fila, direccion)

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
            msg_dry = f"[{i}/{len(filas_a_procesar)}] 🧪 [DRY-RUN] Simulación a {nombre} ({phone}) | Loc: {localidad} | Demo: {link_demo}"
            print(msg_dry)
            fila["estado_envio"] = "dry_run"
            enviados += 1
            if progress_callback:
                progress_callback({"enviados": enviados, "log": msg_dry})
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
                msg_ok = f"[{i}/{len(filas_a_procesar)}] ✅ Plantilla entregada a {nombre} ({phone}) [{localidad}]"
                print(f"     ✅ Plantilla entregada con éxito a {phone} ({ahora_str})")
                if progress_callback:
                    progress_callback({"enviados": enviados, "log": msg_ok})
            else:
                fila["estado_envio"] = "error_meta"
                errores += 1
                msg_fail = f"[{i}/{len(filas_a_procesar)}] ❌ Falló el envío a {nombre} ({phone})"
                print(f"     ❌ Falló el envío a {phone}")
                if progress_callback:
                    progress_callback({"errores": errores, "log": msg_fail})

        # Pacing de seguridad entre llamadas
        if i < len(filas_a_procesar) and delay > 0:
            stopped = False
            tiempo_inicio_espera = time.time()
            while (time.time() - tiempo_inicio_espera) < delay:
                if (stop_event and stop_event.is_set()) or os.path.exists(STOP_SIGNAL_FILE):
                    stopped = True
                    break
                # Dormir en micro-intervalos de hasta 0.25s para detectar señales de detención sin demora
                tiempo_restante = delay - (time.time() - tiempo_inicio_espera)
                time.sleep(min(0.25, max(0.01, tiempo_restante)))

            if stopped:
                msg_pacing_stop = "🛑 Campaña detenida durante el intervalo de espera (pacing)."
                print(msg_pacing_stop)
                if progress_callback:
                    progress_callback({"log": msg_pacing_stop, "current_contact": "", "status": "stopped"})
                break

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

    if progress_callback:
        progress_callback({
            "total": len(filas_a_procesar),
            "enviados": enviados,
            "opt_out": omitidos_opt_out,
            "ya_enviados": omitidos_ya_enviados,
            "errores": errores,
            "current_contact": "",
            "log": f"Campaña finalizada. Enviados: {enviados}, Opt-Out: {omitidos_opt_out}, Errores: {errores}"
        })

    return {
        "total": len(filas_a_procesar),
        "enviados": enviados,
        "opt_out": omitidos_opt_out,
        "ya_enviados": omitidos_ya_enviados,
        "errores": errores,
        "output_path": output_path
    }


# ==============================================================================
# Gestor Singleton de Campaña en Segundo Plano para Flask
# ==============================================================================
_campaign_lock = threading.Lock()
_campaign_task: Optional["CampaignTask"] = None

class CampaignTask:
    def __init__(self, input_path: str, output_path: Optional[str] = None, limit: int = 20, delay: int = 15, dry_run: bool = False):
        self.input_path = input_path
        self.output_path = output_path or input_path
        self.filename = os.path.basename(input_path)
        self.limit = limit
        self.delay = delay
        self.dry_run = dry_run
        self.stop_event = threading.Event()
        self.status = "idle"  # idle, running, completed, stopped, error
        self.total = 0
        self.enviados = 0
        self.opt_out = 0
        self.ya_enviados = 0
        self.errores = 0
        self.current_contact = ""
        self.logs = []
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.error_message: Optional[str] = None
        self.thread: Optional[threading.Thread] = None

    def add_log(self, msg: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{ts}] {msg}"
        self.logs.append(log_entry)
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "filename": self.filename,
            "total": self.total,
            "enviados": self.enviados,
            "opt_out": self.opt_out,
            "ya_enviados": self.ya_enviados,
            "errores": self.errores,
            "current_contact": self.current_contact,
            "limit": self.limit,
            "delay": self.delay,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "logs": list(self.logs)
        }

    def persist_state(self):
        """Guarda el estado actual en disco para que cualquier worker de Gunicorn lo lea."""
        _save_campaign_state_disk(self.get_status())

    def run(self):
        self.status = "running"
        self.started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.add_log(f"Iniciando campaña con '{self.filename}' (Límite: {self.limit}, Delay: {self.delay}s, Dry-run: {self.dry_run})")
        self.persist_state()

        def progress_cb(update: Dict[str, Any]):
            with _campaign_lock:
                if "status" in update: self.status = update["status"]
                if "total" in update: self.total = update["total"]
                if "enviados" in update: self.enviados = update["enviados"]
                if "opt_out" in update: self.opt_out = update["opt_out"]
                if "ya_enviados" in update: self.ya_enviados = update["ya_enviados"]
                if "errores" in update: self.errores = update["errores"]
                if "current_contact" in update: self.current_contact = update["current_contact"]
                if "log" in update: self.add_log(update["log"])
                self.persist_state()

        try:
            res = procesar_campana(
                input_path=self.input_path,
                output_path=self.output_path,
                limit=self.limit,
                delay=self.delay,
                dry_run=self.dry_run,
                stop_event=self.stop_event,
                progress_callback=progress_cb
            )
            with _campaign_lock:
                self.total = res.get("total", self.total)
                self.enviados = res.get("enviados", self.enviados)
                self.opt_out = res.get("opt_out", self.opt_out)
                self.ya_enviados = res.get("ya_enviados", self.ya_enviados)
                self.errores = res.get("errores", self.errores)
                self.current_contact = ""
                if self.stop_event.is_set() or os.path.exists(STOP_SIGNAL_FILE):
                    self.status = "stopped"
                    self.add_log("Campaña detenida por el usuario.")
                else:
                    self.status = "completed"
                    self.add_log(f"Campaña finalizada exitosamente. Total enviados: {self.enviados}")
        except Exception as e:
            logging.error(f"Error fatal en CampaignTask: {e}")
            with _campaign_lock:
                self.status = "error"
                self.error_message = str(e)
                self.current_contact = ""
                self.add_log(f"Error fatal: {e}")
        finally:
            with _campaign_lock:
                self.completed_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.persist_state()
            # Una vez concluida la tarea (detenida o completada), limpiar la señal de detención
            if os.path.exists(STOP_SIGNAL_FILE):
                try:
                    os.remove(STOP_SIGNAL_FILE)
                except Exception:
                    pass

def start_campaign_task(filename: str, limit: int = 20, delay: int = 15, dry_run: bool = False) -> Dict[str, Any]:
    """Inicia una tarea de campaña en segundo plano con soporte multi-worker."""
    global _campaign_task
    with _campaign_lock:
        if _campaign_task and _campaign_task.status == "running":
            return {
                "status": "already_running",
                "error": "Ya hay una campaña en ejecución actualmente.",
                "filename": _campaign_task.filename
            }

        # Comprobar si otro worker de Gunicorn tiene la campaña corriendo en disco
        disk_state = _load_campaign_state_disk()
        if disk_state and disk_state.get("status") == "running" and not os.path.exists(STOP_SIGNAL_FILE):
            return {
                "status": "already_running",
                "error": "Ya hay una campaña en ejecución actualmente.",
                "filename": disk_state.get("filename", "")
            }

        # 3. Eliminar señal de detención previa si existe
        if os.path.exists(STOP_SIGNAL_FILE):
            try:
                os.remove(STOP_SIGNAL_FILE)
            except Exception as e:
                logging.warning(f"No se pudo eliminar STOP_SIGNAL_FILE: {e}")

        # Resolver ruta del archivo CSV
        # 1. En carpeta leads/
        leads_dir = os.path.join(ROOT_DIR, "leads")
        candidate_path = os.path.join(leads_dir, os.path.basename(filename))
        if not candidate_path.endswith('.csv'):
            candidate_path += '.csv'

        if not os.path.exists(candidate_path):
            # 2. Ruta directa o relativa
            if os.path.exists(filename):
                candidate_path = filename
            elif os.path.exists(os.path.join(ROOT_DIR, filename)):
                candidate_path = os.path.join(ROOT_DIR, filename)
            else:
                return {
                    "status": "error",
                    "error": f"Archivo no encontrado: {filename}"
                }

        task = CampaignTask(
            input_path=candidate_path,
            limit=limit,
            delay=delay,
            dry_run=dry_run
        )
        _campaign_task = task
        task.persist_state()

        thread = threading.Thread(target=task.run, daemon=True, name=f"Campaign-{task.filename}")
        task.thread = thread
        thread.start()

        return {
            "status": "started",
            "message": f"Campaña iniciada para {task.filename}",
            "filename": task.filename,
            "limit": task.limit,
            "delay": task.delay,
            "dry_run": task.dry_run
        }

def get_campaign_status() -> Dict[str, Any]:
    """Retorna el estado de la campaña unificado entre memoria local y disco."""
    global _campaign_task
    with _campaign_lock:
        if _campaign_task:
            status_dict = _campaign_task.get_status()
            if os.path.exists(STOP_SIGNAL_FILE) and status_dict.get("status") == "running":
                status_dict["status"] = "stopping"
            return status_dict

        disk_state = _load_campaign_state_disk()
        if disk_state:
            if os.path.exists(STOP_SIGNAL_FILE) and disk_state.get("status") == "running":
                disk_state["status"] = "stopping"
            return disk_state

        return {
            "status": "idle",
            "message": "Sin campañas iniciadas recientemente.",
            "total": 0,
            "enviados": 0,
            "opt_out": 0,
            "ya_enviados": 0,
            "errores": 0,
            "current_contact": "",
            "logs": []
        }

def stop_campaign_task() -> Dict[str, Any]:
    """Detiene la campaña activa escribiendo la señal en disco y señalando el evento en memoria."""
    global _campaign_task
    with _campaign_lock:
        leads_dir = os.path.join(ROOT_DIR, "leads")
        os.makedirs(leads_dir, exist_ok=True)
        with open(STOP_SIGNAL_FILE, 'w') as f:
            f.write(datetime.datetime.now().isoformat())

        if _campaign_task:
            _campaign_task.stop_event.set()

        disk_state = _load_campaign_state_disk()
        if disk_state and disk_state.get("status") == "running":
            disk_state["status"] = "stopping"
            _save_campaign_state_disk(disk_state)

        filename = _campaign_task.filename if _campaign_task else (disk_state.get("filename", "") if disk_state else "")
        return {
            "status": "stopping",
            "filename": filename,
            "message": "Señal de detención emitida a todos los workers."
        }

def main():
    parser = argparse.ArgumentParser(description="Despacho de Campaña Outbound con Plantilla Oficial de Meta Cloud API")
    parser.add_argument("-i", "--input", required=True, help="Ruta al archivo CSV con prospectos y demos generadas")
    parser.add_argument("-o", "--output", default=None, help="Ruta al archivo CSV de salida (default: actualiza el archivo de entrada)")
    parser.add_argument("-l", "--limit", type=int, default=None, help="Límite máximo de prospectos a contactar")
    parser.add_argument("-d", "--delay", type=int, default=12, help="Segundos de espera entre cada mensaje para pacing de seguridad (default: 12)")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación: no realiza llamadas reales a la API de WhatsApp")

    args = parser.parse_args()

    if os.path.exists(STOP_SIGNAL_FILE):
        try:
            os.remove(STOP_SIGNAL_FILE)
        except Exception:
            pass

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

