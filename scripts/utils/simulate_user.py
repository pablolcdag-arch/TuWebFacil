import requests
import time

URL = "https://tuweblista.com.ar/webhook"
PHONE = "5491134710787"
NAME = "Pablo Agent"

def send_message(text):
    print(f"🤖 Enviando al bot: '{text}'")
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
        response = requests.post(URL, json=payload, verify=False)
        print(f"✅ Respuesta del servidor: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    time.sleep(3) # Wait for bot to process and respond

def simulate():
    # 1. Iniciar conversación
    send_message("Confirmar mi web")
    
    # 2. Entrar a Editar Textos
    send_message("2") # MAIN_EDITAR
    
    # 3. Editar Título
    send_message("1") # EDIT_TITULO
    send_message("Estudio Jurídico Internacional Stiefel & Asociados")
    
    # 4. Volver a Editar Textos y Editar Subtítulo
    send_message("2") # MAIN_EDITAR
    send_message("2") # EDIT_SUBTITULO
    send_message("Más de 20 años de experiencia ganando casos imposibles para nuestros clientes.")
    
    # 5. Volver a Editar Textos y Editar Ubicación
    send_message("2") # MAIN_EDITAR
    send_message("3") # EDIT_LOCATION
    send_message("Avenida Corrientes 1234, Piso 5, CABA")
    
    print("🎉 ¡Simulación completada! El usuario puede refrescar la web para ver los cambios.")

if __name__ == "__main__":
    simulate()
