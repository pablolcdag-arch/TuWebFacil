#!/usr/bin/env python3
"""
scripts/ops/bulk_maps_scraper.py
Motor de Barrido Masivo de Google Maps (a nivel nacional, provincial o local).
Permite prospección automatizada por rubro y zonas geográficas con:
1. Deduplicación de prospectos en tiempo real mediante normalización telefónica.
2. Freno de seguridad automático (stop loss por max_comercios).
3. Cálculo en vivo de consumo estimado en USD de la Google Places API.
4. Checkpoint y reanudación automática (--resume) preservando zonas y teléfonos ya vistos.
5. Control concurrente con parada limpia (stop_requested) e integración con Flask.
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
import threading
from datetime import datetime
from typing import List, Dict, Set, Optional
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"))

from scripts.utils.arg_geo_catalog import obtener_zonas_por_clave, obtener_presets

# Costos unitarios de Google Places API (USD)
COST_PER_TEXT_SEARCH = 0.032
COST_PER_PLACE_DETAILS = 0.017

SOCIAL_DOMAINS = [
    "instagram.com", "facebook.com", "fb.com", "fb.me", 
    "linktr.ee", "tiktok.com", "wa.me", "whatsapp.com"
]

def normalizar_telefono(phone_raw: str) -> str:
    """
    Normaliza el número de teléfono al formato internacional de WhatsApp Argentina (549...).
    Soporta formatos tipo: +54 11 3471-0787, 011 3471-0787, 11 3471 0787, 15 3471-0787, etc.
    """
    if not phone_raw:
        return ""
    digits = re.sub(r'\D', '', str(phone_raw))
    if not digits:
        return ""
    
    if digits.startswith("01115") and len(digits) == 13:
        return f"54911{digits[5:]}"
    if digits.startswith("1115") and len(digits) == 12:
        return f"54911{digits[4:]}"
    if digits.startswith("549") and len(digits) >= 12:
        return digits
    if digits.startswith("54") and len(digits) == 12:
        return f"549{digits[2:]}"
    if digits.startswith("0") and len(digits) == 11:
        return f"549{digits[1:]}"
    if digits.startswith("15") and len(digits) == 10:
        return f"54911{digits[2:]}"
    if len(digits) == 10:
        return f"549{digits}"
    if len(digits) == 11 and digits.startswith("1115"):
        return f"54911{digits[4:]}"
    return digits

def slugify(text: str) -> str:
    """Convierte texto en un slug seguro para nombres de archivo."""
    text = re.sub(r'[^\w\s-]', '', str(text).lower()).strip()
    return re.sub(r'[-\s]+', '_', text)

class BulkMapsScraper:
    """
    Motor ejecutor de barrido masivo de Google Places API.
    Soporta ejecución síncrona o asíncrona dentro de hilos secundarios.
    """
    def __init__(
        self,
        rubro: str,
        zona_clave: str,
        max_comercios: int = 1000,
        solo_sin_web: bool = True,
        output_file: Optional[str] = None,
        resume: bool = False,
        api_key: Optional[str] = None,
        task_id: Optional[str] = None
    ):
        self.rubro = str(rubro).strip()
        self.zona_clave = str(zona_clave).strip()
        self.max_comercios = int(max_comercios) if max_comercios else 1000
        self.solo_sin_web = bool(solo_sin_web)
        self.resume = bool(resume)
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY", "")
        self.task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"

        # Carpetas
        self.leads_dir = os.path.join(BASE_DIR, "leads")
        os.makedirs(self.leads_dir, exist_ok=True)

        # Nombre de archivo CSV
        slug_rubro = slugify(self.rubro)
        slug_zona = slugify(self.zona_clave)
        if output_file:
            self.output_file = output_file
        else:
            self.output_file = os.path.join(self.leads_dir, f"prospectos_{slug_rubro}_{slug_zona}.csv")
            
        self.csv_filename = os.path.basename(self.output_file)
        self.state_file = os.path.join(self.leads_dir, f".scraper_state_{slug_rubro}_{slug_zona}.json")

        # Control de flujo y estado
        self.stop_requested = threading.Event()
        self.status = "idle"  # "idle" | "running" | "completed" | "stopped" | "error"
        self.error_message: Optional[str] = None
        self.zona_actual: str = ""
        self.indice_zona: int = 0
        self.total_zonas: int = 0
        self.comercios_encontrados: int = 0
        self.consumo_usd: float = 0.0
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None

        # Memoria de deduplicación y checkpoint
        self.seen_phones: Set[str] = set()
        self.completed_zones: Set[str] = set()

    def get_status(self) -> Dict:
        """Retorna un snapshot serializable del estado actual."""
        progress_pct = round((self.indice_zona / self.total_zonas) * 100) if self.total_zonas > 0 else 0
        if self.status == "completed":
            progress_pct = 100
            
        cost_val = round(self.consumo_usd, 4)
        return {
            "task_id": self.task_id,
            "status": self.status,
            "rubro": self.rubro,
            "zona_clave": self.zona_clave,
            # Zonas
            "zona_actual": self.zona_actual,
            "current_zone": self.zona_actual,
            "indice_zona": self.indice_zona,
            "zone_index": self.indice_zona,
            "total_zonas": self.total_zonas,
            "total_zones": self.total_zonas,
            # Progreso
            "progress_percent": progress_pct,
            # Leads
            "comercios_encontrados": self.comercios_encontrados,
            "leads_count": self.comercios_encontrados,
            "total_leads": self.comercios_encontrados,
            "leads": self.comercios_encontrados,
            # Costos
            "consumo_usd": cost_val,
            "estimated_cost": cost_val,
            "estimated_cost_str": f"~${self.consumo_usd:.2f} USD",
            # Archivo
            "csv_filename": self.csv_filename,
            "filename": self.csv_filename,
            "download_url": f"/admin/bulk_scraper/download/{self.csv_filename}" if self.csv_filename else "",
            # Control y errores
            "error": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }

    def request_stop(self):
        """Solicita la detención limpia del scraper."""
        self.stop_requested.set()
        logging.info(f"[{self.task_id}] Señal de detención recibida.")

    def _load_checkpoint(self):
        """Carga datos previos si resume=True y existe archivo de estado."""
        if not self.resume:
            return

        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.completed_zones = set(data.get("completed_zones", []))
                    self.seen_phones = set(data.get("seen_phones", []))
                    self.comercios_encontrados = int(data.get("comercios_encontrados", 0))
                    self.consumo_usd = float(data.get("consumo_usd", 0.0))
                    logging.info(f"[{self.task_id}] Checkpoint cargado: {len(self.completed_zones)} zonas previas, {self.comercios_encontrados} comercios.")
            except Exception as e:
                logging.warning(f"[{self.task_id}] No se pudo leer checkpoint: {e}")

        # Si el CSV existe, poblar seen_phones desde el CSV para no duplicar
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, mode="r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if rows and len(rows) > 1:
                        for row in rows[1:]:
                            if len(row) >= 2:
                                tel_norm = normalizar_telefono(row[1])
                                if tel_norm:
                                    self.seen_phones.add(tel_norm)
                        self.comercios_encontrados = max(self.comercios_encontrados, len(rows) - 1)
            except Exception as e:
                logging.warning(f"[{self.task_id}] Error leyendo teléfonos de CSV previo: {e}")

    def _save_checkpoint(self):
        """Persiste el estado actual para permitir reanudar si se interrumpe."""
        try:
            state_data = {
                "completed_zones": list(self.completed_zones),
                "seen_phones": list(self.seen_phones),
                "comercios_encontrados": self.comercios_encontrados,
                "consumo_usd": self.consumo_usd,
                "updated_at": datetime.now().isoformat()
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            logging.warning(f"[{self.task_id}] Error guardando checkpoint: {e}")

    def _ensure_csv_headers(self):
        """Crea el CSV con sus encabezados si no existe."""
        if not os.path.exists(self.output_file) or os.path.getsize(self.output_file) == 0:
            with open(self.output_file, mode="w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(['Nombre del Local', 'Teléfono', 'Dirección', 'Sitio Web Detectado', 'Zona'])

    def run(self):
        """
        Ejecuta el ciclo de barrido recorriendo cada una de las zonas configuradas.
        """
        self.status = "running"
        self.started_at = datetime.now().isoformat()
        self.stop_requested.clear()

        if not self.api_key:
            self.status = "error"
            self.error_message = "No se configuró GOOGLE_MAPS_API_KEY"
            logging.error(f"[{self.task_id}] {self.error_message}")
            return self.get_status()

        zonas = obtener_zonas_por_clave(self.zona_clave)
        if not zonas:
            self.status = "error"
            self.error_message = f"No se encontraron zonas para la clave '{self.zona_clave}'"
            logging.error(f"[{self.task_id}] {self.error_message}")
            return self.get_status()

        self.total_zonas = len(zonas)
        self._ensure_csv_headers()
        self._load_checkpoint()

        logging.info(f"[{self.task_id}] Iniciando barrido: Rubro='{self.rubro}', Zonas={self.total_zonas}, Max={self.max_comercios}")

        try:
            for idx, zona in enumerate(zonas, start=1):
                if self.stop_requested.is_set():
                    self.status = "stopped"
                    logging.info(f"[{self.task_id}] Barrido detenido a petición del usuario.")
                    break

                if self.comercios_encontrados >= self.max_comercios:
                    self.status = "completed"
                    logging.info(f"[{self.task_id}] Alcanzado límite de comercios ({self.max_comercios}). Deteniendo.")
                    break

                if zona in self.completed_zones:
                    logging.info(f"[{self.task_id}] [{idx}/{self.total_zonas}] Omitiendo zona ya completada: {zona}")
                    self.indice_zona = idx
                    continue

                self.zona_actual = zona
                self.indice_zona = idx

                self._procesar_zona(zona)
                self.completed_zones.add(zona)
                self._save_checkpoint()

            if self.status == "running":
                self.status = "completed"

        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            logging.error(f"[{self.task_id}] Error durante el barrido: {e}")

        finally:
            self.completed_at = datetime.now().isoformat()
            self._save_checkpoint()
            logging.info(f"[{self.task_id}] Finalizado con estado: {self.status}. Total comercios: {self.comercios_encontrados}. Consumo: ${self.consumo_usd:.4f} USD.")

        return self.get_status()

    def _procesar_zona(self, zona: str):
        """Consulta Google Places para una zona dada y guarda resultados respetando filtros y límites."""
        query_text = f"{self.rubro} en {zona}"
        search_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={requests.utils.quote(query_text)}&key={self.api_key}"

        try:
            res = requests.get(search_url, timeout=10)
            self.consumo_usd += COST_PER_TEXT_SEARCH
            res_json = res.json()

            if res_json.get("status") not in ["OK", "ZERO_RESULTS"]:
                logging.warning(f"[{self.task_id}] Error Places en zona '{zona}': {res_json.get('status')}")
                return

            results = res_json.get("results", [])

            # Si hay next_page_token y aún no alcanzamos el cupo, intentar 2da página
            next_token = res_json.get("next_page_token")
            if next_token and not self.stop_requested.is_set() and (self.comercios_encontrados + len(results) < self.max_comercios):
                time.sleep(2)  # Requerido por Google antes de usar next_page_token
                page2_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?pagetoken={next_token}&key={self.api_key}"
                res2 = requests.get(page2_url, timeout=10)
                self.consumo_usd += COST_PER_TEXT_SEARCH
                res2_json = res2.json()
                if res2_json.get("status") == "OK":
                    results.extend(res2_json.get("results", []))

            # Procesar detalles de cada local encontrado
            for place in results:
                if self.stop_requested.is_set():
                    break
                if self.comercios_encontrados >= self.max_comercios:
                    break

                place_id = place.get("place_id")
                if not place_id:
                    continue

                det_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_phone_number,formatted_address,website&key={self.api_key}"
                det_res = requests.get(det_url, timeout=10)
                self.consumo_usd += COST_PER_PLACE_DETAILS
                det_json = det_res.json()

                if det_json.get("status") == "OK":
                    d = det_json.get("result", {})
                    name = str(d.get("name", "")).strip()
                    raw_phone = str(d.get("formatted_phone_number", "")).strip()
                    address = str(d.get("formatted_address", "")).strip()
                    raw_website = str(d.get("website", "")).strip()

                    if not raw_phone:
                        continue

                    # Deduplicación de teléfono
                    phone_norm = normalizar_telefono(raw_phone)
                    if not phone_norm or phone_norm in self.seen_phones:
                        continue

                    # Filtro inteligente de presencia web
                    tipo_web = None
                    if not raw_website:
                        tipo_web = "Sin web"
                    elif any(dom in raw_website.lower() for dom in SOCIAL_DOMAINS):
                        tipo_web = f"Redes ({raw_website})"
                    else:
                        if not self.solo_sin_web:
                            tipo_web = raw_website

                    # Si pasó el filtro web, registrar y persistir fila
                    if tipo_web:
                        self.seen_phones.add(phone_norm)
                        self.comercios_encontrados += 1
                        fila = [name, raw_phone, address, tipo_web, zona]
                        self._append_row(fila)

        except Exception as e:
            logging.warning(f"[{self.task_id}] Excepción al procesar zona '{zona}': {e}")

    def _append_row(self, row: List[str]):
        """Escribe una fila al CSV de salida de forma atómica y segura."""
        with open(self.output_file, mode="a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)


# ==============================================================================
# Gestor Singleton de Tareas en Segundo Plano para Flask
# ==============================================================================
_active_task_lock = threading.Lock()
_active_task: Optional[BulkMapsScraper] = None

def get_current_task() -> Optional[BulkMapsScraper]:
    """Retorna la tarea de barrido activa o la última ejecutada."""
    with _active_task_lock:
        return _active_task

def start_scraper_task(
    rubro: str,
    zona_clave: str,
    max_comercios: int = 1000,
    solo_sin_web: bool = True,
    resume: bool = False
) -> Dict:
    """Inicia una nueva tarea de barrido masivo en segundo plano."""
    global _active_task
    with _active_task_lock:
        if _active_task and _active_task.status == "running":
            return {
                "status": "already_running",
                "error": "Ya hay un barrido en ejecución actualmente.",
                "task_id": _active_task.task_id
            }

        task = BulkMapsScraper(
            rubro=rubro,
            zona_clave=zona_clave,
            max_comercios=max_comercios,
            solo_sin_web=solo_sin_web,
            resume=resume
        )
        _active_task = task

        thread = threading.Thread(target=task.run, daemon=True, name=f"BulkScraper-{task.task_id}")
        thread.start()

        return {
            "status": "started",
            "task_id": task.task_id,
            "rubro": task.rubro,
            "zona_clave": task.zona_clave,
            "max_comercios": task.max_comercios,
            "csv_filename": task.csv_filename
        }

def stop_scraper_task() -> Dict:
    """Detiene la tarea activa si existe."""
    with _active_task_lock:
        if not _active_task or _active_task.status != "running":
            return {
                "status": "not_running",
                "message": "No hay ningún barrido ejecutándose en este momento."
            }
        _active_task.request_stop()
        return {
            "status": "stopping",
            "task_id": _active_task.task_id,
            "message": "Se solicitó la detención del barrido. Se completará el punto actual."
        }

def get_scraper_status() -> Dict:
    """Retorna el estado de la tarea actual o idle."""
    with _active_task_lock:
        if not _active_task:
            return {
                "status": "idle",
                "message": "Sin barridos iniciados recientemente."
            }
        return _active_task.get_status()


# ==============================================================================
# CLI Entrypoint
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Barrido Masivo de Prospectos en Google Maps")
    parser.add_argument("--rubro", required=True, help="Rubro o actividad comercial (ej: 'peluquería', 'depilación')")
    parser.add_argument("--zona", default="caba", help="Clave de zona del catálogo (ej: caba, gba, cordoba, argentina)")
    parser.add_argument("--max", type=int, default=1000, help="Límite máximo de comercios a recolectar (default: 1000)")
    parser.add_argument("--todos", action="store_true", help="Incluir comercios aunque ya tengan sitio web propio")
    parser.add_argument("--resume", action="store_true", help="Reanudar desde checkpoint previo si existe")
    parser.add_argument("--output", help="Ruta de archivo CSV de salida personalizada")
    args = parser.parse_args()

    scraper = BulkMapsScraper(
        rubro=args.rubro,
        zona_clave=args.zona,
        max_comercios=args.max,
        solo_sin_web=not args.todos,
        output_file=args.output,
        resume=args.resume
    )

    print(f"\n🚀 Iniciando barrido CLI para '{args.rubro}' en zona '{args.zona}'...")
    print(f"📁 Salida: {scraper.output_file}")
    res = scraper.run()
    print(f"\n🏁 Barrido finalizado con estado: {res['status']}")
    print(f"📊 Comercios encontrados: {res['comercios_encontrados']}")
    print(f"💰 Consumo estimado: ${res['consumo_usd']:.4f} USD\n")

if __name__ == "__main__":
    main()
