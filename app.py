import os
import sqlite3
import json
import requests
import re
import uuid
import unicodedata
import logging
import csv
import io
import time
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, send_file, session, flash
from flask_cors import CORS 
from dotenv import load_dotenv
from supabase import create_client, Client
from sender import send_whatsapp_message

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

# Carga de variables de entorno
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.getenv('SECRET_KEY', 'tuwebfacil_super_secret_key_2026')
app.config['SERVER_NAME'] = 'tuweblista.com.ar'
CORS(app) 

# --- CONFIGURACIÓN ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
BOT_PHONE = os.getenv("BOT_PHONE_NUMBER", "PONER_AQUI_TU_NUMERO")

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None
BASE_URL = "https://tuweblista.com.ar"

def initialize_db():
    db_path = os.path.join(os.getcwd(), 'messages.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create admin_messages if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS admin_messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  phone TEXT, 
                  name TEXT, 
                  message TEXT, 
                  reply TEXT, 
                  status TEXT, 
                  created_at TIMESTAMP)''')
                  
    # Create marketing_content if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS marketing_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        content_type TEXT,
        copy_text TEXT,
        design_description TEXT,
        status TEXT
    )''')
    
    # Add new columns safely
    try:
        c.execute("ALTER TABLE marketing_content ADD COLUMN canva_prompt TEXT")
    except Exception:
        pass
        
    try:
        c.execute("ALTER TABLE marketing_content ADD COLUMN scheduled_for DATETIME")
    except Exception:
        pass
        
    # Create marketing_settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS marketing_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_text TEXT,
            hashtags TEXT,
            image_keywords TEXT
        )
    ''')
    
    # Insert default settings if empty
    c.execute("SELECT COUNT(*) FROM marketing_settings")
    if c.fetchone()[0] == 0:
        default_prompt = """Sos el Community Manager y Copywriter Experto de TuWebLista. Tu objetivo principal es redactar contenido persuasivo, dinámico y atractivo para Instagram que convierta seguidores en clientes. Español de Argentina (usá el "vos"). Profesional, empático, claro y muy directo. Resaltá los beneficios principales (fácil, rápido, todo por WhatsApp, desde $4.000)."""
        default_hashtags = "#TuWebLista #DisenoWebArgentina #EmprendedoresArgentinos #VenderMas #NegociosLocales"
        default_image = """Diseño gráfico moderno y profesional. Estética relacionada a WhatsApp (tonos verdes y blancos). 
Incluir un mock-up de un smartphone (iPhone) mostrando una página web limpia.
Texto en grande: "VENDE MÁS RÁPIDO CON WHATSAPP".
Elementos: Ícono de WhatsApp, cursor haciendo clic."""
        
        c.execute("INSERT INTO marketing_settings (prompt_text, hashtags, image_keywords) VALUES (?, ?, ?)", 
                  (default_prompt, default_hashtags, default_image))
                  
    conn.commit()
    conn.close()

initialize_db()

@app.template_filter('format_phone')
def format_phone(phone_str):
    if not phone_str: return ""
    p = str(phone_str).replace(' ', '').replace('+', '').replace('-', '')
    if p.startswith('549') and len(p) >= 12:
        return f"+54 9 {p[3:]}"
    elif len(p) == 10:
        return f"+54 9 {p}"
    return phone_str

def obtener_coordenadas(ubicacion_texto):
    """Convierte texto de ubicación en coordenadas. Foco en precisión Argentina."""
    if not ubicacion_texto or "argentina" in ubicacion_texto.lower() or "no proporcionada" in ubicacion_texto.lower():
        return {"lat": -38.416097, "lon": -63.616672, "zoom": 4}
    
    try:
        # Aseguramos que la búsqueda sea en Argentina para evitar conflictos con ciudades homónimas
        busqueda = f"{ubicacion_texto}, Argentina" if "argentina" not in ubicacion_texto.lower() else ubicacion_texto
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={busqueda}&limit=1"
        res = requests.get(url, headers={'User-Agent': 'TuWebFacilApp/1.0'})
        data = res.json()
        
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            # Zoom: 16 para dirección exacta, 12 para ciudad/zona
            tiene_numeros = any(char.isdigit() for char in ubicacion_texto)
            return {"lat": lat, "lon": lon, "zoom": 16 if tiene_numeros else 12}
    except Exception as e:
        logging.warning(f"Error en Nominatim: {e}")
        
    return {"lat": -38.416097, "lon": -63.616672, "zoom": 4}

def buscar_foto_unsplash(query, rubro_general, used_urls=None):
    """Búsqueda de fotos con respaldo para asegurar estética profesional y evitar repetidas."""
    if used_urls is None:
        used_urls = set()
        
    if not UNSPLASH_ACCESS_KEY: 
        return "https://images.unsplash.com/photo-1521791136364-798a7bc0d26e?q=80&w=1000"
    
    try:
        # Buscamos varias fotos para poder elegir una no usada
        url = f"https://api.unsplash.com/search/photos?query={query}&per_page=10&orientation=landscape&content_filter=high"
        headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get("results"):
            for result in data["results"]:
                img_url = result["urls"]["regular"]
                if img_url not in used_urls:
                    used_urls.add(img_url)
                    return img_url
        
        # Respaldo: si no hay foto específica o todas están usadas, buscamos por rubro general
        url_alt = f"https://api.unsplash.com/search/photos?query={rubro_general}&per_page=10"
        data_alt = requests.get(url_alt, headers=headers).json()
        if data_alt.get("results"):
            for result in data_alt["results"]:
                img_url = result["urls"]["regular"]
                if img_url not in used_urls:
                    used_urls.add(img_url)
                    return img_url
    except Exception as e:
        logging.warning(f"Error buscando foto en Unsplash: {e}")
    
    # Si todo falla, retornamos un fallback genérico y evitamos errores
    fallback = "https://images.unsplash.com/photo-1521791136364-798a7bc0d26e?q=80&w=1000"
    used_urls.add(fallback)
    return fallback

def generar_plantilla_dinamica(rubro, titulo, zona, horario):
    plantilla_base = {
        "titulo_web": titulo if titulo else "Mi Negocio",
        "subtitulo": rubro if rubro else "Brindamos soluciones de máxima calidad",
        "paleta_colores": {"primario": "#4f46e5", "secundario": "#6366f1"},
        "servicios_sugeridos": ["Servicio 1", "Servicio 2", "Servicio 3"],
        "descripciones_servicios": [
            "Describí tu primer servicio principal acá.",
            "Acá va la descripción de tu segundo servicio.",
            "Contale a tus clientes de qué se trata tu tercer servicio."
        ],
        "foto_hero_query": "professional business modern",
        "fotos_queries": ["customer service professional", "premium quality service", "fast efficiency work"],
        "horario": horario if horario else "Enviá 'Editar Horarios' por WhatsApp.",
        "ubicacion_detectada": zona if zona else "Enviá 'Editar Ubicación' por WhatsApp.",
        "galeria": []
    }

    if not GEMINI_API_KEY:
        return plantilla_base

    import google.generativeai as genai
    import json
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Using gemini-flash-lite-latest as it is confirmed to work
        model = genai.GenerativeModel('gemini-flash-lite-latest')
        
        prompt = f"""Sos un experto en marketing y diseño web. Un usuario acaba de registrarse para crear su página web.
El usuario indicó que su rubro/negocio es: "{rubro}".
Su nombre de negocio es: "{titulo}".

Genera un JSON estrictamente con la siguiente estructura y datos relevantes para este rubro:
{{
    "servicios_sugeridos": ["Nombre Servicio 1", "Nombre Servicio 2", "Nombre Servicio 3"],
    "descripciones_servicios": ["Breve descripción vendedora del servicio 1 (máx 15 palabras)", "Breve descripción vendedora del servicio 2", "Breve descripción vendedora del servicio 3"],
    "foto_hero_query": "3 palabras clave en INGLES para buscar una foto de portada perfecta en Unsplash (ej: modern lawyer office)",
    "fotos_queries": ["3 palabras ingles para foto servicio 1", "3 palabras ingles foto servicio 2", "3 palabras ingles foto servicio 3"],
    "paleta_colores": {{"primario": "#hexcode", "secundario": "#hexcode"}}
}}
Devuelve SOLO el JSON válido, sin formato markdown ni explicaciones adicionales."""

        response = model.generate_content(prompt)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp.strip("`").replace("json\n", "", 1)
            
        data = json.loads(text_resp)
        
        # Merge AI data with base template
        plantilla_base["servicios_sugeridos"] = data.get("servicios_sugeridos", plantilla_base["servicios_sugeridos"])
        plantilla_base["descripciones_servicios"] = data.get("descripciones_servicios", plantilla_base["descripciones_servicios"])
        plantilla_base["foto_hero_query"] = data.get("foto_hero_query", plantilla_base["foto_hero_query"])
        plantilla_base["fotos_queries"] = data.get("fotos_queries", plantilla_base["fotos_queries"])
        if "paleta_colores" in data and isinstance(data["paleta_colores"], dict):
            plantilla_base["paleta_colores"] = data["paleta_colores"]
            
    except Exception as e:
        logging.error(f"Error generando plantilla dinámica con Gemini: {e}")
        
    return plantilla_base


def slugify(text):
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^\w\s-]', '', text).strip().lower().replace(' ', '-')

# Caché en memoria para sitios web generados en modo demo / local
DEMO_SITES = {}

# Dominios base que muestran la landing page (TuWebFacil)
BASE_DOMAINS = ["localhost:5000", "127.0.0.1:5000", "tuweblista.com.ar", "tuwebfacil.com.ar", "ngrok-free.dev", "ngrok-free.app"]

@app.before_request
def check_custom_domain():
    host = request.host.lower()
    
    # Si es una petición a un archivo estático, la dejamos pasar
    if request.path.startswith('/static/') or request.path.startswith('/process_form'):
        return None
        
    # Chequear si es un dominio base
    is_base_domain = False
    for bd in BASE_DOMAINS:
        if bd in host:
            is_base_domain = True
            break
            
    # Si NO es dominio base, intentar cargar la web de ese cliente
    if not is_base_domain and supabase:
        try:
            domain_to_check = host.split(":")[0]
            if domain_to_check.startswith("www."):
                domain_to_check = domain_to_check[4:]
            res = supabase.table("websites").select("*").eq("custom_domain", domain_to_check).execute()
            if res.data:
                web = res.data[0]
        except Exception as e:
            # Si Supabase falla (ej. 504 Gateway Timeout), no queremos que la app principal tire un 500.
            # Simplemente asumimos que no es un custom domain válido en este preciso momento, 
            # o retornamos un mensaje de mantenimiento.
            print(f"Error checking custom domain: {e}")
            return "<h1>Servicio temporalmente inactivo.</h1><p>Estamos realizando tareas de mantenimiento. Por favor, reintente en unos minutos.</p>", 503
            
        if 'web' in locals():
            
            # Chequear si está en mantenimiento por falta de pago
            if web.get('status') == 'maintenance':
                return "<h1>Sitio suspendido temporalmente.</h1><p>Por favor, comuníquese con administración.</p>", 402
                
            cont = supabase.table("website_content").select("*").eq("website_id", web["id"]).eq("is_current", True).execute()
            cli = supabase.table("clients").select("*").eq("id", web["client_id"]).execute()
            
            content_data = cont.data[0]["content"]
            parsed_content = json.loads(content_data) if isinstance(content_data, str) else content_data
            
            has_edits = cont.data[0]["version"] > 1
            return render_template('client_template.html', 
                                 web_content=parsed_content, 
                                 client=cli.data[0], 
                                 web_status=web['status'],
                                 bot_phone=BOT_PHONE,
                                 has_edits=has_edits)
    return None

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory('static/uploads', filename)

@app.route('/receipts/<path:filename>')
def serve_receipts(filename):
    if not session.get('admin_logged_in'):
        return "No autorizado", 403
    return send_from_directory('receipts', filename)

# ====== FUNCIONES AUXILIARES ======

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/privacidad')
def privacidad():
    return render_template('privacidad.html')

@app.route('/process_form', methods=['POST'])
def process_form():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400

        # Verificar límite de 3 webs por número de teléfono
        if supabase and data.get("phone"):
            phone = data["phone"]
            # Buscar si el cliente existe
            res_cli = supabase.table("clients").select("id").eq("phone", phone).execute()
            if res_cli.data:
                cli_id = res_cli.data[0]["id"]
                # Contar webs del cliente
                res_webs = supabase.table("websites").select("id", count="exact").eq("client_id", cli_id).execute()
                if res_webs.count and res_webs.count >= 3:
                    return jsonify({"success": False, "error": "Ya llegaste al máximo de 3 páginas permitidas por número de teléfono, manda un mensaje para solicitar más cupo."}), 400

        # Unificamos las preguntas en un bloque de contexto para la IA
        contexto_unificado = f"""
        ZONA/UBICACIÓN: {data.get('zona', 'No especificada')}
        HORARIOS: {data.get('horarios', 'No especificados')}
        EXPERIENCIA: {data.get('experiencia', 'No especificada')}
        SERVICIO ESTRELLA: {data.get('servicio_estrella', 'No especificado')}
        INFO EXTRA: {data.get('bio', '')}
        """
        
        titulo_sugerido = data.get('titulo', '')
        subtitulo_sugerido = data.get('subtitulo', '')

        logging.info(f"Procesando formulario para rubro: {data.get('business_type')}")

        # 1. Asignar plantilla generada por Gemini
        res_ia = generar_plantilla_dinamica(data.get('business_type', ''), titulo_sugerido, data.get('zona'), data.get('horarios'))
        
        # 2. Búsqueda de fotos y coordenadas precisas
        used_image_urls = set()
        
        # Foto Hero
        foto_hero_query = res_ia.get("foto_hero_query", data['business_type'])
        res_ia["foto_hero"] = buscar_foto_unsplash(foto_hero_query, data['business_type'], used_image_urls)
        
        # Fotos de servicios sin repetir
        res_ia["fotos_servicios"] = [buscar_foto_unsplash(q, data['business_type'], used_image_urls) for q in res_ia.get("fotos_queries", [])]
        
        # Priorizamos el campo 'zona' del formulario para el mapa
        res_ia["mapa"] = obtener_coordenadas(data.get('zona') or res_ia.get('ubicacion_detectada'))

        # 3. Datos Extra del formulario
        res_ia["google_maps"] = data.get("google_maps", "")
        plan_type = data.get("plan_type", "basico")
        res_ia["plan_type"] = plan_type
        
        # Guardamos el whatsapp comercial si lo completaron
        wa_comercial = data.get("whatsapp_contacto", "").strip()
        if wa_comercial:
            res_ia["whatsapp_contacto"] = wa_comercial

        # 4. Identificador de la web y almacenamiento en caché local
        slug = f"{slugify(res_ia['titulo_web'])}-{uuid.uuid4().hex[:6]}"
        DEMO_SITES[slug] = {
            "web_content": res_ia,
            "client": {"phone": data.get('phone', '')},
            "status": "demo",
            "plan_type": plan_type
        }

        # 4. Persistencia opcional en Supabase (si está online)
        if supabase:
            try:
                cli = supabase.table("clients").upsert({
                    "phone": data['phone'], "business_type": data['business_type'], "status": "active"
                }, on_conflict="phone").execute()
                
                client_id = cli.data[0]["id"]
                web = supabase.table("websites").insert({
                    "client_id": client_id, "subdomain": slug, 
                    "seo_title": res_ia.get("titulo_web"), "status": "demo"
                }).execute()
                
                supabase.table("website_content").insert({
                    "website_id": web.data[0]["id"], 
                    "content": json.dumps(res_ia), "is_current": True
                }).execute()
            except Exception as se:
                logging.warning(f"Error al conectar o guardar en Supabase: {se}")

        logging.info(f"Sitio demo creado con éxito: {slug}")
        return jsonify({"success": True, "slug": slug})
    except Exception as e:
        logging.error(f"Error detectado procesando formulario: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/', subdomain="<client_slug>")
def client_website(client_slug):
    try:
        # 1. Prioridad: Consultar en Supabase si está disponible
        if supabase:
            res = supabase.table("websites").select("*").eq("subdomain", client_slug).execute()
            if res.data:
                web = res.data[0]
                
                # Chequear si está en mantenimiento por falta de pago
                if web.get('status') == 'maintenance':
                    return "<h1>Sitio suspendido temporalmente.</h1><p>Por favor, comuníquese con administración al WhatsApp.</p>", 402

                cont = supabase.table("website_content").select("*").eq("website_id", web["id"]).eq("is_current", True).execute()
                cli = supabase.table("clients").select("*").eq("id", web["client_id"]).execute()
                
                content_data = cont.data[0]["content"]
                parsed_content = json.loads(content_data) if isinstance(content_data, str) else content_data
                
                has_edits = cont.data[0]["version"] > 1
                return render_template('client_template.html', 
                                     web_content=parsed_content, 
                                     client=cli.data[0], 
                                     web_status=web['status'],
                                     bot_phone=BOT_PHONE,
                                     has_edits=has_edits)

        # 2. Fallback: Si no está en BD (o no hay conexión), buscar en la caché local en memoria
        if client_slug in DEMO_SITES:
            site = DEMO_SITES[client_slug]
            return render_template('client_template.html', 
                                 web_content=site["web_content"], 
                                 client=site["client"], 
                                 web_status=site["status"],
                                 bot_phone=BOT_PHONE,
                                 has_edits=False)
        
        logging.warning(f"No se encontró la web '{client_slug}'")
        return redirect(url_for('index'))
    except Exception as e:
        logging.error(f"Error al cargar la web '{client_slug}': {e}")
        return redirect(url_for('index'))

# --- RUTAS DE ADMINISTRACIÓN ---
ADMIN_PASS = "webfacil2026"


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASS:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Contraseña incorrecta'
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
        
    if not supabase: return "Sin conexión a BD", 500
    
    # Obtener métricas
    cli_res = supabase.table("clients").select("id, phone, business_type, created_at").order("created_at", desc=True).execute()
    clients = cli_res.data
    
    sub_res = supabase.table("subscriptions").select("plan_type, status").execute()
    subs = sub_res.data
    
    free_webs = sum(1 for s in subs if s.get('plan_type') == 'gratis' and s.get('status') == 'active')
    premium_webs = sum(1 for s in subs if s.get('plan_type') == 'premium' and s.get('status') == 'active')
    
    stats = {
        "total_users": len(clients),
        "free_webs": free_webs,
        "premium_webs": premium_webs
    }
    
    # Obtener Demos Abandonadas (clientes con estado activo/demo que no están en suscripciones activas premium/gratis)
    # Forma sencilla: filtrar websites con status = 'demo'
    web_res = supabase.table("websites").select("client_id, subdomain, created_at").eq("status", "demo").execute()
    demo_client_ids = [w["client_id"] for w in web_res.data] if web_res.data else []
    
    abandoned_demos = []
    if demo_client_ids:
        # Get details of those clients
        abandoned_res = supabase.table("clients").select("id, phone, business_type, created_at").in_("id", demo_client_ids).execute()
        if abandoned_res.data:
            abandoned_demos = abandoned_res.data
            # Sort by created_at desc
            abandoned_demos.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
    # Obtener Webs Publicadas
    pub_res = supabase.table("websites").select("id, custom_domain, subdomain, created_at, clients(phone)").eq("status", "published").order("created_at", desc=True).execute()
    published_webs = pub_res.data if pub_res.data else []
    for w in published_webs:
        w["phone"] = w["clients"]["phone"] if w.get("clients") else "Desconocido"
    
    # Obtener pagos pendientes
    pend_res = supabase.table("payments").select("*, clients(phone)").eq("status", "uploaded").execute()
    pending = []
    if pend_res.data:
        for p in pend_res.data:
            p["phone"] = p["clients"]["phone"] if p.get("clients") else "Desconocido"
            p["receipt_path"] = p.get("payment_method")
            pending.append(p)
    
    # Agregar dominio a los pendientes
    for p in pending:
        p["requested_domain"] = p.get("invoice_number", "No especificado")
            
    # Obtener mensajes de SQLite
    messages = []
    import sqlite3
    db_path = os.path.join(os.getcwd(), "messages.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM admin_messages ORDER BY created_at DESC")
        messages = [dict(row) for row in c.fetchall()]
        conn.close()

    # Fetch marketing drafts from sqlite
    marketing_drafts = []
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM marketing_content WHERE status = 'draft' ORDER BY created_at DESC")
        marketing_drafts = [dict(row) for row in c.fetchall()]
        conn.close()

    return render_template('admin_dashboard.html', stats=stats, pending_payments=pending, recent_clients=clients[:10], messages=messages, marketing_drafts=marketing_drafts, abandoned_demos=abandoned_demos, published_webs=published_webs)

@app.route('/admin/delete_abandoned_demos', methods=['POST'])
def delete_abandoned_demos():
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    client_ids_str = request.form.get('client_ids', '')
    if client_ids_str:
        client_ids = [cid.strip() for cid in client_ids_str.split(',') if cid.strip()]
        for cid in client_ids:
            try:
                webs_res = supabase.table("websites").select("id").eq("client_id", cid).execute()
                if webs_res.data:
                    for w in webs_res.data:
                        supabase.table("website_content").delete().eq("website_id", w["id"]).execute()
                
                supabase.table("websites").delete().eq("client_id", cid).execute()
                supabase.table("clients").delete().eq("id", cid).execute()
            except Exception as e:
                logging.error(f"Error borrando demo abandonada {cid}: {e}")
                
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_clients', methods=['POST'])
def delete_clients():
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    client_ids_str = request.form.get('client_ids', '')
    if client_ids_str:
        client_ids = [cid.strip() for cid in client_ids_str.split(',') if cid.strip()]
        for cid in client_ids:
            try:
                webs_res = supabase.table("websites").select("id").eq("client_id", cid).execute()
                if webs_res.data:
                    for w in webs_res.data:
                        supabase.table("website_content").delete().eq("website_id", w["id"]).execute()

                supabase.table("websites").delete().eq("client_id", cid).execute()
                supabase.table("subscriptions").delete().eq("client_id", cid).execute()
                supabase.table("payments").delete().eq("client_id", cid).execute()
                supabase.table("clients").delete().eq("id", cid).execute()
            except Exception as e:
                logging.error(f"Error borrando cliente {cid}: {e}")
                
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/retargeting/<client_id>', methods=['POST'])
def send_retargeting(client_id):
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    # Manejo de múltiples IDs si vienen separados por coma (batch)
    client_ids = client_id.split(',')
    success_count = 0
    
    for cid in client_ids:
        cid = cid.strip()
        if not cid: continue
        
        # Obtener teléfono del cliente
        res = supabase.table("clients").select("phone, business_type").eq("id", cid).execute()
        if not res.data:
            continue
            
        client = res.data[0]
        phone = client["phone"]
        
        mensaje = f"¡Hola! 👋 Vimos que creaste tu página web para tu {client.get('business_type', 'negocio')} pero no llegaste a activarla. ¿Tuviste algún problema o duda en la que podamos ayudarte?\n\nPara retomarla, solo escribí *Quiero confirmar mi web* en este chat."
        
        if send_whatsapp_message(phone, mensaje):
            success_count += 1
            
    if success_count > 0:
        return jsonify({"success": True, "sent": success_count})
    else:
        return jsonify({"success": False, "error": "Falló el envío de mensajes o no se encontraron clientes"})

@app.route('/admin/maps_scraper', methods=['POST'])
def maps_scraper():
    if not session.get('admin_logged_in'): return jsonify({"error": "No autorizado"}), 403
    
    query = request.form.get('query')
    if not query:
        return jsonify({"error": "Falta el término de búsqueda"}), 400
        
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return jsonify({"error": "No hay GOOGLE_MAPS_API_KEY configurada"}), 500
        
    prospectos = []
    
    # Llamada inicial
    search_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={requests.utils.quote(query)}&key={api_key}"
    
    try:
        res = requests.get(search_url).json()
        if res.get("status") != "OK" and res.get("status") != "ZERO_RESULTS":
            return jsonify({"error": f"Error de API: {res.get('status')}"}), 500
            
        results = res.get("results", [])
        
        # Opcional: Procesar segunda página si existe para tener más datos (esperando 2 seg)
        next_token = res.get("next_page_token")
        if next_token:
            time.sleep(2)
            page2_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?pagetoken={next_token}&key={api_key}"
            res2 = requests.get(page2_url).json()
            if res2.get("status") == "OK":
                results.extend(res2.get("results", []))
                
        # Buscar detalles de teléfono
        for place in results:
            place_id = place.get("place_id")
            det_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_phone_number,formatted_address&key={api_key}"
            det_res = requests.get(det_url).json()
            
            if det_res.get("status") == "OK":
                d = det_res.get("result", {})
                name = d.get("name", "")
                phone = d.get("formatted_phone_number", "")
                address = d.get("formatted_address", "")
                
                # Filtrar solo los que tienen teléfono (necesario para Whatsapp)
                if phone:
                    prospectos.append([name, phone, address])
                    
        # Generar CSV en memoria
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Nombre del Local', 'Teléfono', 'Dirección'])
        writer.writerows(prospectos)
        
        # Devolver como archivo descargable
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'prospectos_{slugify(query)}.csv'
        )
        
    except Exception as e:
        logging.error(f"Error en Maps Scraper: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/view_receipt/<pid>')
def view_receipt(pid):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    res = supabase.table("payments").select("payment_method").eq("id", pid).execute()
    if res.data and res.data[0].get("payment_method"):
        return send_file(res.data[0]["payment_method"])
    return "Imagen no encontrada", 404

@app.route('/admin/approve/<pid>')
def approve_payment(pid):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    # Marcar como aprobado
    res = supabase.table("payments").select("*, clients(phone)").eq("id", pid).execute()
    if not res.data: return "Pago no encontrado", 404
    
    pago = res.data[0]
    client_id = pago["client_id"]
    phone = pago["clients"]["phone"] if pago.get("clients") else "Desconocido"
    
    supabase.table("payments").update({"status": "approved"}).eq("id", pid).execute()
    # Insertar en subscriptions como premium
    supabase.table("subscriptions").insert({
        "client_id": client_id,
        "plan_type": "premium",
        "status": "active"
    }).execute()
    # supabase.table("subscriptions").update({"status": "active"}).eq("client_id", client_id).eq("plan_type", "premium").execute()
    
    # Configurar Nginx automáticamente
    dominio = pago.get("invoice_number", "").strip()
    if dominio:
        import subprocess
        # Buscar la web más reciente del cliente para actualizar solo esa
        res_webs = supabase.table("websites").select("id").eq("client_id", client_id).order("created_at", desc=True).limit(1).execute()
        if res_webs.data:
            web_id = res_webs.data[0]["id"]
            supabase.table("websites").update({"custom_domain": dominio, "status": "published"}).eq("id", web_id).execute()
        else:
            return "No se encontró ninguna web para publicar", 400
        
        # Generar config de Nginx
        nginx_conf = f"""server {{
    listen 80;
    server_name {dominio} www.{dominio};

    location / {{
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}
}}"""
        conf_path = f"/etc/nginx/sites-available/{dominio}"
        link_path = f"/etc/nginx/sites-enabled/{dominio}"
        
        try:
            with open(conf_path, 'w') as f:
                f.write(nginx_conf)
            if not os.path.exists(link_path):
                os.symlink(conf_path, link_path)
            subprocess.run(["systemctl", "reload", "nginx"], check=False)
            logging.info(f"Nginx config creada para {dominio}")
        except Exception as e:
            logging.error(f"Error configurando Nginx para {dominio}: {e}")
    
    msg = ("✅ ¡Tu pago ha sido verificado con éxito!\n\n"
           "Tu Plan Premium ya está activo. En las próximas 24/48hs hábiles te confirmaremos cuando el dominio "
           "esté registrado y apuntando a tu web.\n\n"
           "¡Gracias por confiar en TuWebLista! 🚀")
    send_whatsapp_message(phone, msg)
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/revert_publish/<website_id>', methods=['POST'])
def revert_publish(website_id):
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    res = supabase.table("websites").select("custom_domain").eq("id", website_id).execute()
    if not res.data or not res.data[0].get("custom_domain"):
        return jsonify({"success": False, "error": "Dominio no encontrado"})
        
    dominio = res.data[0]["custom_domain"]
    
    # Remover configuración de Nginx si existe
    import subprocess, os
    conf_path = f"/etc/nginx/sites-available/{dominio}"
    link_path = f"/etc/nginx/sites-enabled/{dominio}"
    try:
        if os.path.exists(link_path): os.remove(link_path)
        if os.path.exists(conf_path): os.remove(conf_path)
        subprocess.run(["systemctl", "reload", "nginx"], check=False)
    except Exception as e:
        logging.error(f"Error borrando Nginx config para {dominio}: {e}")
        
    # Revertir DB
    supabase.table("websites").update({"custom_domain": None, "status": "demo"}).eq("id", website_id).execute()
    
    # Obtener client_id para borrar su suscripción
    res_web = supabase.table("websites").select("client_id").eq("id", website_id).execute()
    if res_web.data:
        client_id = res_web.data[0]["client_id"]
        supabase.table("subscriptions").delete().eq("client_id", client_id).execute()
        
    return jsonify({"success": True, "message": f"Web despublicada exitosamente. Se eliminó {dominio}."})

@app.route('/admin/generate_ssl/<website_id>', methods=['POST'])
def generate_ssl(website_id):
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    res = supabase.table("websites").select("custom_domain").eq("id", website_id).execute()
    if not res.data or not res.data[0].get("custom_domain"):
        return jsonify({"success": False, "error": "Dominio no encontrado"})
        
    dominio = res.data[0]["custom_domain"]
    try:
        import subprocess
        cmd = [
            "certbot", "--nginx", 
            "-d", dominio, "-d", f"www.{dominio}", 
            "--non-interactive", "--agree-tos", 
            "-m", "tuweblista@gmail.com", 
            "--redirect"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({"success": True, "message": f"SSL generado exitosamente para {dominio}"})
        else:
            logging.error(f"Certbot error: {result.stderr}")
            return jsonify({"success": False, "error": result.stderr})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/admin/reject/<pid>')
def reject_payment(pid):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    res = supabase.table("payments").select("*, clients(phone)").eq("id", pid).execute()
    if not res.data: return "Pago no encontrado", 404
    
    pago = res.data[0]
    phone = pago["clients"]["phone"] if pago.get("clients") else "Desconocido"
    
    supabase.table("payments").update({"status": "rejected"}).eq("id", pid).execute()
    
    msg = ("❌ Tuvimos un inconveniente verificando el comprobante de pago que nos enviaste.\n\n"
           "Por favor, revisá que la foto sea legible o enviá un nuevo comprobante respondiendo con la imagen por este chat.")
    send_whatsapp_message(phone, msg)
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reply_message/<int:msg_id>', methods=['POST'])
def reply_message(msg_id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    reply_text = request.form.get('reply_text')
    if not reply_text: return "Mensaje vacío", 400
    
    import sqlite3
    db_path = os.path.join(os.getcwd(), "messages.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT phone FROM admin_messages WHERE id = ?", (msg_id,))
        row = c.fetchone()
        if row:
            phone = row[0]
            send_whatsapp_message(phone, f"👨🏻‍💻 *Respuesta del Administrador:*\n\n{reply_text}")
            c.execute("UPDATE admin_messages SET status = 'replied', reply = ? WHERE id = ?", (reply_text, msg_id))
            conn.commit()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_messages', methods=['POST'])
def delete_messages():
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    msg_ids = request.form.get('message_ids', '')
    if msg_ids:
        import sqlite3
        ids_list = [i.strip() for i in msg_ids.split(',') if i.strip().isdigit()]
        if ids_list:
            placeholders = ','.join('?' * len(ids_list))
            db_path = os.path.join(os.getcwd(), "messages.db")
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute(f"DELETE FROM admin_messages WHERE id IN ({placeholders})", ids_list)
            conn.commit()
            conn.close()
            return jsonify({"success": True})
            
    return jsonify({"success": False, "error": "No se encontraron mensajes válidos"})


@app.route('/admin/broadcast', methods=['POST'])
def broadcast_message():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    target_group = request.form.get('target_group')
    message = request.form.get('broadcast_message')
    if not message: return "Mensaje vacío", 400
    
    formatted_msg = f"📣 *Comunicado de TuWebLista:*\n\n{message}"
    
    if target_group == 'manual':
        manual_numbers = request.form.get('manual_numbers', '')
        phones = [p.strip() for p in manual_numbers.split(',') if p.strip()]
        for phone in phones:
            send_whatsapp_message(phone, formatted_msg)
    else:
        # Fetch all clients
        res = supabase.table("clients").select("id, phone").execute()
        if not res.data: return "No hay clientes", 404
        
        clients = res.data
        if target_group == 'all':
            for c in clients:
                send_whatsapp_message(c['phone'], formatted_msg)
        else:
            # Need to filter by premium/free via subscriptions
            sub_res = supabase.table("subscriptions").select("client_id, plan_type").eq("status", "active").execute()
            subs = sub_res.data if sub_res.data else []
            premium_client_ids = [s['client_id'] for s in subs if s['plan_type'] == 'premium']
            
            for c in clients:
                is_premium = c['id'] in premium_client_ids
                if (target_group == 'premium' and is_premium) or (target_group == 'free' and not is_premium):
                    send_whatsapp_message(c['phone'], formatted_msg)

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/marketing/settings', methods=['GET', 'POST'])
def marketing_settings():
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    import sqlite3
    db_path = os.path.join(os.getcwd(), 'messages.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        c.execute("""UPDATE marketing_settings SET 
                     prompt_text = ?, hashtags = ?, image_keywords = ? 
                     WHERE id = 1""", 
                  (data.get('prompt_text'), data.get('hashtags'), data.get('image_keywords')))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
        
    c.execute("SELECT prompt_text, hashtags, image_keywords FROM marketing_settings WHERE id = 1")
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({"prompt_text": row[0], "hashtags": row[1], "image_keywords": row[2]})
    return jsonify({})

@app.route('/admin/marketing/generate_promo_ai', methods=['POST'])
def generate_promo_ai():
    if not session.get('admin_logged_in'): return jsonify({"success": False, "error": "No autorizado"}), 403
    
    try:
        import google.generativeai as genai
        import sqlite3
        import json
        
        db_path = os.path.join(os.getcwd(), 'messages.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("SELECT prompt_text, hashtags, image_keywords FROM marketing_settings WHERE id = 1")
        settings = c.fetchone()
        
        base_prompt = settings[0] if settings else "Escribí un post corto y persuasivo."
        hashtags = settings[1] if settings else "#TuWebLista"
        design_guidelines = settings[2] if settings else "Diseño verde de WhatsApp"
        
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            return jsonify({"success": False, "error": "Falta GEMINI_API_KEY"})
            
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-3.6-flash')
        
        prompt = f"""Actúa como Copywriter y Director de Arte. 
Instrucciones de Texto: {base_prompt}
Instrucciones de Diseño Visual: {design_guidelines}
Hashtags a incluir: {hashtags}

Debes devolver un objeto JSON estrictamente con este formato y nada más:
{{
  "caption": "Acá va el texto del posteo de Instagram, usando emojis y los hashtags al final.",
  "canva_prompt": "Acá van las instrucciones detalladas de qué tiene que decir la imagen y qué gráfica usar, para pasarlo a Canva IA."
}}"""

        response = model.generate_content(prompt)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp.strip("`").replace("json\n", "", 1)
            
        data = json.loads(text_resp)
        copy_text = data.get("caption", "")
        canva_prompt = data.get("canva_prompt", "")
        
        # design_description is null initially (no image yet)
        c.execute("INSERT INTO marketing_content (content_type, copy_text, canva_prompt, status) VALUES (?, ?, ?, ?)", 
                  ("post", copy_text, canva_prompt, "draft"))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Borrador de ideas generado con éxito."})
    except Exception as e:
        logging.error(f"Error generando promo IA: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/marketing/approve/<id>')
def marketing_approve_route(id):
    return marketing_approve(id)

@app.route('/admin/marketing/upload', methods=['POST'])
def marketing_upload():
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    content_type = request.form.get('content_type', 'reel')
    caption = request.form.get('caption', '')
    
    if 'media_file' not in request.files:
        flash('No se seleccionó ningún archivo.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    file = request.files['media_file']
    if file.filename == '':
        flash('El archivo no tiene nombre.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    if file:
        filename = secure_filename(file.filename)
        # Ensure directory exists
        upload_folder = os.path.join(os.getcwd(), 'static', 'marketing_images')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Save to DB
        media_url = f"{BASE_URL}/static/marketing_images/{filename}"
        import sqlite3
        db_path = os.path.join(os.getcwd(), 'messages.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("INSERT INTO marketing_content (content_type, copy_text, design_description, status) VALUES (?, ?, ?, ?)", (content_type, caption, media_url, "draft"))
        conn.commit()
        conn.close()
        
        flash('Publicación guardada como borrador con éxito.', 'success')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/marketing/upload_design/<id>', methods=['POST'])
def marketing_upload_design(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    if 'design_file' not in request.files:
        flash('No se seleccionó ninguna imagen.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    file = request.files['design_file']
    if file.filename == '':
        flash('El archivo no tiene nombre.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    if file:
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(os.getcwd(), 'static', 'marketing_images')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        media_url = f"{BASE_URL}/static/marketing_images/{filename}"
        
        import sqlite3
        db_path = os.path.join(os.getcwd(), 'messages.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("UPDATE marketing_content SET design_description = ? WHERE id = ?", (media_url, id))
        conn.commit()
        conn.close()
        
        flash('Diseño subido con éxito. El borrador está listo para publicar.', 'success')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/marketing/schedule/<id>', methods=['POST'])
def marketing_schedule(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    schedule_time = request.form.get('schedule_time')
    if not schedule_time:
        flash('Debe seleccionar fecha y hora.', 'error')
        return redirect(url_for('admin_dashboard'))
        
    import sqlite3
    db_path = os.path.join(os.getcwd(), 'messages.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("UPDATE marketing_content SET status = 'scheduled', scheduled_for = ? WHERE id = ?", (schedule_time, id))
    conn.commit()
    conn.close()
    
    flash('Publicación programada con éxito.', 'success')
    return redirect(url_for('admin_dashboard'))

def marketing_approve(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    import sqlite3
    db_path = os.path.join(os.getcwd(), "messages.db")
    draft = None
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM marketing_content WHERE id = ?", (id,))
        row = c.fetchone()
        if row: draft = dict(row)
        conn.close()
        
    if not draft: return "Draft not found", 404
    
    image_url = draft["design_description"]
    caption = draft["copy_text"]
    
    import sys
    scripts_dir = os.path.join(os.getcwd(), 'scripts')
    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)
    
    try:
        from instagram_auto_poster import post_to_instagram
    except ImportError:
        import instagram_auto_poster
        post_to_instagram = instagram_auto_poster.post_to_instagram
        
    success = post_to_instagram(image_url, caption)
    
    if success:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("UPDATE marketing_content SET status = 'published' WHERE id = ?", (id,))
            conn.commit()
            conn.close()
        flash('Publicado exitosamente en Instagram.', 'success')
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Error al publicar en Instagram. Revisa que el token y credenciales estén configuradas.', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/marketing/edit/<id>', methods=['POST'])
def marketing_edit(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    new_text = request.form.get('copy_text')
    new_prompt = request.form.get('canva_prompt')
    
    if new_text or new_prompt:
        db_path = os.path.join(os.getcwd(), 'messages.db')
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        if new_text and new_prompt:
            c.execute("UPDATE marketing_content SET copy_text = ?, canva_prompt = ? WHERE id = ?", (new_text, new_prompt, id))
        elif new_text:
            c.execute("UPDATE marketing_content SET copy_text = ? WHERE id = ?", (new_text, id))
        elif new_prompt:
            c.execute("UPDATE marketing_content SET canva_prompt = ? WHERE id = ?", (new_prompt, id))
            
        conn.commit()
        conn.close()
        flash('Cambios guardados correctamente.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/marketing/reject/<id>')
def marketing_reject(id):
    if not session.get('admin_logged_in'): return redirect(url_for('admin_login'))
    
    import sqlite3
    db_path = os.path.join(os.getcwd(), "messages.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("UPDATE marketing_content SET status = 'rejected' WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)