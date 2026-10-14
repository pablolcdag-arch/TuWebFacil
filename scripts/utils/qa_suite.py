import requests
import time
import json
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno locales
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
if not supabase_url or not supabase_key:
    print("❌ Error: No se encontraron SUPABASE_URL y SUPABASE_KEY en .env")
    sys.exit(1)

supabase = create_client(supabase_url, supabase_key)

BASE_URL = "https://tuweblista.com.ar"
WEBHOOK_URL = f"{BASE_URL}/webhook"
FORM_URL = f"{BASE_URL}/process_form"

# Constantes de prueba
QA_PHONE = "54911999900QA"
QA_NAME = "Bot de QA Automatizado"
QA_BUSINESS = "Negocio de Prueba QA"

def teardown():
    """Limpia la base de datos de cualquier registro del QA."""
    print("\n🧹 [TEARDOWN] Limpiando datos de prueba en la base de datos...")
    
    # 1. Buscar cliente
    res_client = supabase.table("clients").select("id").eq("phone", QA_PHONE).execute()
    if not res_client.data:
        print("ℹ️ No se encontraron clientes de prueba para borrar.")
        return
    
    client_id = res_client.data[0]["id"]
    
    # 2. Buscar webs del cliente
    res_webs = supabase.table("websites").select("id").eq("client_id", client_id).execute()
    for web in res_webs.data:
        web_id = web["id"]
        # Borrar contents
        supabase.table("website_content").delete().eq("website_id", web_id).execute()
        # Borrar payments
        supabase.table("payments").delete().eq("client_id", client_id).execute()
        # Borrar web
        supabase.table("websites").delete().eq("id", web_id).execute()
        
    # 3. Borrar cliente
    supabase.table("clients").delete().eq("id", client_id).execute()
    print("✅ [TEARDOWN] Base de datos limpia.")

def send_wa_message(text):
    """Simula el envío de un mensaje de WhatsApp al webhook de producción."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": QA_PHONE, "profile": {"name": QA_NAME}}],
                    "messages": [{"from": QA_PHONE, "type": "text", "text": {"body": text}}]
                }
            }]
        }]
    }
    res = requests.post(WEBHOOK_URL, json=payload, verify=False)
    if res.status_code != 200:
        raise Exception(f"Webhook falló con status {res.status_code}")
    time.sleep(4) # Esperar a que el bot procese asíncronamente

def run_tests():
    print("==================================================")
    print("🧪 INICIANDO SUITE DE QA AUTOMATIZADA END-TO-END")
    print("==================================================")
    
    try:
        # Asegurarnos de estar limpios antes de empezar
        teardown()
        
        # --- TEST 1: ONBOARDING / CREACIÓN DE WEB ---
        print("\n▶️ TEST 1: Creación de Web vía Formulario")
        form_data = {
            "phone": QA_PHONE,
            "business_type": QA_BUSINESS,
            "zona": "Internet",
            "horarios": "24/7",
            "plan_type": "basico",
            "titulo": "Sitio de Pruebas Automatizadas"
        }
        res_form = requests.post(FORM_URL, json=form_data, verify=False)
        assert res_form.status_code == 200, "El formulario no devolvió 200 OK"
        data = res_form.json()
        assert data.get("success") == True, "La respuesta del form no indica éxito"
        slug = data.get("slug")
        assert slug is not None, "No se generó el slug"
        print(f"✅ Web creada exitosamente: /{slug}")
        
        # Verificar en base de datos
        res_client = supabase.table("clients").select("*").eq("phone", QA_PHONE).execute()
        assert len(res_client.data) == 1, "El cliente no se guardó en Supabase"
        
        # --- TEST 2: INTERACCIÓN BOT (Modificar texto) ---
        print("\n▶️ TEST 2: Edición de textos vía WhatsApp")
        send_wa_message("cancelar") # Resetear estado del bot a IDLE
        send_wa_message("quiero confirmar mi web") # Despierta al bot -> IDLE a MAIN_MENU
        send_wa_message("main_editar") # MAIN_EDITAR (Editar Web)
        send_wa_message("edit_titulo") # EDIT_TITULO (Editar Título)
        
        nuevo_titulo = "Título Editado por QA Automático"
        send_wa_message(nuevo_titulo)
        
        # Verificar en base de datos
        res_webs = supabase.table("websites").select("id").eq("subdomain", slug).execute()
        web_id = res_webs.data[0]["id"]
        res_content = supabase.table("website_content").select("content, version").eq("website_id", web_id).eq("is_current", True).execute()
        
        content_json = res_content.data[0]["content"]
        if isinstance(content_json, str):
            content_json = json.loads(content_json)
            
        assert content_json.get("titulo_web") == nuevo_titulo, f"El título no se actualizó. Esperado: {nuevo_titulo}, Obtenido: {content_json.get('titulo_web')}"
        print("✅ Edición de texto por WhatsApp verificada exitosamente.")
        
        # TODO: Add image simulation if possible (requires uploading media via form-data or simulating WA media payload)
        
        print("\n🎉 TODOS LOS TESTS PASARON EXITOSAMENTE 🎉")
        
    except AssertionError as e:
        print(f"\n❌ [FALLA DE TEST] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ [ERROR INESPERADO] {e}")
        sys.exit(1)
    finally:
        # Siempre limpiar al terminar, incluso si falló
        teardown()

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    run_tests()
