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

def send_whatsapp_image(to_number, image_url, caption=""):
    """
    Envía una imagen a través de la API de WhatsApp Cloud.
    """
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "image",
        "image": {
            "link": image_url
        }
    }
    if caption:
        payload["image"]["caption"] = caption
        
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ Imagen enviada con éxito a {to_number}")
            return True
        else:
            print(f"❌ Error al enviar imagen: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def download_whatsapp_media(media_id, save_path):
    """
    Descarga un archivo multimedia de WhatsApp usando su ID y lo guarda localmente.
    Devuelve True si tuvo éxito, False en caso contrario.
    """
    try:
        # Paso 1: Obtener la URL de la media
        url = f"https://graph.facebook.com/{VERSION}/{media_id}"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"❌ Error obteniendo URL de media: {res.text}")
            return False
            
        media_url = res.json().get("url")
        if not media_url:
            return False
            
        # Paso 2: Descargar el archivo binario
        res_file = requests.get(media_url, headers=headers)
        if res_file.status_code == 200:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(res_file.content)
            print(f"✅ Imagen descargada con éxito en {save_path}")
            return True
        else:
            print(f"❌ Error descargando archivo: {res_file.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error al descargar media: {e}")
        return False

def send_whatsapp_buttons(to_number, text, buttons):
    """
    Envía botones interactivos (máximo 3).
    buttons: lista de diccionarios [{"id": "btn_1", "title": "Opción 1"}, ...]
    """
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    formatted_buttons = []
    for btn in buttons:
        formatted_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn["id"][:256],
                "title": btn["title"][:20]
            }
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": text
            },
            "action": {
                "buttons": formatted_buttons
            }
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ Botones enviados con éxito a {to_number}")
            return True
        else:
            print(f"❌ Error al enviar botones: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def send_whatsapp_list(to_number, text, button_text, options, title=""):
    """
    Envía un menú desplegable (lista).
    options: lista de diccionarios [{"id": "opt_1", "title": "Opción 1", "description": "Opcional"}, ...]
    """
    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    rows = []
    for opt in options:
        row = {
            "id": opt["id"][:200],
            "title": opt["title"][:24]
        }
        if "description" in opt and opt["description"]:
            row["description"] = opt["description"][:72]
        rows.append(row)
        
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": text
            },
            "action": {
                "button": button_text[:20],
                "sections": [
                    {
                        "title": "Opciones disponibles",
                        "rows": rows
                    }
                ]
            }
        }
    }
    
    if title:
        payload["interactive"]["header"] = {
            "type": "text",
            "text": title[:60]
        }
        
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ Lista enviada con éxito a {to_number}")
            return True
        else:
            print(f"❌ Error al enviar lista: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False