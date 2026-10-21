from flask import Flask, request
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from sender import send_whatsapp_message  # Importamos tu nuevo músculo
import bot_engine  # <-- Nuestro nuevo Bot Nivel Dios

load_dotenv()
app = Flask(__name__)

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
            contacto_obj_list = data['entry'][0]['changes'][0]['value'].get('contacts', [])
            contacto_obj = contacto_obj_list[0] if contacto_obj_list else {}
            
            wa_id = contacto_obj.get('wa_id', mensaje_obj.get('from', ''))
            nombre = contacto_obj.get('profile', {}).get('name', 'Usuario')
            
            msg_type = mensaje_obj.get('type', 'text')
            media_id = None
            
            if msg_type == 'text':
                texto = mensaje_obj['text']['body']
            elif msg_type == 'image':
                texto = "" # Para audios, imagenes, etc.
                media_id = mensaje_obj.get('image', {}).get('id')
            elif msg_type == 'document':
                doc_obj = mensaje_obj.get('document', {})
                media_id = doc_obj.get('id')
                texto = doc_obj.get('filename', '')
            elif msg_type == 'interactive':
                inter_obj = mensaje_obj.get('interactive', {})
                if inter_obj.get('type') == 'button_reply':
                    b_reply = inter_obj.get('button_reply', {})
                    texto = b_reply.get('id') or b_reply.get('title', '')
                elif inter_obj.get('type') == 'list_reply':
                    l_reply = inter_obj.get('list_reply', {})
                    texto = l_reply.get('id') or l_reply.get('title', '')
                else:
                    texto = ""
            elif msg_type == 'button':
                btn_obj = mensaje_obj.get('button', {})
                texto = btn_obj.get('text') or btn_obj.get('payload', '')
            else:
                texto = ""
                
            # --- LÓGICA DE DETECCIÓN DE INSTAGRAM ---
            if "instagram.com" in texto.lower() and msg_type == 'text':
                print(f"📸 Detectado link de Instagram de {nombre}")
                respuesta = f"¡Excelente {nombre}! Ya recibí tu Instagram. Voy a analizar tu perfil y en unos minutos te enviaré un link con un ejemplo de tu nueva web profesional. Mientras tanto, aquí puedes ver algunos ejemplos: [LINK_EJEMPLOS]"
                send_whatsapp_message(wa_id, respuesta)
            else:
                # Pasamos el mensaje a nuestro Bot Engine en Python usando un hilo en segundo plano
                import threading
                threading.Thread(target=bot_engine.procesar_mensaje, args=(wa_id, texto, nombre, msg_type, media_id)).start()
            
    except Exception as e:
        print(f"⚠️ Evento recibido: {e}")
        
    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    app.run(port=5002, debug=True)