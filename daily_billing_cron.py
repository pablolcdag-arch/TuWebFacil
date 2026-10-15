import os
import json
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
from sender import send_whatsapp_message

# Configuración
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TUWEBLISTA_BILLING: %(message)s")
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
ADMIN_PHONE = os.getenv("ADMIN_PHONE") or os.getenv("BOT_PHONE_NUMBER") or "5491134710787"

supabase: Client = create_client(supabase_url, supabase_key) if (supabase_url and supabase_key) else None

def run_billing_check():
    logging.info("Iniciando revisión diaria de suscripciones, mora y vencimiento de trial (30 días)...")
    if not supabase:
        logging.error("Supabase client no configurado.")
        return []
    
    suspendidas_hoy = []
    ahora = datetime.utcnow()
    
    # 1. Obtenemos suscripciones con pago fallido (mora > 72hs)
    try:
        res = supabase.table("subscriptions").select("*, clients(id, name, phone)").eq("status", "payment_failed").execute()
        if res.data:
            for sub in res.data:
                client = sub.get("clients", {})
                if isinstance(client, list):
                    client = client[0] if client else {}
                client_id = sub["client_id"]
                
                # Buscamos cuándo fue el último pago fallido en la tabla payments
                pay_res = supabase.table("payments").select("*").eq("subscription_id", sub["id"]).eq("status", "rejected").order("created_at", desc=True).limit(1).execute()
                
                if pay_res.data:
                    failed_date_str = pay_res.data[0].get("created_at")
                    if failed_date_str:
                        if failed_date_str.endswith("Z"):
                            failed_date_str = failed_date_str[:-1] + "+00:00"
                        failed_date = datetime.fromisoformat(failed_date_str)
                        if failed_date.tzinfo is not None:
                            failed_date = failed_date.replace(tzinfo=None)
                        
                        # Si pasaron más de 72 horas (3 días)
                        if (ahora - failed_date).total_seconds() > (72 * 3600):
                            # Suspender la web
                            web_res = supabase.table("websites").select("*").eq("client_id", client_id).execute()
                            if web_res.data:
                                for web in web_res.data:
                                    if web.get("status") != "maintenance":
                                        supabase.table("websites").update({"status": "maintenance"}).eq("id", web["id"]).execute()
                                        nombre_cli = client.get('name', 'Cliente')
                                        subdomain = web.get('subdomain', 'N/A')
                                        suspendidas_hoy.append(f"{nombre_cli} ({subdomain}) [Mora pago fallido > 72hs]")
                                        logging.info(f"Web suspendida por mora > 72hs: {subdomain}")
    except Exception as e:
        logging.error(f"Error procesando pagos fallidos: {e}")

    # 2. Revisión de webs con trial vencido (>= 30 días sin suscripción activa paga)
    try:
        webs_res = supabase.table("websites").select("id, subdomain, created_at, client_id, status, clients(id, name, phone)").eq("status", "published").execute()
        if webs_res.data:
            for web in webs_res.data:
                web_id = web.get("id")
                client_id = web.get("client_id")
                created_at_str = web.get("created_at")
                if not created_at_str:
                    continue
                
                try:
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str[:-1] + '+00:00'
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at.tzinfo is not None:
                        created_at = created_at.replace(tzinfo=None)
                except Exception as e:
                    logging.error(f"Error parseando created_at de web {web_id}: {e}")
                    continue
                
                days_active = (ahora - created_at).days
                if days_active >= 30:
                    # Chequear si tiene suscripción activa paga
                    has_paid_sub = False
                    if client_id:
                        try:
                            sub_res = supabase.table("subscriptions").select("plan_type, status").eq("client_id", client_id).eq("status", "active").execute()
                            if sub_res and sub_res.data:
                                has_paid_sub = any(s.get("plan_type") != "gratis" for s in sub_res.data)
                        except Exception as e:
                            logging.warning(f"Error verificando suscripciones para cliente {client_id}: {e}")
                    
                    if not has_paid_sub:
                        supabase.table("websites").update({"status": "maintenance"}).eq("id", web_id).execute()
                        client_obj = web.get("clients") or {}
                        if isinstance(client_obj, list):
                            client_obj = client_obj[0] if client_obj else {}
                        client_name = client_obj.get("name", "Cliente")
                        subdomain = web.get("subdomain", "N/A")
                        suspendidas_hoy.append(f"{client_name} ({subdomain}) [Trial 30 días vencido]")
                        logging.info(f"Web pausada por trial vencido (>= 30 días): {subdomain}")
    except Exception as e:
        logging.error(f"Error procesando trial vencido: {e}")

    # 3. Enviar resumen al Admin
    if ADMIN_PHONE and suspendidas_hoy:
        msg = "🤖 *Reporte Diario TuWebLista*\n\nHoy se pausaron las siguientes webs por falta de pago o trial vencido:\n\n"
        for s in suspendidas_hoy:
            msg += f"⏸️ {s}\n"
        
        try:
            send_whatsapp_message(ADMIN_PHONE, msg)
            logging.info("Resumen de webs pausadas enviado al admin.")
        except Exception as e:
            logging.error(f"Error enviando reporte a admin: {e}")
    else:
        logging.info("No hubo webs para pausar hoy.")
        
    return suspendidas_hoy

if __name__ == "__main__":
    run_billing_check()
