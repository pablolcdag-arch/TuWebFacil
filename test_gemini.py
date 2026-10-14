import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def test_gen():
    genai.configure(api_key=GEMINI_API_KEY)
    # The SDK for Gemini requires just "gemini-1.5-flash" or similar, wait, what is the right model string?
    # In app.py we were using 'gemini-3.6-flash' wait, does that exist? In my previous edit I put 'gemini-3.6-flash'.
    # Actually, in app.py we previously had 'gemini-3.6-flash' ? No, looking back at app.py:
    model = genai.GenerativeModel('gemini-flash-lite-latest')
    
    prompt = """Sos un experto en marketing y diseño web. Un usuario acaba de registrarse para crear su página web.
El usuario indicó que su rubro/negocio es: "Peluquería Canina".
Su nombre de negocio es: "Doggy Style".

Genera un JSON estrictamente con la siguiente estructura y datos relevantes para este rubro:
{
    "servicios_sugeridos": ["Nombre Servicio 1", "Nombre Servicio 2", "Nombre Servicio 3"],
    "descripciones_servicios": ["Breve descripción vendedora del servicio 1 (máx 15 palabras)", "Breve descripción vendedora del servicio 2", "Breve descripción vendedora del servicio 3"],
    "foto_hero_query": "3 palabras clave en INGLES para buscar una foto de portada perfecta en Unsplash (ej: modern lawyer office)",
    "fotos_queries": ["3 palabras ingles para foto servicio 1", "3 palabras ingles foto servicio 2", "3 palabras ingles foto servicio 3"],
    "paleta_colores": {"primario": "#hexcode", "secundario": "#hexcode"}
}
Devuelve SOLO el JSON válido, sin formato markdown ni explicaciones adicionales."""

    response = model.generate_content(prompt)
    text_resp = response.text.strip()
    if text_resp.startswith("```json"):
        text_resp = text_resp.strip("`").replace("json\n", "", 1)
        
    data = json.loads(text_resp)
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    test_gen()
