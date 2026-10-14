import os
import sys
import time
import requests
from dotenv import load_dotenv

# Add parent directory to path to import app config if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from supabase import create_client

load_dotenv()

# Configuration
BASE_URL = os.getenv("QA_TARGET_URL", "https://tuweblista.com.ar")
ADMIN_USER = "admin"
ADMIN_PASS = "webfacil2026"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Faltan las variables de entorno de Supabase.")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Variables globales para el teardown
QA_PHONE = "54911ADMIN00QA"
client_id = None
subscription_id = None
payment_id = None
message_id = None

def setup_test_data():
    global client_id, subscription_id, payment_id, message_id
    print("🧹 [SETUP] Preparando datos de prueba en la base de datos...")
    
    # 1. Crear Cliente
    cli_res = supabase.table("clients").upsert({
        "name": "Admin QA Test",
        "phone": QA_PHONE,
        "business_type": "Test Automático",
        "email": "adminqa@tuweblista.com.ar",
        "status": "active"
    }, on_conflict="phone").execute()
    client_id = cli_res.data[0]["id"]
    
    # 2. Crear Suscripción
    sub_res = supabase.table("subscriptions").insert({
        "client_id": client_id,
        "plan_type": "premium",
        "status": "pending",
        "price": 1000
    }).execute()
    subscription_id = sub_res.data[0]["id"]
    
    # 3. Crear Pago (Comprobante cargado)
    pay_res = supabase.table("payments").insert({
        "client_id": client_id,
        "amount": 1000,
        "currency": "ARS",
        "status": "uploaded",
        "payment_method": "/receipts/test_receipt.jpg"
    }).execute()
    payment_id = pay_res.data[0]["id"]
    
    print("✅ [SETUP] Datos de prueba creados.")

def send_wa_message(text):
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": QA_PHONE, "profile": {"name": "QA Test Admin"}}],
                    "messages": [{"from": QA_PHONE, "type": "text", "text": {"body": text}}]
                }
            }]
        }]
    }
    requests.post(f"{BASE_URL}/webhook", json=payload, verify=False)
    time.sleep(2)

def teardown():
    print("🧹 [TEARDOWN] Limpiando datos de prueba...")
    if client_id:
        supabase.table("whatsapp_interactions").delete().eq("client_id", client_id).execute()
        supabase.table("payments").delete().eq("client_id", client_id).execute()
        supabase.table("subscriptions").delete().eq("client_id", client_id).execute()
        supabase.table("clients").delete().eq("id", client_id).execute()
    print("✅ [TEARDOWN] Base de datos limpia.")

def run_admin_tests():
    print("==================================================")
    print("🧪 INICIANDO SUITE DE QA DASHBOARD ADMINISTRADOR")
    print("==================================================")
    
    session = requests.Session()
    
    try:
        setup_test_data()
        
        # --- TEST 1: LOGIN ---
        print("\n▶️ TEST 1: Login de Administrador")
        login_res = session.post(f"{BASE_URL}/admin/login", data={
            "password": ADMIN_PASS
        })
        assert login_res.status_code == 200, f"Error en login. Status: {login_res.status_code}"
        assert "Dashboard" in login_res.text or "Panel" in login_res.text or "logout" in login_res.text.lower(), "No se redireccionó al Dashboard correctamente."
        print("✅ Login exitoso.")
        
        # --- TEST 2: VERIFICAR PANEL ---
        print("\n▶️ TEST 2: Visualizar Panel")
        dash_res = session.get(f"{BASE_URL}/admin")
        assert dash_res.status_code == 200, "Error cargando dashboard."
        assert "QA Test" in dash_res.text or "Test Automático" in dash_res.text, "El cliente de prueba no aparece en el Dashboard."
        print("✅ Dashboard cargado y muestra datos de prueba.")
        
        # --- TEST 3: APROBAR PAGO ---
        print("\n▶️ TEST 3: Aprobar Comprobante")
        appr_res = session.get(f"{BASE_URL}/admin/approve/{payment_id}")
        assert appr_res.status_code == 200, f"Error al aprobar pago. Status: {appr_res.status_code}"
        
        # Verificar en DB que el pago se aprobó
        ver_pay = supabase.table("payments").select("status").eq("id", payment_id).execute()
        assert ver_pay.data[0]["status"] == "approved", "El estado del pago en BD no cambió a approved."
        
        # Verificar que la suscripción pasó a active
        ver_sub = supabase.table("subscriptions").select("status").eq("id", subscription_id).execute()
        assert ver_sub.data[0]["status"] == "active", "El estado de la suscripción en BD no cambió a active."
        print("✅ Pago aprobado exitosamente.")
        
        # --- TEST 4: CREAR MENSAJE SOPORTE VIA WEBHOOK ---
        print("\n▶️ TEST 4: Crear Mensaje de Soporte vía Webhook")
        send_wa_message("cancelar")
        send_wa_message("quiero confirmar mi web") # Despierta al bot
        send_wa_message("main_soporte") # MAIN_SOPORTE (Hablar con un humano)
        send_wa_message("Mensaje de prueba de QA automático")
        print("✅ Mensaje enviado al bot.")
        
        # --- TEST 5: RESPONDER SOPORTE DESDE DASHBOARD ---
        print("\n▶️ TEST 5: Responder a Mensaje de Soporte")
        import re
        dash_res = session.get(f"{BASE_URL}/admin")
        
        # Buscar el bloque del mensaje
        msg_id_match = None
        for block in dash_res.text.split('bg-slate-800/50 rounded-xl'):
            if QA_PHONE in block:
                m = re.search(r'action="/admin/reply_message/(\d+)"', block)
                if m:
                    msg_id_match = m.group(1)
                    break
                
        assert msg_id_match is not None, "No se encontró el mensaje de soporte en el Dashboard."
        msg_id = msg_id_match
        
        reply_res = session.post(f"{BASE_URL}/admin/reply_message/{msg_id}", data={
            "reply_text": "Esta es una respuesta automática del QA."
        })
        assert reply_res.status_code == 200, f"Error al responder mensaje. Status: {reply_res.status_code}"
        
        print("✅ Respuesta enviada exitosamente desde el dashboard.")
        
        print("\n🎉 TODOS LOS TESTS DEL DASHBOARD PASARON EXITOSAMENTE 🎉\n")
        
    except AssertionError as e:
        print(f"\n❌ [FALLA DE TEST] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [ERROR INESPERADO] {e}")
        sys.exit(1)
    finally:
        teardown()

if __name__ == "__main__":
    run_admin_tests()
