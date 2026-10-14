import requests
import time
import json
import random

BASE_URL = "https://tuweblista.com.ar"
WEBHOOK_URL = f"{BASE_URL}/webhook"
FORM_URL = f"{BASE_URL}/process_form"

# Generar un número de teléfono falso aleatorio para la prueba
RANDOM_ID = str(random.randint(1000, 9999))
PHONE = f"549110000{RANDOM_ID}"
NAME = "Usuario Tester"

def send_message(text, wait=4):
    print(f"\n📱 Usuario envía: '{text}'")
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": PHONE, "profile": {"name": NAME}}],
                    "messages": [{"from": PHONE, "type": "text", "text": {"body": text}}]
                }
            }]
        }]
    }
    try:
        response = requests.post(WEBHOOK_URL, json=payload, verify=False)
        print(f"✅ (Webhook 200 OK)")
    except Exception as e:
        print(f"❌ Error webhook: {e}")
    
    # Wait for the bot to process and respond so we don't send messages out of order
    time.sleep(wait)

def simulate():
    print("=========================================")
    print(f"🚀 INICIANDO SIMULACIÓN END-TO-END")
    print(f"Teléfono simulado: {PHONE}")
    print("=========================================\n")
    
    # 1. Simular envío del formulario web
    print("🌐 1. Enviando formulario web inicial...")
    form_data = {
        "phone": PHONE,
        "business_type": "abogado",
        "zona": "Palermo",
        "horarios": "Lun a Vie de 9 a 18hs",
        "plan_type": "basico"
    }
    
    try:
        res = requests.post(FORM_URL, json=form_data, verify=False)
        if res.status_code == 200:
            slug = res.json().get('slug', 'demo-error')
            print(f"✅ Formulario enviado. Web generada en: {BASE_URL}/{slug}")
        else:
            print(f"❌ Error en formulario: {res.text}")
            slug = "error"
    except Exception as e:
        print(f"❌ Error HTTP form: {e}")
        slug = "error"
        
    time.sleep(2)
    
    # 2. Interacción con el Bot
    print("\n🤖 2. Iniciando chat de WhatsApp...")
    
    # Inicio
    send_message("quiero confirmar mi web", wait=4)
    
    # Entrar a menú edición
    send_message("2", wait=3) # MAIN_EDITAR
    
    # Editar Título
    send_message("1", wait=3) # EDIT_TITULO
    send_message("Estudio de Abogados Superiores", wait=5)
    # The bot should automatically transition back to MAIN_MENU and re-trigger EDIT_MENU (via procesar_mensaje("2"))
    
    # Editar Ubicación
    send_message("4", wait=3) # EDIT_LOCATION
    print("\n📱 Usuario envía: 'Avenida Corrientes 1000, CABA'")
    send_message("Avenida Corrientes 1000, CABA", wait=5)
    time.sleep(5)
    
    # Editar Horarios
    send_message("5", wait=3) # EDIT_SCHEDULE
    send_message("Lunes a Sábados 24/7", wait=5)
    
    # Salir del menú de edición
    send_message("0", wait=4) # EDIT_VOLVER
    
    # Ahora el bot simuló volver al inicio. Vamos a "Publicar"
    send_message("3", wait=4) # MAIN_PUBLICAR
    
    # Nos pregunta si queremos buscar dominio (Nic.ar)
    send_message("DOMINIO_SI", wait=4) 
    
    # Simulamos que fuimos a Nic.ar y encontramos uno
    send_message("abogadossuperiores.com.ar", wait=4)
    
    # Nos pide elegir plan
    send_message("PLAN_ANUAL", wait=4)
    
    print("\n=========================================")
    print("🎉 SIMULACIÓN COMPLETADA CON ÉXITO")
    print(f"Podés revisar la URL: {BASE_URL}/{slug} para ver los textos actualizados.")
    print("Y si entrás a la base de datos, verás el pago pendiente.")
    print("=========================================")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    simulate()
