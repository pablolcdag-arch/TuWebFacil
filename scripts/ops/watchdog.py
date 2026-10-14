import requests
import sys
import os
from dotenv import load_dotenv

load_dotenv()
from sender import send_whatsapp_message

ADMIN_PHONE = "5491134710787"  # El número del administrador (Pablo)
URL = "https://tuweblista.com.ar"

def check_server():
    try:
        response = requests.get(URL, timeout=10)
        if response.status_code >= 500:
            msg = f"🚨 *ALERTA GUARDIÁN* 🚨\n\nEl servidor de TuWebLista devolvió un error interno ({response.status_code}). ¡Revisalo!"
            send_whatsapp_message(ADMIN_PHONE, msg)
            print("Alerta enviada (Status 500+)")
        else:
            print(f"✅ Servidor OK ({response.status_code})")
    except requests.exceptions.RequestException as e:
        msg = f"🚨 *ALERTA GUARDIÁN CRÍTICA* 🚨\n\nTuWebLista está *COMPLETAMENTE CAÍDO* o no responde.\nError: {str(e)[:50]}"
        send_whatsapp_message(ADMIN_PHONE, msg)
        print("Alerta enviada (Caída total)")

if __name__ == "__main__":
    check_server()
