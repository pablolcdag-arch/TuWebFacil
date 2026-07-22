import os
import json
import requests
import re
import uuid
import unicodedata
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for
from flask_cors import CORS 
from dotenv import load_dotenv
from supabase import create_client, Client

# Carga de variables de entorno
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app) 

# --- CONFIGURACIÓN ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

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
        print(f"Error en Nominatim: {e}")
        
    return {"lat": -38.416097, "lon": -63.616672, "zoom": 4}

def buscar_foto_unsplash(query, rubro_general):
    """Búsqueda de fotos con respaldo para asegurar estética profesional."""
    if not UNSPLASH_ACCESS_KEY: 
        return "https://images.unsplash.com/photo-1521791136364-798a7bc0d26e?q=80&w=1000"
    try:
        url = f"https://api.unsplash.com/search/photos?query={query}&per_page=1&orientation=landscape&content_filter=high"
        headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get("results"): 
            return data["results"][0]["urls"]["regular"]
        
        # Respaldo: si no hay foto específica, buscamos por rubro general
        url_alt = f"https://api.unsplash.com/search/photos?query={rubro_general}&per_page=1"
        data_alt = requests.get(url_alt, headers=headers).json()
        if data_alt.get("results"):
            return data_alt["results"][0]["urls"]["regular"]
    except: 
        pass
    return "https://images.unsplash.com/photo-1521791136364-798a7bc0d26e?q=80&w=1000"

def llamar_a_ia_directo(rubro, contexto_completo=""):
    """Cerebro de la web: Genera textos y descripciones visuales para fotos."""
    prompt_sistema = f"""Actúa como experto en Copywriting para Argentina. 
    Genera un JSON para una web de '{rubro}'.
    
    REGLAS DE LENGUAJE:
    1. PROHIBIDO: 'deléitate', 'manjares', 'exquisito', 'hecho con amor'.
    2. USAR: 'disfrutá', 'probá', 'calidad', 'confianza', 'profesionalismo'.
    3. Tono: Profesional, vendedor y directo.
    
    REGLAS DE IMÁGENES:
    1. Genera frases visuales LITERALES en INGLÉS para Unsplash.
       Ej: 'modern fitness gym equipment' en lugar de 'entrenamiento'.
    
    RESPONDE SOLO EL JSON:
    {{
      "titulo_web": "", "subtitulo": "",
      "paleta_colores": {{"primario": "#hex", "secundario": "#hex"}},
      "servicios_sugeridos": ["", "", ""],
      "descripciones_servicios": ["", "", ""],
      "fotos_queries": ["visual description 1", "visual description 2", "visual description 3"],
      "horario": "", "ubicacion_detectada": "", "galeria": []
    }}"""
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": prompt_sistema}, 
            {"role": "user", "content": f"Rubro: {rubro}\nDatos proporcionados: {contexto_completo}"}
        ],
        "response_format": {"type": "json_object"}
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    response = requests.post(GROQ_URL, headers=headers, json=payload)
    return response.json()['choices'][0]['message']['content']

def slugify(text):
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return re.sub(r'[^\w\s-]', '', text).strip().lower().replace(' ', '-')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/process_form', methods=['POST'])
def process_form():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400

        # Unificamos las 5 preguntas en un bloque de contexto para la IA
        contexto_unificado = f"""
        ZONA/UBICACIÓN: {data.get('zona', 'No especificada')}
        HORARIOS: {data.get('horarios', 'No especificados')}
        EXPERIENCIA: {data.get('experiencia', 'No especificada')}
        SERVICIO ESTRELLA: {data.get('servicio_estrella', 'No especificado')}
        INFO EXTRA: {data.get('bio', '')}
        """

        # 1. IA genera el contenido base
        res_ia_raw = llamar_a_ia_directo(data['business_type'], contexto_unificado)
        res_ia = json.loads(res_ia_raw)
        
        # 2. Búsqueda de fotos y coordenadas precisas
        res_ia["fotos_servicios"] = [buscar_foto_unsplash(q, data['business_type']) for q in res_ia["fotos_queries"]]
        # Priorizamos el campo 'zona' del formulario para el mapa
        res_ia["mapa"] = obtener_coordenadas(data.get('zona') or res_ia.get('ubicacion_detectada'))

        # 3. Persistencia en Supabase
        slug = f"{slugify(res_ia['titulo_web'])}-{uuid.uuid4().hex[:6]}"
        
        if supabase:
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

        return jsonify({"success": True, "slug": slug})
    except Exception as e:
        print(f"❌ Error detectado: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/<client_slug>')
def client_website(client_slug):
    try:
        res = supabase.table("websites").select("*").eq("subdomain", client_slug).execute()
        if not res.data: return redirect(url_for('index'))
        web = res.data[0]
        cont = supabase.table("website_content").select("*").eq("website_id", web["id"]).eq("is_current", True).execute()
        cli = supabase.table("clients").select("*").eq("id", web["client_id"]).execute()
        return render_template('client_template.html', 
                             web_content=json.loads(cont.data[0]["content"]), 
                             client=cli.data[0], web_status=web['status'])
    except: return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)