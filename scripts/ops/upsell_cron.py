import os
import sys
import sqlite3
import time
import datetime
import logging
from dotenv import load_dotenv

# Asegurar que estamos en el root del proyecto para cargar las env y paths
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] UPSELL_CRON: %(message)s",
    handlers=[
        logging.FileHandler("upsell_cron.log"),
        logging.StreamHandler()
    ]
)

# Agregar el directorio raíz al path para importar app y sender
sys.path.append(os.getcwd())
try:
    from app import supabase
    from sender import send_whatsapp_message, send_whatsapp_buttons
except ImportError as e:
    logging.error(f"Error importando dependencias: {e}")
    sys.exit(1)

def init_db():
    db_path = os.path.join(os.getcwd(), 'messages.db')
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS upsell_logs (
                website_id TEXT PRIMARY KEY,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    finally:
        if conn:
            conn.close()
    return db_path

def check_has_been_sent(db_path, website_id):
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT 1 FROM upsell_logs WHERE website_id = ?", (website_id,))
        res = c.fetchone()
        return res is not None
    finally:
        if conn:
            conn.close()

def mark_as_sent(db_path, website_id):
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO upsell_logs (website_id) VALUES (?)", (website_id,))
        conn.commit()
    finally:
        if conn:
            conn.close()

def run_upsell_check():
    db_path = init_db()
    logging.info("Iniciando revisión de Upselling (Día 27 de prueba gratuita)...")
    
    try:
        if not supabase:
            logging.error("Supabase client no está disponible.")
            return

        # Obtenemos las webs publicadas sin dominio propio (plan gratis / trial)
        res = supabase.table("websites").select("id, created_at, client_id, clients(id, phone, name)").eq("status", "published").is_("custom_domain", "null").execute()
        
        if not res.data:
            logging.info("No hay webs gratuitas publicadas en este momento.")
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        count_sent = 0
        
        for web in res.data:
            web_id = web.get("id")
            client_data = web.get("clients")
            if not client_data:
                continue
            
            # Obtener datos del cliente tolerando estructura de Supabase (dict o list)
            if isinstance(client_data, list):
                client_dict = client_data[0] if client_data else {}
            else:
                client_dict = client_data
                
            phone = client_dict.get("phone")
            nombre = client_dict.get("name", "Hola")
            client_id = web.get("client_id") or client_dict.get("id")
            
            if not phone:
                continue
            
            # Parsing created_at (ej: "2024-09-08T12:00:00+00:00")
            created_at_str = web.get("created_at")
            if not created_at_str:
                continue
            
            try:
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str[:-1] + '+00:00'
                created_at = datetime.datetime.fromisoformat(created_at_str)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=datetime.timezone.utc)
            except Exception as e:
                logging.error(f"Error parseando fecha para web {web_id}: {e}")
                continue
            
            days_active = (now - created_at).days
            
            if days_active >= 27:
                if check_has_been_sent(db_path, web_id):
                    continue

                # Chequear que el cliente no tenga ya una suscripción activa paga
                if client_id:
                    try:
                        sub_res = supabase.table("subscriptions").select("plan_type, status").eq("client_id", client_id).eq("status", "active").execute()
                        if sub_res and sub_res.data:
                            has_paid_sub = any(s.get("plan_type") != "gratis" for s in sub_res.data)
                            if has_paid_sub:
                                logging.info(f"Cliente {client_id} ya posee suscripción activa paga. Omitiendo aviso Día 27.")
                                continue
                    except Exception as e:
                        logging.warning(f"Error al verificar suscripciones de cliente {client_id}: {e}")

                # Mensaje interactivo del Día 27
                msg = (
                    f"👋 ¡Hola {nombre}! En 3 días finalizan tus 30 días de prueba gratuita en TuWebLista. 🎉\n\n"
                    "Tu web ya está online y lista para seguir recibiendo clientes. Para mantenerla activa el mes que viene, tenés 2 opciones transparentes:\n\n"
                    "🟢 OPCIÓN 1: Mantener tu web con subdominio\n"
                    "💰 Solo $2.000 al mes (menos que un alfajor 🍫).\n\n"
                    "💎 OPCIÓN 2: Activar tu Dominio Propio (.com.ar)\n"
                    "💰 Costo anual oficial NIC.ar: $8.500.\n"
                    "💰 Abono mensual: $2.000 (Total hoy: $10.500).\n"
                    "🎁 Toda la configuración técnica te la hacemos 100% BONIFICADA.\n\n"
                    "🔒 Recordá: Cero tarjetas ni débitos automáticos. Transferís al alias tuweblista solo si querés seguir."
                )

                buttons = [
                    {"id": "TRIAL_SUBDOMINIO", "title": "🟢 Subdominio $2.000"},
                    {"id": "TRIAL_DOMINIO", "title": "💎 Dominio Propio"}
                ]
                
                logging.info(f"Enviando aviso interactivo Día 27 a {phone} (web: {web_id}) - {days_active} días activa.")
                
                try:
                    sent = send_whatsapp_buttons(phone, msg, buttons)
                    if sent is not False:
                        mark_as_sent(db_path, web_id)
                        count_sent += 1
                except Exception as e:
                    logging.error(f"Error enviando mensaje interactivo a {phone}: {e}")
        
        logging.info(f"Revisión terminada. {count_sent} avisos de Día 27 enviados hoy.")
        
    except Exception as e:
        logging.error(f"Error durante el proceso de upsell Día 27: {e}")

if __name__ == "__main__":
    run_upsell_check()
