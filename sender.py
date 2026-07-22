import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de Meta (Sacalos de tu Dashboard de Meta Developers)
ACCESS_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = "v19.0"

def send_whatsapp_message(to_number, message_text):
    """
    Envía un mensaje de texto simple a través de la API de WhatsApp Cloud.
    """
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ Mensaje enviado con éxito a {to_number}")
            return True
        else:
            print(f"❌ Error al enviar: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

# Prueba rápida (Descomentá para probar solo este archivo)
# if __name__ == "__main__":
#     send_whatsapp_message("TU_NUMERO_CON_CODIGO_PAIS", "¡Hola desde TuWebFacil!")