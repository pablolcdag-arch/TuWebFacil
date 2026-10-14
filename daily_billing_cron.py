import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from sender import send_whatsapp_message

# Configuración
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
ADMIN_PHONE = os.getenv("BOT_PHONE_NUMBER")

if not supabase_url or not supabase_key:
    logging.error("Credenciales de Supabase no encontradas.")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

def run_billing_check():
    logging.info("Iniciando revisión diaria de suscripciones y mora...")
    
    # Obtenemos suscripciones con pago fallido
    res = supabase.table("subscriptions").select("*, clients(id, name, phone)").eq("status", "payment_failed").execute()
    
    suspendidas_hoy = []
    
    if res.data:
        for sub in res.data:
            client = sub.get("clients", {})
            client_id = sub["client_id"]
            
            # Buscamos cuándo fue el último pago fallido en la tabla payments
            pay_res = supabase.table("payments").select("*").eq("subscription_id", sub["id"]).eq("status", "rejected").order("created_at", desc=True).limit(1).execute()
            
            if pay_res.data:
                failed_date_str = pay_res.data[0].get("created_at")
                if failed_date_str:
                    failed_date = datetime.fromisoformat(failed_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    ahora = datetime.utcnow()
                    
                    # Si pasaron más de 72 horas (3 días)
                    if (ahora - failed_date).total_seconds() > (72 * 3600):
                        # Suspender la web
                        web_res = supabase.table("websites").select("*").eq("client_id", client_id).execute()
                        if web_res.data:
                            for web in web_res.data:
                                if web.get("status") != "maintenance":
                                    supabase.table("websites").update({"status": "maintenance"}).eq("id", web["id"]).execute()
                                    suspendidas_hoy.append(f"{client.get('name', 'Cliente')} ({web.get('subdomain', 'N/A')})")
                                    logging.info(f"Web suspendida por mora > 72hs: {web.get('subdomain')}")

    # Enviar resumen al Admin
    if ADMIN_PHONE and suspendidas_hoy:
        msg = "🤖 *Reporte Diario TuWebFacil*\n\nHoy se suspendieron las siguientes webs por falta de pago (>72hs):\n\n"
        for s in suspendidas_hoy:
            msg += f"❌ {s}\n"
        
        send_whatsapp_message(ADMIN_PHONE, msg)
        logging.info("Resumen enviado al admin.")
    else:
        logging.info("No hubo webs para suspender hoy.")

if __name__ == "__main__":
    run_billing_check()
