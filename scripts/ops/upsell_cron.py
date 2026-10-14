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
    from sender import send_whatsapp_message
except ImportError as e:
    logging.error(f"Error importando dependencias: {e}")
    sys.exit(1)

def init_db():
    db_path = os.path.join(os.getcwd(), 'messages.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS upsell_logs (
            website_id TEXT PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    return db_path

def check_has_been_sent(db_path, website_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT 1 FROM upsell_logs WHERE website_id = ?", (website_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def mark_as_sent(db_path, website_id):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("INSERT INTO upsell_logs (website_id) VALUES (?)", (website_id,))
    conn.commit()
    conn.close()

def run_upsell_check():
    db_path = init_db()
    logging.info("Iniciando revisión de Upselling (30 días de antigüedad en plan gratis)...")
    
    try:
        # Obtenemos las webs que están publicadas pero no tienen dominio propio (siguen gratis)
        # Hacemos un JOIN con clients para tener el teléfono
        res = supabase.table("websites").select("id, created_at, clients(phone, name)").eq("status", "published").is_("custom_domain", "null").execute()
        
        if not res.data:
            logging.info("No hay webs gratuitas publicadas en este momento.")
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        count_sent = 0
        
        for web in res.data:
            web_id = web.get("id")
            client_data = web.get("clients")
            if not client_data: continue
            
            phone = client_data.get("phone")
            nombre = client_data.get("name", "Hola")
            if not phone: continue
            
            # Parsing created_at (ej: "2024-09-08T12:00:00+00:00")
            created_at_str = web.get("created_at")
            if not created_at_str: continue
            
            try:
                # Usamos fromisoformat que parsea el timezone. Si falla, asumimos formato Z
                if created_at_str.endswith('Z'):
                    created_at_str = created_at_str[:-1] + '+00:00'
                created_at = datetime.datetime.fromisoformat(created_at_str)
            except Exception as e:
                logging.error(f"Error parseando fecha para web {web_id}: {e}")
                continue
            
            days_active = (now - created_at).days
            
            if days_active >= 30:
                if not check_has_been_sent(db_path, web_id):
                    # Enviar mensaje
                    msg = f"¡Hola {nombre}! Hace un mes que tu web gratuita está activa. 🚀\n\n¿Sabías que podés darle una imagen 100% profesional a tu negocio con un dominio .com.ar propio? (ej: tunegocio.com.ar).\n\nEsto da muchísima más confianza a tus clientes cuando buscan tus servicios.\n\nRespondé *QUIERO MI DOMINIO* para ver los planes de actualización."
                    
                    logging.info(f"Enviando upsell a {phone} (web: {web_id}) - {days_active} días activa.")
                    
                    try:
                        send_whatsapp_message(phone, msg)
                        mark_as_sent(db_path, web_id)
                        count_sent += 1
                    except Exception as e:
                        logging.error(f"Error enviando mensaje a {phone}: {e}")
        
        logging.info(f"Revisión terminada. {count_sent} mensajes de upsell enviados hoy.")
        
    except Exception as e:
        logging.error(f"Error durante el proceso de upsell: {e}")

if __name__ == "__main__":
    run_upsell_check()
