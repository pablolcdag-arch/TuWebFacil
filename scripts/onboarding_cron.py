import os
import sys
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone

# Asegurar que importemos sender correctamente
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sender import send_whatsapp_message

load_dotenv()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

def send_onboarding_messages():
    if not supabase:
        print("No supabase connection.")
        return
        
    now = datetime.now(timezone.utc)
    
    try:
        res = supabase.table("clients").select("id, phone, created_at").execute()
        
        for client in res.data:
            created_at_str = client.get("created_at")
            if not created_at_str: continue
            
            try:
                created_dt = datetime.strptime(created_at_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except:
                continue
                
            days_since = (now - created_dt).days
            phone = client["phone"]
            
            # Mandamos mensaje el Día 3
            if days_since == 3:
                msg = ("¡Hola! 👋 Vi que creaste tu web gratis hace unos días en *TuWebFacil*.\n\n"
                       "Recordá que podés pedirme que le cambie el título, los colores o actualice tus datos directamente por acá. "
                       "¡Aprovechá tus 30 ediciones gratuitas de bienvenida para dejarla impecable! ✨\n\n"
                       "Escribí la palabra *menu* para empezar.")
                print(f"Mandando onboarding Día 3 a {phone}")
                send_whatsapp_message(phone, msg)
                
            # Mandamos mensaje el Día 10
            elif days_since == 10:
                msg = ("¡Hola de nuevo! 🚀 Tu periodo de gracia de 15 días en *TuWebFacil* está por terminar.\n\n"
                       "A partir de la semana que viene tendrás un límite de 10 cambios por mes en tu plan gratuito. "
                       "Si todavía querés hacer modificaciones grandes a tu web, ¡este es el momento!\n\n"
                       "Escribí *menu* si querés editar algo, o elegir tu Plan Premium para tener Dominio propio.")
                print(f"Mandando onboarding Día 10 a {phone}")
                send_whatsapp_message(phone, msg)
                
    except Exception as e:
        print(f"Error corriendo onboarding_cron: {e}")

if __name__ == "__main__":
    print("Ejecutando Cron de Onboarding...")
    send_onboarding_messages()
    print("Cron finalizado.")
