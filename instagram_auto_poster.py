import os
import random
import argparse
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
IG_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IG_USER_ID = os.getenv("INSTAGRAM_BUSINESS_ID")
BASE_URL = "https://tuweblista.com.ar/static/marketing_images"
LOCAL_IMG_DIR = "/var/www/tuwebfacil/static/marketing_images"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-flash-lite-latest")

def get_random_image():
    if not os.path.exists(LOCAL_IMG_DIR):
        print("Image directory not found.")
        return None
    images = [f for f in os.listdir(LOCAL_IMG_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
    if not images:
        print("No images found in directory.")
        return None
    img_name = random.choice(images)
    return f"{BASE_URL}/{img_name}"

def generate_caption(content_type):
    task_description = """Redactá el texto (caption) para UN POSTEO ESTÁTICO de Instagram. 
    REGLA DE ORO: Debe ser extremadamente CORTO, directo y con un gancho que llame la atención. Máximo 4 oraciones en total. La gente en redes no lee textos largos.
    Elegí al azar uno de los 4 pilares de venta para enfocar el mensaje de hoy.
    Usá emojis (sin abusar), incluí un CTA claro invitando a comentar la palabra "DEMO" o enviar un MD para probarlo, y agregá máximo 3 o 4 hashtags al final."""

    if content_type == 'reel':
        task_description = """Redactá el GUIÓN y CAPTION para UN REEL CORTO de Instagram (10 a 15 segundos).
        REGLA DE ORO: La atención de la gente es mínima, el video debe ser dinámico.
        El formato de tu respuesta DEBE ser el siguiente (respetá las partes):
        
        [GUIÓN DEL VIDEO]
        (Escribí lo que la persona debe decir o el texto que debe aparecer en pantalla, debe durar máximo 15 segundos leyendo rápido. Muy punchy).
        
        [CAPTION PARA EL POST]
        (Escribí un texto extremadamente CORTO para acompañar el video, máximo 2 o 3 oraciones, e invitando a comentar "DEMO" para probarlo).
        """

    prompt = f"""
    Sos el Community Manager y Copywriter Experto de "TuWebLista", un servicio argentino que permite a comerciantes, artesanos y profesionales crear una página web profesional y optimizada en 30 minutos, gestionando todo desde un bot de WhatsApp.

    Tu objetivo principal es redactar contenido persuasivo, dinámico y atractivo para redes sociales que convierta seguidores en clientes.

    **TU PÚBLICO OBJETIVO:**
    Comerciantes, artesanos y profesionales independientes en Argentina que solo venden por redes sociales y no tienen página web. Odian las complicaciones técnicas y buscan soluciones simples que les traigan clientes directos al celular.

    **TUS 4 PILARES DE VENTA:**
    1. Precio/Valor: Gratis con subdominio, o solo $2.000 ARS mensuales con dominio propio (menos que un alfajor). Cero tarjetas ni débitos automáticos: mes a mes por transferencia bancaria.
    2. Cero Fricción: Todo se maneja por WhatsApp (no tienen que aprender a usar paneles ni plataformas).
    3. Velocidad: Web lista en 30 minutos.
    4. SEO Local: Posicionamiento en Google Maps.

    **TU TONO Y ESTILO:**
    - Español de Argentina (usá el "vos"). Profesional, empático, claro y muy directo.
    
    **TAREA ESPECÍFICA:**
    {task_description}
    
    Devolvé ÚNICAMENTE el resultado final, sin aclaraciones extras ni saludos, listo para usar.
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def post_to_instagram(image_url, caption):
    # 1. Create Media Container
    url_create = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    res = requests.post(url_create, data=payload)
    data = res.json()
    if "id" not in data:
        print("Error creating media container:", data)
        return False
    creation_id = data["id"]
    
    # 2. Publish Container
    url_publish = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    payload_pub = {
        "creation_id": creation_id,
        "access_token": IG_ACCESS_TOKEN
    }
    res_pub = requests.post(url_publish, data=payload_pub)
    data_pub = res_pub.json()
    if "id" in data_pub:
        print("Successfully published to Instagram! Post ID:", data_pub["id"])
        return True
    else:
        print("Error publishing post:", data_pub)
        return False

import sqlite3
from sender import send_whatsapp_message

ADMIN_PHONE = "5491134710787"  # El número del administrador (Pablo)

def save_draft(image_url, caption, content_type):
    db_path = os.path.join(os.getcwd(), 'messages.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("INSERT INTO marketing_content (content_type, copy_text, design_description, status) VALUES (?, ?, ?, ?)", (content_type, caption, image_url, "draft"))
        draft_id = c.lastrowid
        conn.commit()
        conn.close()
        return draft_id
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', type=str, default='post', choices=['post', 'reel'])
    args = parser.parse_args()
    content_type = args.type

    print(f"Starting Auto Poster (Draft Mode) - Type: {content_type}...")
    img_url = get_random_image()
    if not img_url:
        print("Missing image URL. Exiting.")
        return
    
    print(f"Selected image: {img_url}")
    caption = generate_caption(content_type)
    print(f"Generated caption:\n{caption}\n")
    
    # Save as draft
    draft_id = save_draft(img_url, caption, content_type)
    if draft_id:
        print(f"Draft saved successfully with ID: {draft_id}")
        msg = "🚀 *NUEVO BORRADOR DE INSTAGRAM*\n\nTu asistente generó un nuevo posteo.\nEntrá al Dashboard para revisarlo y publicarlo:\nhttps://tuweblista.com.ar/admin"
        send_whatsapp_message(ADMIN_PHONE, msg)
        print("WhatsApp alert sent.")
    else:
        print("Error saving draft.")

if __name__ == "__main__":
    main()
