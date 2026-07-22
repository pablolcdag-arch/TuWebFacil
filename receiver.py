from flask import Flask, request
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from sender import send_whatsapp_message  # Importamos tu nuevo músculo

load_dotenv()
app = Flask(__name__)

URL_MAKE = "https://hook.us2.make.com/fjfjs5s09thyoo7m7b3vnt2u8bs6p60s"

@app.route('/', methods=['GET'])
def home():
    return "🚀 TuWebFacil Core Online", 200

@app.route('/webhook', methods=['GET'])
def verify():
    challenge = request.args.get("hub.challenge")
    if challenge:
        return str(challenge), 200
    return "Servidor activo - Esperando a Meta", 200

@app.route('/webhook', methods=['POST'])
def handle_messages():
    data = request.json
    try:
        if 'messages' in data['entry'][0]['changes'][0]['value']:
            mensaje_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
            contacto_obj = data['entry'][0]['changes'][0]['value']['contacts'][0]
            
            wa_id = contacto_obj['wa_id']
            nombre = contacto_obj['profile']['name']
            texto = mensaje_obj['text']['body']
            
            payload = {
                "wa_id": wa_id,
                "nombre": nombre,
                "mensaje": texto,
                "fecha": datetime.utcnow().isoformat()
            }

            # --- LÓGICA DE DETECCIÓN DE INSTAGRAM ---
            if "instagram.com" in texto.lower():
                print(f"📸 Detectado link de Instagram de {nombre}")
                # Respuesta automática inmediata desde Python
                respuesta = f"¡Excelente {nombre}! Ya recibí tu Instagram. Voy a analizar tu perfil y en unos minutos te enviaré un link con un ejemplo de tu nueva web profesional. Mientras tanto, aquí puedes ver algunos ejemplos: [LINK_EJEMPLOS]"
                send_whatsapp_message(wa_id, respuesta)
            
            # Enviamos a Make para el procesamiento largo (IA, Análisis, etc.)
            requests.post(URL_MAKE, json=payload, timeout=5)
            
    except Exception as e:
        print(f"⚠️ Evento recibido: {e}")
        
    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run(port=5001, debug=True)