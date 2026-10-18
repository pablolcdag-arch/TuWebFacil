import os
import re
import json
import sqlite3
import requests
import secrets
from dotenv import load_dotenv
from supabase import create_client
from sender import send_whatsapp_message, send_whatsapp_image, download_whatsapp_media, send_whatsapp_buttons, send_whatsapp_list
from scripts.utils.price_list_parser import parse_price_list
import logging
import uuid
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)

load_dotenv()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

# Diccionario en memoria como caché de sesiones de usuario.
# Formato: { "numero_wa": {"estado": "MAIN_MENU", "temp_data": {}} }
user_states = {}

# Estados posibles
IDLE = "IDLE"
MAIN_MENU = "MAIN_MENU"
EDIT_MENU = "EDIT_MENU"
EDIT_MENU_SERVICIOS = "EDIT_MENU_SERVICIOS"
WAITING_FOR_TITLE = "WAITING_FOR_TITLE"
WAITING_FOR_SUBTITLE = "WAITING_FOR_SUBTITLE"
WAITING_FOR_SERVICE_TITLE = "WAITING_FOR_SERVICE_TITLE"
WAITING_FOR_SERVICE_DESC = "WAITING_FOR_SERVICE_DESC"
WAITING_FOR_LOCATION = "WAITING_FOR_LOCATION"
WAITING_FOR_SCHEDULE = "WAITING_FOR_SCHEDULE"
WAITING_FOR_IMAGE_ROLE = "WAITING_FOR_IMAGE_ROLE"
WAITING_FOR_RECEIPT = "WAITING_FOR_RECEIPT"
WAITING_FOR_PLAN_SELECTION = "WAITING_FOR_PLAN_SELECTION"
WAITING_FOR_DOMAIN_NAME = "WAITING_FOR_DOMAIN_NAME"
WAITING_FOR_ADMIN_MESSAGE = "WAITING_FOR_ADMIN_MESSAGE"
WAITING_FOR_WHATSAPP = "WAITING_FOR_WHATSAPP"
WAITING_FOR_EMAIL = "WAITING_FOR_EMAIL"
WAITING_FOR_INSTAGRAM = "WAITING_FOR_INSTAGRAM"
WAITING_FOR_TRANSFER_PHONE = "WAITING_FOR_TRANSFER_PHONE"
WAITING_FOR_PRICE_LIST = "WAITING_FOR_PRICE_LIST"
CONFIRM_PRICE_LIST_DRAFT = "CONFIRM_PRICE_LIST_DRAFT"
WAITING_FOR_PRICE_MENU_OPTION = "WAITING_FOR_PRICE_MENU_OPTION"
WAITING_FOR_PROMO_TITLE = "WAITING_FOR_PROMO_TITLE"
WAITING_FOR_PROMO_DISCOUNT_1 = "WAITING_FOR_PROMO_DISCOUNT_1"
WAITING_FOR_PROMO_DATE_1 = "WAITING_FOR_PROMO_DATE_1"
WAITING_FOR_PROMO_TIER2_CHOICE = "WAITING_FOR_PROMO_TIER2_CHOICE"
WAITING_FOR_PROMO_DISCOUNT_2 = "WAITING_FOR_PROMO_DISCOUNT_2"
WAITING_FOR_PROMO_DATE_2 = "WAITING_FOR_PROMO_DATE_2"
CONFIRM_PROMO_DRAFT = "CONFIRM_PROMO_DRAFT"


def get_db_path():
    """Retorna la ruta absoluta a messages.db."""
    cwd_db = os.path.join(os.getcwd(), "messages.db")
    if os.path.exists(cwd_db):
        return cwd_db
    file_dir_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "messages.db")
    if os.path.exists(file_dir_db):
        return file_dir_db
    return cwd_db


def init_sessions_db():
    """Crea la tabla user_sessions si no existe en messages.db y activa modo WAL."""
    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                phone TEXT PRIMARY KEY,
                estado TEXT NOT NULL,
                temp_data TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        logging.error(f"Error al inicializar tabla user_sessions en {get_db_path()}: {e}")
    finally:
        if conn:
            conn.close()


# Inicializar la tabla al cargar el módulo
init_sessions_db()


def get_user_state(wa_id) -> dict:
    """
    Obtiene el estado actual y temp_data del usuario.
    Primero consulta la caché en memoria; si no está, busca en SQLite.
    Garantiza devolver siempre un diccionario con {'estado': ..., 'temp_data': ...}.
    """
    clean_wa_id = str(wa_id).strip()
    
    # 1. Caché en memoria
    if clean_wa_id in user_states:
        cached = user_states[clean_wa_id]
        if isinstance(cached, dict) and "estado" in cached:
            if "temp_data" not in cached or not isinstance(cached["temp_data"], dict):
                cached["temp_data"] = {}
            return cached

    # 2. Consultar SQLite
    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT estado, temp_data FROM user_sessions WHERE phone = ?", (clean_wa_id,))
        row = c.fetchone()
        if row:
            estado, temp_data_raw = row
            try:
                temp_data = json.loads(temp_data_raw) if temp_data_raw else {}
                if not isinstance(temp_data, dict):
                    temp_data = {}
            except Exception:
                temp_data = {}
            session_data = {"estado": estado or IDLE, "temp_data": temp_data}
            user_states[clean_wa_id] = session_data
            return session_data
    except Exception as e:
        logging.error(f"Error al leer user_state para {clean_wa_id} de SQLite: {e}")
    finally:
        if conn:
            conn.close()

    # 3. Fallback por defecto si no existe o falló la BD
    default_session = {"estado": IDLE, "temp_data": {}}
    user_states[clean_wa_id] = default_session
    return default_session


def set_user_state(wa_id, estado, temp_data=None):
    """
    Actualiza el estado y opcionalmente temp_data del usuario en memoria y SQLite.
    Si temp_data es None, preserva el temp_data existente.
    """
    clean_wa_id = str(wa_id).strip()

    if temp_data is None:
        current = get_user_state(clean_wa_id)
        final_temp_data = current.get("temp_data", {})
        if not isinstance(final_temp_data, dict):
            final_temp_data = {}
    elif isinstance(temp_data, dict):
        final_temp_data = temp_data
    else:
        final_temp_data = {}

    session_data = {"estado": estado, "temp_data": final_temp_data}
    user_states[clean_wa_id] = session_data

    # Persistir en SQLite
    conn = None
    try:
        db_path = get_db_path()
        temp_data_str = json.dumps(final_temp_data, ensure_ascii=False)
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("""
            INSERT INTO user_sessions (phone, estado, temp_data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phone) DO UPDATE SET
                estado = excluded.estado,
                temp_data = excluded.temp_data,
                updated_at = CURRENT_TIMESTAMP
        """, (clean_wa_id, estado, temp_data_str))
        conn.commit()
    except Exception as e:
        logging.error(f"Error al persistir user_state para {clean_wa_id} en SQLite: {e}")
    finally:
        if conn:
            conn.close()

    return session_data


def clear_user_state(wa_id):
    """
    Limpia la sesión del usuario tanto en memoria como en SQLite.
    """
    clean_wa_id = str(wa_id).strip()
    user_states[clean_wa_id] = {"estado": IDLE, "temp_data": {}}

    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("DELETE FROM user_sessions WHERE phone = ?", (clean_wa_id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Error al limpiar user_state para {clean_wa_id} en SQLite: {e}")
    finally:
        if conn:
            conn.close()

def obtener_web_del_cliente(phone):
    """Busca la web actual del cliente en Supabase usando su teléfono."""
    if not supabase:
        return None
    try:
        # 1. Buscar al cliente
        clean_phone = phone.replace("+", "")
        base_phone = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
        cli_res = supabase.table("clients").select("id").ilike("phone", f"%{base_phone}").execute()
        
        if not cli_res.data:
            return None
        
        client_id = cli_res.data[0]["id"]
        
        # 2. Buscar su web (asumimos la más reciente)
        web_res = supabase.table("websites").select("id, subdomain, custom_domain").eq("client_id", client_id).order("created_at", desc=True).limit(1).execute()
        if not web_res.data:
            return None
            
        website_id = web_res.data[0]["id"]
        slug = web_res.data[0]["subdomain"]
        custom_domain = web_res.data[0].get("custom_domain")
        
        # 3. Buscar la versión actual de la web
        ver_res = supabase.table("website_content").select("id, content").eq("website_id", website_id).execute()
            
        if ver_res.data:
            return {
                "website_id": website_id,
                "version_id": ver_res.data[0]["id"],
                "content": json.loads(ver_res.data[0]["content"]) if isinstance(ver_res.data[0]["content"], str) else ver_res.data[0]["content"],
                "slug": slug,
                "custom_domain": custom_domain
            }
    except Exception as e:
        logging.error(f"Error al buscar web en BD: {e}")
    return None

def actualizar_web_content(version_id, new_content):
    if not supabase:
        return False
    try:
        # Obtener versión actual
        res = supabase.table("website_content").select("version").eq("id", version_id).execute()
        current_version = res.data[0]["version"] if res.data else 1
        
        supabase.table("website_content").update({"content": new_content, "version": current_version + 1}).eq("id", version_id).execute()
        return True
    except Exception as e:
        logging.error(f"Error al actualizar web en BD: {e}")
        return False

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
    
    # Fallback default
    return {"lat": -38.416097, "lon": -63.616672, "zoom": 4}

def verificar_y_consumir_cuota(phone):
    return True, 999

def procesar_borrador_lista_precios(wa_id, parsed_data, nombre):
    """Genera borrador seguro de lista de precios con draft_token y envía vista previa."""
    draft_token = secrets.token_hex(4)
    temp_data = {
        "draft_prices": parsed_data,
        "draft_token": draft_token
    }
    set_user_state(wa_id, CONFIRM_PRICE_LIST_DRAFT, temp_data)

    # Persistir en tabla price_drafts para preservar histórico de tokens
    conn = None
    try:
        conn = sqlite3.connect(get_db_path(), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS price_drafts (
                token TEXT PRIMARY KEY,
                phone TEXT,
                draft_prices TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            INSERT OR REPLACE INTO price_drafts (token, phone, draft_prices)
            VALUES (?, ?, ?)
        """, (draft_token, wa_id, json.dumps(parsed_data)))
        conn.commit()
    except Exception as e:
        logging.error(f"Error guardando price_draft en SQLite: {e}")
    finally:
        if conn:
            conn.close()

    count = len(parsed_data.get("items", []))
    ejemplos_lines = []
    for it in parsed_data.get("items", [])[:3]:
        srv = it.get("servicio", "Servicio")
        prc_dict = it.get("precios", {})
        prc_str = " / ".join([f"{k.capitalize()}: {v}" for k, v in prc_dict.items() if v and v != "-"])
        if not prc_str:
            prc_str = "-"
        ejemplos_lines.append(f"• *{srv}*: {prc_str}")
    ejemplos_txt = "\n".join(ejemplos_lines)

    web_info = obtener_web_del_cliente(wa_id)
    if web_info and web_info.get("custom_domain"):
        preview_url = f"https://{web_info['custom_domain']}/precios?preview={draft_token}"
    else:
        slug = web_info["slug"] if web_info else "mi-web"
        preview_url = f"https://{slug}.tuweblista.com.ar/precios?preview={draft_token}"

    msg = (f"📋 *¡Borrador de Lista de Precios generado!*\n\n"
           f"Detectamos *{count} servicios*:\n"
           f"{ejemplos_txt}\n\n"
           f"🔗 *Mirá cómo se ve tu lista acá:*\n"
           f"{preview_url}\n\n"
           f"¿Deseás publicarla ahora mismo en tu web?\n\n"
           f"💡 _Si algo no se ve como querías, tocá Cancelar o escribí *soporte* para que te ayudemos a configurarlo._")

    buttons = [
        {"id": "CONFIRM_PRICES_OK", "title": "✅ Publicar Precios"},
        {"id": "CONFIRM_PRICES_CANCEL", "title": "❌ Cancelar"}
    ]
    send_whatsapp_buttons(wa_id, msg, buttons)

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def parse_promo_date(texto):
    """
    Parsea y valida fechas para promociones.
    Soporta formatos DD/MM y DD/MM/AAAA (con separadores /, -, . o espacios).
    Si solo se ingresa DD/MM, calcula el año (actual, o el siguiente si ya pasó).
    Retorna dict con 'iso' (YYYY-MM-DD) y 'display' ('27 de Octubre de 2026'), o None si no es válida.
    """
    if not texto:
        return None
    raw = str(texto).strip()
    match = re.search(r'(\d{1,2})[/\-.\s](\d{1,2})(?:[/\-.\s](\d{2,4}))?', raw)
    if not match:
        return None
    
    try:
        day = int(match.group(1))
        month = int(match.group(2))
        year_raw = match.group(3)
        now = datetime.now()
        
        if year_raw:
            year = int(year_raw)
            if year < 100:
                year += 2000
        else:
            year = now.year
            target_candidate = datetime(year, month, day).date()
            if target_candidate < now.date():
                year += 1
                
        valid_date = datetime(year, month, day).date()
        mes_nombre = MESES_ES.get(valid_date.month, "")
        
        return {
            "iso": valid_date.strftime("%Y-%m-%d"),
            "display": f"{valid_date.day} de {mes_nombre} de {valid_date.year}",
            "year": valid_date.year,
            "month": valid_date.month,
            "day": valid_date.day,
            "date": valid_date
        }
    except Exception as e:
        logging.warning(f"Error parseando fecha '{texto}': {e}")
        return None

def mostrar_menu_precios(wa_id):
    """Muestra el submenú interactivo de gestión de precios y promociones según el estado de la web del cliente."""
    web_info = obtener_web_del_cliente(wa_id)
    tiene_lista = False
    tiene_promo = False
    if web_info and web_info.get("content"):
        lp = web_info["content"].get("lista_precios")
        if lp and isinstance(lp, dict) and lp.get("items"):
            tiene_lista = True
            if lp.get("promocion_fecha"):
                tiene_promo = True

    if tiene_lista:
        options = [
            {"id": "PRECIOS_ACTUALIZAR", "title": "📄 Actualizar Precios", "description": "Subir nuevo Excel, PDF o texto"},
            {"id": "PROMO_FECHA_START", "title": "📅 Promo por Fecha", "description": "Reserva anticipada con % de descuento"}
        ]
        if tiene_promo:
            options.append({"id": "PROMO_DETENER", "title": "⏹️ Detener Promo Activa", "description": "Quitar descuento y volver a precios normales"})
        options.append({"id": "PRECIOS_QUITAR", "title": "🗑️ Quitar Lista", "description": "Eliminar la lista de precios de la web"})
        options.append({"id": "PRECIOS_VOLVER", "title": "⬅️ Volver", "description": "Regresar al menú principal"})

        msg = ("📋 *Gestión de Precios y Promociones*\n\n"
               "Ya tenés una lista de precios publicada en tu web. Elegí qué deseás configurar:")
        send_whatsapp_list(wa_id, msg, "Ver Opciones", options, "Precios y Promos")
        set_user_state(wa_id, WAITING_FOR_PRICE_MENU_OPTION)
    else:
        msg = ("📋 *Actualización de Lista de Precios*\n\n"
               "Podés enviarme:\n"
               "1️⃣ Un archivo Excel (.xlsx) o CSV.\n"
               "2️⃣ Un archivo PDF con tus precios.\n"
               "3️⃣ Una foto nítida de tu lista o pizarra de precios.\n"
               "4️⃣ O directamente escribir/pegar tu lista acá por texto (Ej: Corte $15.000 / Barba $8.000).\n\n"
               "¿Cómo preferís enviármela?\n\n"
               "💡 _(Escribí *cancelar* o *volver* para regresar al menú anterior)_")
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, WAITING_FOR_PRICE_LIST)

def detener_promocion_activa(wa_id, nombre):
    """Detiene y retira la promoción por fecha activa de la web del cliente."""
    web_info = obtener_web_del_cliente(wa_id)
    if not web_info or not web_info.get("content"):
        send_whatsapp_message(wa_id, "⚠️ No encontramos tu página web en el sistema.")
        set_user_state(wa_id, MAIN_MENU, {})
        return False

    content = web_info["content"]
    lp = content.get("lista_precios")
    if lp and isinstance(lp, dict) and lp.get("promocion_fecha"):
        lp.pop("promocion_fecha", None)
        if actualizar_web_content(web_info["version_id"], content):
            slug = web_info.get("slug", "mi-web")
            public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"
            msg = (f"⏹️ ¡Listo! La promoción fue detenida y retirada de tu web.\n\n"
                   f"Tus precios volvieron a mostrarse en su valor regular sin descuentos ni banners.\n\n"
                   f"🔗 Refrescá tu web: {public_url}")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
            return True
        else:
            send_whatsapp_message(wa_id, "❌ Hubo un error al actualizar tu web en la base de datos.")
            set_user_state(wa_id, MAIN_MENU, {})
            return False
    else:
        send_whatsapp_message(wa_id, "ℹ️ Tu lista de precios no tiene ninguna promoción activa en este momento.")
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        return False

def generar_borrador_promocion(wa_id, temp_data, nombre):
    """
    Construye la estructura promocion_fecha, inyecta en draft_prices,
    genera un draft_token seguro y envía mensaje con vista previa y botones.
    """
    web_info = obtener_web_del_cliente(wa_id)
    if not web_info or not web_info.get("content"):
        send_whatsapp_message(wa_id, "⚠️ No pudimos encontrar tu web en el sistema para asociar la promoción.")
        set_user_state(wa_id, IDLE, {})
        return False
    
    current_lp = web_info["content"].get("lista_precios")
    if not current_lp or not isinstance(current_lp, dict) or not current_lp.get("items"):
        send_whatsapp_message(wa_id, "⚠️ Necesitás tener una lista de precios publicada para poder activar una promoción.")
        set_user_state(wa_id, IDLE, {})
        return False
    
    desc_1 = temp_data.get("promo_desc_1", 30)
    date_1_iso = temp_data.get("promo_date_1_iso", "")
    date_1_display = temp_data.get("promo_date_1_display", "")
    
    escalas = [
        {
            "hasta": date_1_iso,
            "hasta_display": date_1_display,
            "descuento": desc_1,
            "label": f"{desc_1}% OFF Anticipado"
        }
    ]
    
    has_tier2 = "promo_desc_2" in temp_data and "promo_date_2_iso" in temp_data
    if has_tier2:
        desc_2 = temp_data["promo_desc_2"]
        date_2_iso = temp_data["promo_date_2_iso"]
        date_2_display = temp_data["promo_date_2_display"]
        escalas.append({
            "hasta": date_2_iso,
            "hasta_display": date_2_display,
            "descuento": desc_2,
            "label": f"{desc_2}% OFF"
        })
    
    titulo_promo = temp_data.get("promo_title", "Jornada Especial")
    promocion_data = {
        "titulo": titulo_promo,
        "activa": True,
        "escalas": escalas
    }
    
    draft_prices = json.loads(json.dumps(current_lp))
    draft_prices["promocion_fecha"] = promocion_data
    
    draft_token = secrets.token_hex(4)
    
    conn = None
    try:
        conn = sqlite3.connect(get_db_path(), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL;")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS price_drafts (
                token TEXT PRIMARY KEY,
                phone TEXT,
                draft_prices TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            INSERT OR REPLACE INTO price_drafts (token, phone, draft_prices)
            VALUES (?, ?, ?)
        """, (draft_token, wa_id, json.dumps(draft_prices)))
        conn.commit()
    except Exception as e:
        logging.error(f"Error guardando price_draft de promoción en SQLite: {e}")
    finally:
        if conn:
            conn.close()
            
    temp_data["draft_token"] = draft_token
    temp_data["draft_prices"] = draft_prices
    temp_data["promocion_data"] = promocion_data
    set_user_state(wa_id, CONFIRM_PROMO_DRAFT, temp_data)
    
    slug = web_info.get("slug", "mi-web")
    if web_info.get("custom_domain"):
        preview_url = f"https://{web_info['custom_domain']}/precios?preview={draft_token}"
    else:
        preview_url = f"https://{slug}.tuweblista.com.ar/precios?preview={draft_token}"
        
    tramo_2_txt = f"🟡 *Tramo 2:* {temp_data['promo_desc_2']}% OFF hasta el {temp_data['promo_date_2_display']}\n" if has_tier2 else ""
    
    msg = (f"🎉 *¡Borrador de Promoción generado!*\n\n"
           f"📅 *Evento:* {titulo_promo}\n"
           f"🟢 *Tramo 1:* {desc_1}% OFF hasta el {date_1_display}\n"
           f"{tramo_2_txt}\n"
           f"🔗 *Mirá cómo se ve tu promo y los precios en tu web:*\n"
           f"{preview_url}\n\n"
           f"¿Deseás activarla en tu web ahora mismo?")
           
    buttons = [
        {"id": "CONFIRM_PROMO_OK", "title": "✅ Activar Promo"},
        {"id": "CONFIRM_PROMO_CANCEL", "title": "❌ Cancelar"}
    ]
    send_whatsapp_buttons(wa_id, msg, buttons)
    return True

def procesar_mensaje(wa_id, texto, nombre, msg_type="text", media_id=None, filename=None):
    """Función principal que enruta el mensaje según el estado actual."""
    print(f"DEBUG BOT: Mensaje recibido de {nombre} ({wa_id}): Tipo: {msg_type} - '{texto}'")
    
    user_session = get_user_state(wa_id)
    estado_actual = user_session["estado"]
    
    if msg_type not in ["text", "interactive", "image", "document"]:
        send_whatsapp_message(wa_id, "Por favor, escribime por texto o enviame archivos (Excel, CSV, PDF) o imágenes. Todavía no puedo escuchar audios. 😅")
        return

    texto_limpio = texto.strip().lower()
    print(f"DEBUG BOT: Estado actual: {estado_actual}")
    
    # 1. Palabra clave universal de reseteo
    if texto_limpio in ["menu", "menú", "volver", "inicio", "cancelar", "btn_menu", "main_menu"]:
        clear_user_state(wa_id)
        procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        return
        
    # 1.5 Interceptar código de mudanza
    if texto_limpio.startswith("mudanza-"):
        import sqlite3
        try:
            db_path = os.path.join(os.getcwd(), "messages.db")
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Check if code exists and is pending
            c.execute("SELECT from_phone, to_phone FROM transfers WHERE code = ?", (texto_limpio,))
            row = c.fetchone()
            if row:
                from_phone, to_phone = row
                
                # Check if this phone is the to_phone! (wa_id usually includes + or not, let's normalize)
                norm_wa = wa_id.replace("+", "").replace(" ", "").replace("-", "")
                
                if norm_wa == to_phone:
                    if supabase:
                        # Buscamos el cliente original
                        clean_from = from_phone.replace("+", "")
                        base_from = clean_from[-10:] if len(clean_from) >= 10 else clean_from
                        cli_res = supabase.table("clients").select("id").ilike("phone", f"%{base_from}").execute()
                        
                        if cli_res.data:
                            old_client_id = cli_res.data[0]["id"]
                            
                            # Obtenemos la web (la más reciente, que es la que el bot administra)
                            web_res = supabase.table("websites").select("id").eq("client_id", old_client_id).order("created_at", desc=True).limit(1).execute()
                            if web_res.data:
                                website_id = web_res.data[0]["id"]
                                
                                # Buscamos si el nuevo número ya tiene un cliente
                                clean_to = norm_wa.replace("+", "")
                                base_to = clean_to[-10:] if len(clean_to) >= 10 else clean_to
                                new_cli_res = supabase.table("clients").select("id").ilike("phone", f"%{base_to}").execute()
                                
                                if new_cli_res.data:
                                    new_client_id = new_cli_res.data[0]["id"]
                                else:
                                    # Creamos un nuevo cliente
                                    create_res = supabase.table("clients").insert({"phone": norm_wa, "name": "Usuario Transferido", "business_type": "No especificado"}).execute()
                                    new_client_id = create_res.data[0]["id"]
                                    
                                # Actualizamos el dueño de la web
                                supabase.table("websites").update({"client_id": new_client_id}).eq("id", website_id).execute()
                                
                                # Borramos el código
                                c.execute("DELETE FROM transfers WHERE code = ?", (texto_limpio,))
                                conn.commit()
                                
                                # Movemos el estado
                                clear_user_state(from_phone)
                                set_user_state(wa_id, IDLE, {})
                                
                                send_whatsapp_message(wa_id, "✅ ¡Transferencia exitosa! Ahora sos el administrador de esta página web.")
                                send_whatsapp_message(from_phone, f"⚠️ El usuario {norm_wa} ha aceptado la transferencia. Ya no tenés acceso a la administración de esta web.")
                                
                                # Le mostramos el menú al nuevo dueño
                                procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
                                return
                            else:
                                send_whatsapp_message(wa_id, "❌ El usuario original no tiene una web válida para transferir.")
                                return
                else:
                    send_whatsapp_message(wa_id, "❌ Este código de mudanza fue generado para otro número de teléfono.")
                    return
            else:
                send_whatsapp_message(wa_id, "❌ El código de mudanza no existe o ya fue usado.")
                return
        except Exception as e:
            logging.error(f"Error procesando mudanza: {e}")
            send_whatsapp_message(wa_id, "⚠️ Hubo un error procesando la transferencia.")
            return
        finally:
            conn.close()
            
    # 1.6 Interceptar respuestas al flujo del Día 27 (Trial 30 días)
    # Soporte para botones TRIAL_SUBDOMINIO, TRIAL_DOMINIO y texto tolerante
    is_trial_subdominio = (
        texto_limpio == "trial_subdominio" or
        texto_limpio in ["subdominio", "opcion 1", "opción 1"] or
        (estado_actual == IDLE and texto_limpio in ["1", "opcion 1", "opción 1", "subdominio"])
    )

    is_trial_dominio = (
        texto_limpio == "trial_dominio" or
        texto_limpio in ["opcion 2", "opción 2"] or
        (estado_actual == IDLE and texto_limpio in ["2", "opcion 2", "opción 2", "dominio", "dominio propio"])
    )

    if is_trial_subdominio:
        set_user_state(wa_id, WAITING_FOR_RECEIPT, {"plan": "subdominio", "monto": 2000})
        msg = ("¡Excelente elección! 🚀 Tu página seguirá online en su dirección actual.\n\n"
               "Para renovar tu mes activo, transferí $2.000 al siguiente Alias:\n"
               "*tuweblista*\n\n"
               "Una vez que transfieras, envianos la foto del comprobante por acá y lo activaremos en el día.")
        send_whatsapp_message(wa_id, msg)
        return

    if is_trial_dominio:
        set_user_state(wa_id, WAITING_FOR_DOMAIN_NAME, {"plan": "custom_domain", "monto": 10500})
        msg = ("¡Excelente! 💎 Vamos a registrar tu propio dominio .com.ar.\n\n"
               "Escribí el nombre que te gustaría tener (por ejemplo: 'minegocio.com.ar' o 'minegocio'):")
        send_whatsapp_message(wa_id, msg)
        return

    # 1.7 Interceptar intención de reactivación de web pausada ("reactivar mi web", "reactivar")
    if "reactivar mi web" in texto_limpio or "reactivar" in texto_limpio:
        web_info = obtener_web_del_cliente(wa_id)
        msg = (f"¡Hola {nombre}! 👋 Tu web está guardada y lista para reactivarse.\n\n"
               "Para volver a ponerla online hoy mismo por solo $2.000/mes (o con dominio .com.ar propio por $10.500), transferí el monto al siguiente Alias:\n"
               "*tuweblista*\n\n"
               "Una vez que transfieras, envianos la foto del comprobante por acá y la activaremos de inmediato. 🚀")
        send_whatsapp_message(wa_id, msg)
        temp_data = {"accion": "reactivacion", "monto": 2000}
        if web_info:
            if "slug" in web_info:
                temp_data["slug"] = web_info["slug"]
            if "website_id" in web_info:
                temp_data["website_id"] = web_info["website_id"]
        set_user_state(wa_id, WAITING_FOR_RECEIPT, temp_data)
        return

    # 1.8 Interceptar intención de detener promoción activa ("detener promo", "frenar promo", "pausar promo")
    if any(k in texto_limpio for k in ["detener promo", "frenar promo", "pausar promo", "detener promocion", "pausar promocion"]):
        detener_promocion_activa(wa_id, nombre)
        return

    # 2. Detectar intención de inicio (Confirmar mi web) - Esto resetea al MAIN MENU
    if "confirmar mi web" in texto_limpio:
        msg = (f"¡Hola {nombre}! 🎉 Qué bueno que te gustó tu demo.\n\n"
               f"📱 *TuWebLista - Panel de Control*\n\n"
               f"¿Qué te gustaría hacer con tu web hoy?\n\n"
               f"💡 _Tip: Podés escribir la palabra *'menu'* en cualquier momento para volver a ver estas opciones._")
        
        options = [
            {"id": "MAIN_VER_LINK", "title": "🌐 Ver mi página web"},
            {"id": "MAIN_PRECIOS", "title": "📋 Precios y Promos", "description": "Gestionar lista y promociones"},
            {"id": "MAIN_EDITAR", "title": "🛠️ Textos / Imágenes", "description": "Editar textos e imágenes"},
            {"id": "MAIN_DOMAIN", "title": "🌐 Comprar Dominio", "description": "Buscador de dominios .com.ar"},
            {"id": "MAIN_TRANSFER", "title": "🔄 Transferir Admin", "description": "Cambiar número celular"},
            {"id": "MAIN_PUBLICAR", "title": "🚀 Publicar / Planes", "description": "Publicar página / ver planes"},
            {"id": "MAIN_CONTACT", "title": "💬 Hablar con Admin", "description": "Hablar con soporte / admin"}
        ]
        send_whatsapp_list(wa_id, msg, "Abrir Opciones", options, "Panel de Control")
        set_user_state(wa_id, MAIN_MENU, {})
        return

    # === RECEPCIÓN DE DOCUMENTOS ===
    if msg_type == "document":
        if estado_actual == WAITING_FOR_PRICE_LIST:
            doc_name = filename or texto or "precios.pdf"
            ext = os.path.splitext(doc_name)[1].lower()
            if not ext:
                ext = ".pdf"
            temp_filename = f"doc_{wa_id}_{uuid.uuid4().hex[:8]}{ext}"
            temp_dir = os.path.join(os.getcwd(), "receipts")
            os.makedirs(temp_dir, exist_ok=True)
            save_path = os.path.join(temp_dir, temp_filename)
            
            send_whatsapp_message(wa_id, "⏳ Analizando tu documento y extrayendo los precios... aguardá unos segundos.")
            if download_whatsapp_media(media_id, save_path):
                try:
                    parsed = parse_price_list(save_path, filename=doc_name)
                    if parsed and parsed.get("items"):
                        procesar_borrador_lista_precios(wa_id, parsed, nombre)
                    else:
                        send_whatsapp_message(wa_id, "⚠️ No pude detectar una lista de precios válida en el documento. Podés escribir *soporte* para que te ayudemos a cargarla, o probar enviándola en formato Excel, CSV o texto.")
                except Exception as e:
                    logging.error(f"Error parseando documento de precios: {e}")
                    send_whatsapp_message(wa_id, "❌ No pudimos procesar el archivo. Podés escribir *soporte* para que lo carguemos juntos o probar enviarlo en formato Excel o CSV.")
            else:
                send_whatsapp_message(wa_id, "❌ Hubo un error al descargar el archivo. Por favor intentá nuevamente.")
            return
        else:
            send_whatsapp_message(wa_id, "📄 Recibimos tu documento. Si querías actualizar tu lista de precios, primero seleccioná *Lista de Precios* en el menú de edición.")
            return

    # === RECEPCIÓN DE IMÁGENES ===
    if msg_type == "image":
        if estado_actual == WAITING_FOR_RECEIPT:
            filename = f"receipt_{wa_id}_{uuid.uuid4().hex[:8]}.jpg"
            receipts_dir = os.path.join(os.getcwd(), "receipts")
            os.makedirs(receipts_dir, exist_ok=True)
            save_path = os.path.join(receipts_dir, filename)
            
            if download_whatsapp_media(media_id, save_path):
                try:
                    clean_phone = wa_id.replace("+", "")
                    base_phone = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
                    res_cli = supabase.table("clients").select("id").ilike("phone", f"%{base_phone}").execute()
                    if res_cli.data:
                        cli_id = res_cli.data[0]["id"]
                        dominio = get_user_state(wa_id).get("temp_data", {}).get("dominio", "")
                        supabase.table("payments").insert({
                            "client_id": cli_id,
                            "payment_method": save_path,
                            "invoice_number": dominio,
                            "status": "uploaded"
                        }).execute()
                except Exception as e:
                    logging.error(f"Error guardando pending_payment en BD: {e}")
            
            msg = "✅ Recibimos el comprobante muchas gracias, en el transcurso del día recibirás una notificación con el 'Pago verificado'. Tu web va a seguir activa, no te preocupes."
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, IDLE, {})
            
            logging.info(f"NUEVO PAGO: {nombre} ({wa_id}) mandó un comprobante.")
            send_whatsapp_message("5491134710787", f"💰 NUEVO PAGO DE {nombre} ({wa_id}). Revisá el servidor.")
        elif estado_actual == WAITING_FOR_PRICE_LIST:
            filename_img = f"price_img_{wa_id}_{uuid.uuid4().hex[:8]}.jpg"
            temp_dir = os.path.join(os.getcwd(), "receipts")
            os.makedirs(temp_dir, exist_ok=True)
            save_path = os.path.join(temp_dir, filename_img)
            
            send_whatsapp_message(wa_id, "⏳ Procesando la foto de tus precios... aguardá unos segundos.")
            if download_whatsapp_media(media_id, save_path):
                try:
                    parsed = parse_price_list(save_path, filename=filename_img)
                    if parsed and parsed.get("items"):
                        procesar_borrador_lista_precios(wa_id, parsed, nombre)
                    else:
                        send_whatsapp_message(wa_id, "⚠️ No pude detectar precios legibles en la imagen. Probá con una foto más nítida o pegando el texto.")
                except Exception as e:
                    logging.error(f"Error procesando imagen de precios: {e}")
                    send_whatsapp_message(wa_id, "❌ Error al procesar la imagen de precios.")
            else:
                send_whatsapp_message(wa_id, "❌ Error al descargar la imagen.")
            return
        else:
            # Es una foto para la web
            msg = "¡Recibimos tu imagen! 📸 ¿En qué parte de tu web querés ponerla?"
            options = [
                {"id": "FOTO_HERO", "title": "🖼️ Foto Principal"},
                {"id": "FOTO_LOGO", "title": "🔹 Mi Logo"},
                {"id": "FOTO_SRV1", "title": "💼 Servicio 1"},
                {"id": "FOTO_SRV2", "title": "💼 Servicio 2"},
                {"id": "FOTO_SRV3", "title": "💼 Servicio 3"}
            ]
            send_whatsapp_list(wa_id, msg, "Elegir Destino", options, "Asignar Foto")
            set_user_state(wa_id, "WAITING_FOR_IMAGE_ROLE", {"media_id": media_id})
        return

    # === MÁQUINA DE ESTADOS PRINCIPAL ===
    if estado_actual == "WAITING_FOR_IMAGE_ROLE":
        if texto_limpio in ["foto_hero", "foto_logo", "foto_srv1", "foto_srv2", "foto_srv3"]:
            media_id_guardado = get_user_state(wa_id).get("temp_data", {}).get("media_id")
            if media_id_guardado:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                save_dir = os.path.join(base_dir, "static", "uploads")
                os.makedirs(save_dir, exist_ok=True)
                
                filename = f"{media_id_guardado}.jpg"
                save_path = os.path.join(save_dir, filename)
                
                if download_whatsapp_media(media_id_guardado, save_path):
                    # Guardar en BD
                    image_url = f"https://tuweblista.com.ar/static/uploads/{filename}"
                    web_data = obtener_web_del_cliente(wa_id)
                    if web_data:
                        content = web_data["content"]
                        if texto_limpio == "foto_hero":
                            content["foto_hero"] = image_url
                        elif texto_limpio == "foto_logo":
                            content["logo_url"] = image_url
                        elif texto_limpio == "foto_srv1":
                            content["fotos_servicios"][0] = image_url
                        elif texto_limpio == "foto_srv2":
                            content["fotos_servicios"][1] = image_url
                        elif texto_limpio == "foto_srv3":
                            content["fotos_servicios"][2] = image_url
                            
                        actualizar_web_content(web_data["version_id"], content)
                        msg_img = (f"✅ ¡Imagen actualizada con éxito!\n\n"
                                   f"🔗 *Refrescá tu web para verla:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                                   f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                        buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                        send_whatsapp_buttons(wa_id, msg_img, buttons)
                        set_user_state(wa_id, IDLE, {})
                        return
                    else:
                        send_whatsapp_message(wa_id, "⚠️ No encontré tu web en el sistema.")
                else:
                    send_whatsapp_message(wa_id, "❌ Hubo un error al descargar la imagen. Volvé a intentarlo.")
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "2", nombre)
            return

    elif estado_actual == MAIN_MENU:
        if texto_limpio in ["main_ver_link", "ver mi pagina web", "ver mi página web", "ver web", "1"]:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and (web_info.get("custom_domain") or web_info.get("slug")):
                web_url = f"https://{web_info['custom_domain']}" if web_info.get("custom_domain") else f"https://{web_info['slug']}.tuweblista.com.ar"
                msg = (f"🌐 *Tu Página Web:*\n\n"
                       f"Podés verla y compartirla ingresando acá:\n"
                       f"👉 {web_url}\n\n"
                       f"💡 _Tip: Copiá este enlace para enviárselo a tus clientes o colocarlo en el perfil de tus redes sociales._\n\n"
                       f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
            else:
                msg = ("⚠️ No encontramos una página web activa vinculada a tu número de teléfono.\n\n"
                       "📲 _Tocá el botón abajo o escribí *menu* para ver las opciones disponibles._")
                buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
        elif texto_limpio in ["main_precios", "precios", "promos", "promociones", "lista de precios"]:
            mostrar_menu_precios(wa_id)
        elif texto_limpio == "main_soporte" or texto_limpio == "main_contact":
            send_whatsapp_message(wa_id, "Escribí el mensaje que le querés enviar al administrador.\n\n⚠️ *Aviso*: Esto no es un chat en vivo, pero tu mensaje quedará registrado y te responderemos por este mismo medio en el transcurso del día.\n\n💡 _Si no querés enviar ningún mensaje ahora, escribí *cancelar* o *volver* para regresar al menú._")
            set_user_state(wa_id, WAITING_FOR_ADMIN_MESSAGE)

        elif texto_limpio == "main_transfer":
            msg = ("🔄 *Transferir Administración*\n\n"
                   "Para transferir la administración de esta web a otro número, escribí acá abajo el nuevo número de WhatsApp (Ej: 1131234567 o +5491131234567).\n\n"
                   "⚠️ Importante: Una vez confirmada la transferencia, perderás acceso a este menú.\n\n"
                   "💡 _Si no querés transferirla ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_TRANSFER_PHONE)

        elif texto_limpio == "main_domain":
            msg = ("🌐 *Buscador Oficial de Dominios (.com.ar)*\n\n"
                   "Escribí acá abajo el nombre que te gustaría tener para tu página (Ej: mipanaderia, estudiojuridico, etc).\n\n"
                   "No hace falta que escribas el '.com.ar', nosotros lo agregamos y verificamos si está disponible en NIC Argentina al instante.\n\n"
                   "💡 _Si preferís hacerlo en otro momento, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_DOMAIN_NAME)
            
        elif texto_limpio in ["main_editar", "editar", "2"]:
            msg = "✏️ *Menú de Edición*\n¿Qué parte de tu página web querés modificar?\n\n💡 _Para volver al menú principal escribí *volver*_"
            options = [
                {"id": "EDIT_TITULO", "title": "📝 Editar Título"},
                {"id": "EDIT_SUBTITULO", "title": "📝 Editar Subtítulo"},
                {"id": "EDIT_SERVICIOS", "title": "💼 Editar Servicios"},
                {"id": "EDIT_LOCATION", "title": "📍 Editar Ubicación"},
                {"id": "EDIT_SCHEDULE", "title": "🕒 Editar Horarios"},
                {"id": "EDIT_IMAGENES", "title": "🖼️ Editar Imágenes"},
                {"id": "EDIT_WHATSAPP", "title": "💬 Editar WhatsApp"},
                {"id": "EDIT_EMAIL", "title": "✉️ Editar Email"},
                {"id": "EDIT_INSTAGRAM", "title": "📷 Editar Instagram"}
            ]
            send_whatsapp_list(wa_id, msg, "Elegir Sección", options, "Edición de Web")
            set_user_state(wa_id, EDIT_MENU)
            
        elif texto_limpio == "main_publicar" or texto_limpio == "3":
            web_info = obtener_web_del_cliente(wa_id)
            slug = web_info["slug"] if web_info else "tu-negocio"
            
            msg = ("¡Excelente! 🚀 Para que tu web esté online y puedas compartirla, tenés 2 opciones:\n\n"
                   f"🎁 *OPCIÓN 1: Web 100% Gratis*\nTe activamos la página sin costo de por vida bajo nuestro dominio.\nTu link será: https://{slug}.tuweblista.com.ar\n\n"
                   "💎 *OPCIÓN 2: Web Profesional (.com.ar)*\nBuscamos y registramos un dominio a tu nombre. Costo: $8.500 (dominio anual) + $2.000 (abono mensual).\n\n"
                   "¿Qué opción preferís para arrancar?")
            buttons = [
                {"id": "DOMINIO_GRATIS", "title": "🎁 Usar dominio gratis"},
                {"id": "DOMINIO_SI", "title": "💎 Buscar Dominio"}
            ]
            send_whatsapp_buttons(wa_id, msg, buttons)
            set_user_state(wa_id, WAITING_FOR_DOMAIN_NAME)

    elif estado_actual == EDIT_MENU:
        if texto_limpio == "edit_titulo" or texto_limpio == "1":
            msg = ("Escribí el nuevo Título que querés para tu web (Por ejemplo: 'Estudio Jurídico Gonzalez').\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_TITLE)
        elif texto_limpio == "edit_subtitulo" or texto_limpio == "2":
            msg = ("Escribí el nuevo *Subtítulo*\n*(Por ejemplo: 'Más de 20 años ayudando a las personas'):*\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_SUBTITLE)
        elif texto_limpio == "edit_servicios" or texto_limpio == "3":
            msg = "¿Qué servicio querés editar?"
            options = [
                {"id": "EDIT_SRV_1", "title": "Servicio 1"},
                {"id": "EDIT_SRV_2", "title": "Servicio 2"},
                {"id": "EDIT_SRV_3", "title": "Servicio 3"},
                {"id": "EDIT_VOLVER", "title": "⬅️ Volver"}
            ]
            send_whatsapp_list(wa_id, msg, "Elegir Servicio", options, "Editar Servicios")
            set_user_state(wa_id, "EDIT_MENU_SERVICIOS")
        elif texto_limpio == "edit_location" or texto_limpio == "4":
            msg = ("Escribí la nueva Ubicación o Dirección (Por ejemplo: 'Avenida Corrientes 1000, CABA'. Mientras más exacto, mejor aparecerá en el mapa. También podés poner ciudad y provincia si no querés poner una dirección exacta).\n\n"
                   "💡 _Si no querés cambiarla ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_LOCATION)
        elif texto_limpio == "edit_schedule" or texto_limpio == "5":
            msg = ("Escribí tus *Horarios de Atención*\n*(Por ejemplo: 'Lunes a Viernes de 9 a 18hs').*\n\nSi no querés mostrar los horarios, escribí *Ocultar*.\n\n"
                   "💡 _Si no querés cambiarlos ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_SCHEDULE)
        elif texto_limpio == "edit_imagenes" or texto_limpio == "6":
            msg = ("💡 *Tamaños sugeridos:*\n"
                   "• *Foto Principal (Hero):* Horizontal apaisada (16:9) aprox 1920x1080 px.\n"
                   "• *Logo y Servicios:* Cuadradas (1:1) aprox 800x800 px.\n\n"
                   "📸 *¡Es súper fácil cambiar las fotos!*\n"
                   "Simplemente *enviame la foto por este chat ahora mismo* y te preguntaremos dónde querés ubicarla.\n\n"
                   "📲 _O tocá el botón abajo si preferís volver al panel de control:_")
            buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
            send_whatsapp_buttons(wa_id, msg, buttons)
            set_user_state(wa_id, IDLE, {})
        elif texto_limpio in ["edit_precios", "precios", "lista de precios", "7"]:
            mostrar_menu_precios(wa_id)
        elif texto_limpio == "edit_whatsapp":
            msg = ("Escribí el número de WhatsApp donde querés recibir las consultas de tus clientes (Ej: +54 9 1131234567 o 1131234567).\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_WHATSAPP)

        elif texto_limpio == "edit_email":
            msg = ("Escribí la dirección de correo electrónico que querés mostrar en la sección de contacto de tu web (Ej: info@empresa.com).\n\nSi no querés mostrar ningún correo, simplemente escribí *Ocultar*.\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_EMAIL)
        elif texto_limpio == "edit_instagram" or texto_limpio == "9":
            msg = ("Escribí tu usuario de Instagram (Ej: @minegocio) o pegá el enlace directo a tu perfil.\n\nSi no querés mostrar tu Instagram en la web, simplemente escribí *Ocultar*.\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_INSTAGRAM)

        elif texto_limpio == "edit_volver" or texto_limpio == "0":
            clear_user_state(wa_id)
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre) # Simulamos volver a entrar
        else:
            send_whatsapp_message(wa_id, "Por favor, elegí una opción de la lista.")
            
    elif estado_actual == "EDIT_MENU_SERVICIOS":
        if texto_limpio == "edit_srv_1" or texto_limpio == "1":
            msg = ("Escribí el nuevo *Título* para el Servicio 1:\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 0})
        elif texto_limpio == "edit_srv_2" or texto_limpio == "2":
            msg = ("Escribí el nuevo *Título* para el Servicio 2:\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 1})
        elif texto_limpio == "edit_srv_3" or texto_limpio == "3":
            msg = ("Escribí el nuevo *Título* para el Servicio 3:\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 2})
        elif texto_limpio == "edit_volver" or texto_limpio == "0":
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "2", nombre)
        else:
            send_whatsapp_message(wa_id, "Por favor, elegí un servicio de la lista.")
            
    elif estado_actual == "WAITING_FOR_SERVICE_TITLE":
        nuevo_titulo = texto.strip()
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["nuevo_titulo_srv"] = nuevo_titulo
        msg = ("Excelente. Ahora escribí la *Descripción* para este servicio\n"
               "*(Por ejemplo: 'Asesoramiento legal integral personalizado'):*\n\n"
               "💡 _Si no querés cambiarla ahora, escribí *cancelar* o *volver* para regresar al menú._")
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, "WAITING_FOR_SERVICE_DESC", current_data)
        
    elif estado_actual == "WAITING_FOR_SERVICE_DESC":
        nueva_desc = texto.strip()
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        idx = temp_data.get("servicio_idx", 0)
        nuevo_titulo = temp_data.get("nuevo_titulo_srv", "")
        
        can_edit, remaining = verificar_y_consumir_cuota(wa_id)
        if not can_edit:
            send_whatsapp_message(wa_id, "¡Ups! 🛑 Llegaste a tu límite de ediciones gratuitas de este mes.\n\nPara seguir haciendo cambios hoy, comunicate con el soporte tecnico.")
            set_user_state(wa_id, IDLE, {})
            return
            
        web_data = obtener_web_del_cliente(wa_id)
        if web_data:
            content = web_data["content"]
            if "servicios_sugeridos" not in content:
                content["servicios_sugeridos"] = ["", "", ""]
            if "descripciones_servicios" not in content:
                content["descripciones_servicios"] = ["", "", ""]
            
            content["servicios_sugeridos"][idx] = nuevo_titulo
            content["descripciones_servicios"][idx] = nueva_desc
            
            if actualizar_web_content(web_data["version_id"], content):
                msg = (f"✅ ¡Servicio actualizado con éxito!\n\n"
                       f"🔗 *Refrescá tu web para ver los cambios:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                       f"*(Te quedan {remaining} ediciones gratis)*")
            else:
                msg = "❌ Hubo un error al guardar."
        else:
            msg = "⚠️ No pude encontrar tu web."
            
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)
            
    elif estado_actual == WAITING_FOR_TITLE:
        nuevo_titulo = texto.strip()
        
        can_edit, remaining = verificar_y_consumir_cuota(wa_id)
        if not can_edit:
            msg = ("¡Ups! 🛑 Llegaste a tu límite de ediciones gratuitas de este mes.\n\n"
                   "Para seguir haciendo cambios hoy, comunicate con el soporte tecnico.")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, IDLE, {})
            return
            
        # Actualizar en BD
        web_data = obtener_web_del_cliente(wa_id)
        if web_data:
            content = web_data["content"]
            content["titulo_web"] = nuevo_titulo
            if actualizar_web_content(web_data["version_id"], content):
                msg = (f"✅ ¡Título actualizado con éxito a: '{nuevo_titulo}'!\n\n"
                       f"🔗 *Refrescá tu web para ver los cambios:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                       f"*(Te quedan {remaining} ediciones gratis este mes)*")
            else:
                msg = "❌ Hubo un error al guardar el título. Intentalo de nuevo."
        else:
            msg = "⚠️ No pude encontrar tu web en la base de datos (quizás fue creada como demo anónima)."
            
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)
        
    elif estado_actual == WAITING_FOR_SUBTITLE:
        nuevo_subtitulo = texto.strip()
        
        can_edit, remaining = verificar_y_consumir_cuota(wa_id)
        if not can_edit:
            msg = ("¡Ups! 🛑 Llegaste a tu límite de ediciones gratuitas de este mes.\n\n"
                   "Para seguir haciendo cambios hoy, comunicate con el soporte tecnico.")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, IDLE, {})
            return
            
        # Actualizar en BD
        web_data = obtener_web_del_cliente(wa_id)
        if web_data:
            content = web_data["content"]
            content["subtitulo"] = nuevo_subtitulo
            if actualizar_web_content(web_data["version_id"], content):
                msg = (f"✅ ¡Subtítulo actualizado con éxito!\n\n"
                       f"🔗 *Refrescá tu web para ver los cambios:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                       f"*(Te quedan {remaining} ediciones gratis este mes)*")
            else:
                msg = "❌ Hubo un error al guardar el subtítulo."
        else:
            msg = "⚠️ No pude encontrar tu web."
            
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)
        
    elif estado_actual == WAITING_FOR_LOCATION:
        nueva_ubicacion = texto.strip()
        can_edit, remaining = verificar_y_consumir_cuota(wa_id)
        if not can_edit:
            send_whatsapp_message(wa_id, "¡Ups! 🛑 Llegaste a tu límite de ediciones gratuitas de este mes.\n\nPara seguir haciendo cambios hoy, comunicate con el soporte tecnico.")
            set_user_state(wa_id, IDLE, {})
            return
            
        web_data = obtener_web_del_cliente(wa_id)
        if web_data:
            content = web_data["content"]
            content["ubicacion_detectada"] = nueva_ubicacion
            content["mapa"] = obtener_coordenadas(nueva_ubicacion)
            
            if actualizar_web_content(web_data["version_id"], content):
                msg = (f"✅ ¡Ubicación y Mapa actualizados con éxito!\n\n"
                       f"🔗 *Refrescá tu web para ver los cambios:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                       f"*(Te quedan {remaining} ediciones gratis)*")
            else:
                msg = "❌ Hubo un error al guardar."
        else:
            msg = "⚠️ No pude encontrar tu web."
            
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)
        
    elif estado_actual == WAITING_FOR_SCHEDULE:
        nuevo_horario = texto.strip()
        can_edit, remaining = verificar_y_consumir_cuota(wa_id)
        if not can_edit:
            send_whatsapp_message(wa_id, "¡Ups! 🛑 Llegaste a tu límite de ediciones gratuitas de este mes.\n\nPara seguir haciendo cambios hoy, comunicate con el soporte tecnico.")
            set_user_state(wa_id, IDLE, {})
            return
            
        web_data = obtener_web_del_cliente(wa_id)
        if web_data:
            content = web_data["content"]
            content["horario"] = texto_limpio if texto_limpio == "ocultar" else nuevo_horario
            if actualizar_web_content(web_data["version_id"], content):
                if texto_limpio == "ocultar":
                    msg = (f"✅ ¡Horarios ocultados con éxito!\n\n"
                           f"🔗 *Refrescá tu web para ver los cambios:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                           f"*(Te quedan {remaining} ediciones gratis)*")
                else:
                    msg = (f"✅ ¡Horarios actualizados con éxito!\n\n"
                           f"🔗 *Refrescá tu web para ver los cambios:* https://{web_data['slug']}.tuweblista.com.ar\n\n"
                           f"*(Te quedan {remaining} ediciones gratis)*")
            else:
                msg = "❌ Hubo un error al guardar."
        else:
            msg = "⚠️ No pude encontrar tu web."
            
        send_whatsapp_message(wa_id, msg)
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)
        
    elif estado_actual == WAITING_FOR_WHATSAPP:
        try:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("version_id"):
                c_id = web_info["version_id"]
                current_content = web_info["content"]
                current_content["whatsapp_contacto"] = texto
                
                if actualizar_web_content(c_id, current_content):
                    send_whatsapp_message(wa_id, f"✅ ¡Número de WhatsApp actualizado! Los clientes ahora te contactarán a ese número desde el botón de la web.\n\n🔗 *Refrescá tu web para ver los cambios:* https://{web_info['slug']}.tuweblista.com.ar")
                else:
                    send_whatsapp_message(wa_id, "⚠️ Hubo un error interno al actualizar el WhatsApp.")
            else:
                send_whatsapp_message(wa_id, "⚠️ Hubo un error al actualizar el WhatsApp.")
        except Exception as e:
            logging.error(f"Error actualizando whatsapp: {e}")
            send_whatsapp_message(wa_id, "❌ Error al actualizar.")
        
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)

    elif estado_actual == WAITING_FOR_EMAIL:
        try:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("version_id"):
                c_id = web_info["version_id"]
                current_content = web_info["content"]
                current_content["email_contacto"] = texto_limpio if texto_limpio == "ocultar" else texto
                
                if actualizar_web_content(c_id, current_content):
                    if texto_limpio == "ocultar":
                        send_whatsapp_message(wa_id, f"✅ ¡Correo electrónico ocultado de tu web!\n\n🔗 *Refrescá tu web para ver los cambios:* https://{web_info['slug']}.tuweblista.com.ar")
                    else:
                        send_whatsapp_message(wa_id, f"✅ ¡Email de contacto actualizado correctamente!\n\n🔗 *Refrescá tu web para ver los cambios:* https://{web_info['slug']}.tuweblista.com.ar")
                else:
                    send_whatsapp_message(wa_id, "⚠️ Hubo un error interno al actualizar el email.")
            else:
                send_whatsapp_message(wa_id, "⚠️ Hubo un error al actualizar el email.")
        except Exception as e:
            logging.error(f"Error actualizando email: {e}")
            send_whatsapp_message(wa_id, "❌ Error al actualizar.")
        
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)

    elif estado_actual == WAITING_FOR_INSTAGRAM:
        try:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("version_id"):
                c_id = web_info["version_id"]
                current_content = web_info["content"]
                
                # Limpiar el input si mandaron un @ o URL
                insta_input = texto.strip()
                if texto_limpio == "ocultar":
                    current_content["instagram"] = ""
                else:
                    if "instagram.com/" in insta_input:
                        # Extraer solo el username si es URL
                        partes = insta_input.split("instagram.com/")
                        if len(partes) > 1:
                            insta_input = partes[1].split("/")[0].split("?")[0]
                    elif insta_input.startswith("@"):
                        insta_input = insta_input[1:]
                    current_content["instagram"] = insta_input
                
                if actualizar_web_content(c_id, current_content):
                    if texto_limpio == "ocultar":
                        send_whatsapp_message(wa_id, f"✅ ¡Instagram ocultado de tu web!\n\n🔗 *Refrescá tu web para ver los cambios:* https://{web_info['slug']}.tuweblista.com.ar")
                    else:
                        send_whatsapp_message(wa_id, f"✅ ¡Instagram actualizado correctamente (@{current_content['instagram']})!\n\n🔗 *Refrescá tu web para ver los cambios:* https://{web_info['slug']}.tuweblista.com.ar")
                else:
                    send_whatsapp_message(wa_id, "⚠️ Hubo un error interno al actualizar el Instagram.")
            else:
                send_whatsapp_message(wa_id, "⚠️ Hubo un error al actualizar el Instagram.")
        except Exception as e:
            logging.error(f"Error actualizando instagram: {e}")
            send_whatsapp_message(wa_id, "❌ Error al actualizar.")
        
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "2", nombre)

    elif estado_actual == WAITING_FOR_DOMAIN_NAME:
        import subprocess
        
        dominio_limpio = texto_limpio.replace("https://", "").replace("http://", "").replace("www.", "").strip()
        if not dominio_limpio.endswith(".com.ar"):
            dominio_limpio += ".com.ar"
            
        send_whatsapp_message(wa_id, f"🔍 Buscando disponibilidad de *{dominio_limpio}* en NIC Argentina... aguardá unos segundos.")
        
        try:
            result = subprocess.run(["whois", dominio_limpio], capture_output=True, text=True, timeout=10)
            output = result.stdout
            
            if "El dominio no se encuentra registrado en NIC Argentina" in output:
                msg = (f"✅ ¡Buenas noticias! **{dominio_limpio}** ESTÁ DISPONIBLE.\n\n"
                       f"El costo de registrar un dominio en nic.ar a tu nombre es de $8.500 ARS anuales + $2.000 del abono mensual de la web (Total hoy: $10.500).\n\n"
                       "Para registrarlo y activar tu plan profesional, transferí los $10.500 al siguiente Alias:\n"
                       "*tuweblista*\n\n"
                       "Una vez que transfieras, envianos la foto del comprobante por acá y lo activaremos.")
                send_whatsapp_message(wa_id, msg)
                current_temp = get_user_state(wa_id).get("temp_data") or {}
                current_temp["dominio"] = dominio_limpio
                if "plan" not in current_temp:
                    current_temp["plan"] = "custom_domain"
                if "monto" not in current_temp:
                    current_temp["monto"] = 10500
                set_user_state(wa_id, WAITING_FOR_RECEIPT, current_temp)
            else:
                msg = (f"❌ Lo sentimos, **{dominio_limpio}** ya está registrado por otra persona.\n\n"
                       "¡Escribí otro nombre para volver a intentar!")
                send_whatsapp_message(wa_id, msg)
                # Sigue esperando otro nombre
        except Exception as e:
            logging.error(f"Error whois: {e}")
            send_whatsapp_message(wa_id, "⚠️ Hubo un error temporal conectando con NIC.ar. Por favor intentá en unos minutos.")

    elif estado_actual == WAITING_FOR_TRANSFER_PHONE:
        import random
        import sqlite3
        nuevo_numero = texto_limpio.replace("+", "").replace(" ", "").replace("-", "").strip()
        if not nuevo_numero.isdigit() or len(nuevo_numero) < 10:
            send_whatsapp_message(wa_id, "❌ El número no parece válido. Por favor ingresá solo números (Ej: 5491131234567).")
            return
            
        codigo_mudanza = f"MUDANZA-{random.randint(1000, 9999)}"
        
        try:
            db_path = os.path.join(os.getcwd(), "messages.db")
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS transfers
                         (code TEXT PRIMARY KEY, from_phone TEXT, to_phone TEXT, created_at TIMESTAMP)''')
            c.execute("INSERT INTO transfers (code, from_phone, to_phone, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                      (codigo_mudanza.lower(), wa_id, nuevo_numero))
            conn.commit()
            conn.close()
            
            msg = (f"¡Perfecto! Para confirmar el traspaso, por favor pedile al nuevo administrador ({nuevo_numero}) que me envíe un mensaje por WhatsApp diciendo exactamente esto:\n\n"
                   f"*{codigo_mudanza}*\n\n"
                   f"Una vez que reciba ese mensaje, la web se transferirá automáticamente.\n\n"
                   f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
            buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
            send_whatsapp_buttons(wa_id, msg, buttons)
            set_user_state(wa_id, IDLE, {})
        except Exception as e:
            logging.error(f"Error saving transfer: {e}")
            send_whatsapp_message(wa_id, "⚠️ Hubo un error al procesar la transferencia. Intentá nuevamente.")
            set_user_state(wa_id, IDLE, {})

    elif estado_actual == WAITING_FOR_ADMIN_MESSAGE:
        import sqlite3
        from datetime import datetime as dt
        db_path = os.path.join(os.getcwd(), "messages.db")
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS admin_messages
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      phone TEXT, 
                      name TEXT, 
                      message TEXT, 
                      reply TEXT, 
                      status TEXT, 
                      created_at TIMESTAMP)''')
        c.execute("INSERT INTO admin_messages (phone, name, message, status, created_at) VALUES (?, ?, ?, ?, ?)",
                  (wa_id, nombre, texto, 'pending', dt.now()))
        conn.commit()
        conn.close()
        
        msg_confirm = ("✅ Tu mensaje fue enviado con éxito. En el transcurso del día un administrador revisará tu consulta y te responderá por acá.\n\n"
                       "📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
        buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
        send_whatsapp_buttons(wa_id, msg_confirm, buttons)
        send_whatsapp_message("5491134710787", f"✉️ NUEVO MENSAJE DE {nombre} ({wa_id}):\n\n{texto}\n\nRevisá el dashboard para contestarle.")
        set_user_state(wa_id, IDLE, {})

    elif estado_actual == WAITING_FOR_RECEIPT:
        send_whatsapp_message(wa_id, "📸 Por favor, enviame la foto o captura del comprobante de transferencia por acá para que podamos verificarlo.\n\n(Si querés volver al menú principal, escribí *menu*)")

    elif estado_actual == WAITING_FOR_PRICE_LIST:
        if texto_limpio in ["quitar", "borrar", "eliminar", "ocultar"]:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("content") and "lista_precios" in web_info["content"] and web_info["content"]["lista_precios"]:
                content = web_info["content"]
                content.pop("lista_precios", None)
                actualizar_web_content(web_info["version_id"], content)
                slug = web_info.get("slug", "mi-web")
                page_url = f"https://{web_info['custom_domain']}" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar"
                msg = (f"🗑️ ¡Listo! Tu lista de precios fue eliminada de tu web y ya no aparece publicada.\n\n"
                       f"🔗 Refrescá tu página para ver los cambios: {page_url}")
                send_whatsapp_message(wa_id, msg)
            else:
                send_whatsapp_message(wa_id, "ℹ️ Tu web no tenía ninguna lista de precios publicada.")
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
            return

        send_whatsapp_message(wa_id, "⏳ Analizando tu lista de precios... aguardá unos segundos.")
        try:
            parsed = parse_price_list(texto, is_text=True)
            if parsed and parsed.get("items"):
                procesar_borrador_lista_precios(wa_id, parsed, nombre)
            else:
                send_whatsapp_message(wa_id, "⚠️ No pude detectar una lista de precios en el texto. Asegurate de incluir nombres de servicios y montos (por ejemplo: 'Corte $15.000 / Barba $8.000').")
        except Exception as e:
            logging.error(f"Error parseando texto de precios: {e}")
            send_whatsapp_message(wa_id, "❌ Hubo un error al procesar el texto. Por favor reintentá.")

    elif estado_actual == CONFIRM_PRICE_LIST_DRAFT:
        if texto_limpio in ["confirm_prices_ok", "publicar", "si", "sí", "confirmar", "1", "ok"]:
            user_session = get_user_state(wa_id)
            temp_data = user_session.get("temp_data", {})
            draft_prices = temp_data.get("draft_prices")
            
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and draft_prices:
                content = web_info["content"]
                content["lista_precios"] = draft_prices
                if actualizar_web_content(web_info["version_id"], content):
                    clear_user_state(wa_id)
                    if web_info.get("custom_domain"):
                        public_url = f"https://{web_info['custom_domain']}/precios"
                    else:
                        slug = web_info.get("slug", "mi-web")
                        public_url = f"https://{slug}.tuweblista.com.ar/precios"
                    msg = (f"✅ ¡Lista de precios publicada con éxito! 🎉\n\n"
                           f"Tus clientes ya pueden ver tus precios actualizados en:\n"
                           f"🔗 {public_url}\n\n"
                           f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                    buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                    send_whatsapp_buttons(wa_id, msg, buttons)
                else:
                    send_whatsapp_message(wa_id, "❌ Hubo un error al guardar tu lista de precios en la base de datos.")
            else:
                send_whatsapp_message(wa_id, "⚠️ No se encontró el borrador o los datos de tu web. Por favor reintentá cargando la lista.")
                clear_user_state(wa_id)
        elif texto_limpio in ["confirm_prices_cancel", "cancelar", "no", "descartar", "2"]:
            clear_user_state(wa_id)
            send_whatsapp_message(wa_id, "❌ Publicación cancelada. El borrador fue descartado y tus precios no sufrieron modificaciones.")
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        else:
            send_whatsapp_message(wa_id, "Por favor respondé *Publicar* para confirmar la subida a tu web o *Cancelar* para descartar el borrador.")

    elif estado_actual == WAITING_FOR_PRICE_MENU_OPTION:
        if texto_limpio in ["precios_actualizar", "actualizar", "actualizar precios", "1"]:
            msg = ("📋 *Actualización de Lista de Precios*\n\n"
                   "Podés enviarme:\n"
                   "1️⃣ Un archivo Excel (.xlsx) o CSV.\n"
                   "2️⃣ Un archivo PDF con tus precios.\n"
                   "3️⃣ Una foto nítida de tu lista o pizarra de precios.\n"
                   "4️⃣ O directamente escribir/pegar tu lista acá por texto (Ej: Corte $15.000 / Barba $8.000).\n\n"
                   "¿Cómo preferís enviármela?\n\n"
                   "💡 _(Escribí *cancelar* o *volver* para regresar al menú anterior)_")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_PRICE_LIST, {})
        elif texto_limpio in ["promo_fecha_start", "promo", "promocion", "promo por fecha", "2"]:
            web_info = obtener_web_del_cliente(wa_id)
            if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
                send_whatsapp_message(wa_id, "⚠️ Necesitás tener una lista de precios publicada antes de configurar una promoción.")
                set_user_state(wa_id, MAIN_MENU, {})
                procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
                return
            msg = ("📅 *Promoción por Fecha / Reserva Anticipada*\n\n"
                   "Paso 1 de 4: ¿Qué nombre o título querés ponerle al evento o jornada?\n"
                   "(Por ejemplo: 'Jornada Láser 17 de Noviembre' o 'Jornada Especial').\n\n"
                   "💡 _Escribí *cancelar* para volver al menú anterior._")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_PROMO_TITLE, {})
        elif texto_limpio in ["promo_detener", "detener promo", "frenar promo", "pausar promo", "detener", "3"]:
            detener_promocion_activa(wa_id, nombre)
        elif texto_limpio in ["precios_quitar", "quitar", "borrar", "eliminar", "ocultar", "4"]:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("content") and "lista_precios" in web_info["content"] and web_info["content"]["lista_precios"]:
                content = web_info["content"]
                content.pop("lista_precios", None)
                actualizar_web_content(web_info["version_id"], content)
                slug = web_info.get("slug", "mi-web")
                page_url = f"https://{web_info['custom_domain']}" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar"
                msg = (f"🗑️ ¡Listo! Tu lista de precios fue eliminada de tu web y ya no aparece publicada.\n\n"
                       f"🔗 Refrescá tu página para ver los cambios: {page_url}")
                send_whatsapp_message(wa_id, msg)
            else:
                send_whatsapp_message(wa_id, "ℹ️ Tu web no tenía ninguna lista de precios publicada.")
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        elif texto_limpio in ["precios_volver", "volver", "cancelar", "5"]:
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        else:
            send_whatsapp_message(wa_id, "Por favor, elegí una opción de la lista de gestión de precios o escribí *volver*.")

    elif estado_actual == WAITING_FOR_PROMO_TITLE:
        promo_title = texto.strip()
        temp_data = {"promo_title": promo_title}
        set_user_state(wa_id, WAITING_FOR_PROMO_DISCOUNT_1, temp_data)
        msg = ("🎯 Paso 2 de 4: ¿De cuánto es el porcentaje de descuento inicial por reserva anticipada?\n\n"
               "Escribí solo el número (Por ejemplo: 30 para 30% OFF):")
        send_whatsapp_message(wa_id, msg)

    elif estado_actual == WAITING_FOR_PROMO_DISCOUNT_1:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_message(wa_id, "⚠️ Por favor, ingresá un porcentaje válido entre 1 y 99 (por ejemplo: 30 para 30% OFF):")
            return
        desc_1 = int(clean_num)
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["promo_desc_1"] = desc_1
        set_user_state(wa_id, WAITING_FOR_PROMO_DATE_1, current_data)
        msg = (f"⏳ Paso 3 de 4: ¿Hasta qué fecha es válido ese {desc_1}% OFF inicial?\n\n"
               "Escribí la fecha completa con día, mes y año (Por ejemplo: 27/10/2026):")
        send_whatsapp_message(wa_id, msg)

    elif estado_actual == WAITING_FOR_PROMO_DATE_1:
        parsed_date = parse_promo_date(texto)
        if not parsed_date:
            send_whatsapp_message(wa_id, "⚠️ No pude entender la fecha. Por favor escribí la fecha completa con día, mes y año (Por ejemplo: 27/10/2026):")
            return
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["promo_date_1_iso"] = parsed_date["iso"]
        current_data["promo_date_1_display"] = parsed_date["display"]
        set_user_state(wa_id, WAITING_FOR_PROMO_TIER2_CHOICE, current_data)
        msg = (f"¿Querés agregar un 2do tramo con menor descuento antes de la fecha final?\n\n"
               f"(Por ejemplo: 15% OFF después del {parsed_date['display']})")
        buttons = [
            {"id": "PROMO_T2_YES", "title": "➕ Sí, agregar tramo"},
            {"id": "PROMO_T2_NO", "title": "🚀 No, solo este"}
        ]
        send_whatsapp_buttons(wa_id, msg, buttons)

    elif estado_actual == WAITING_FOR_PROMO_TIER2_CHOICE:
        if texto_limpio in ["promo_t2_no", "no", "solo este", "1", "no agregar", "no, solo este"]:
            current_data = get_user_state(wa_id).get("temp_data", {})
            generar_borrador_promocion(wa_id, current_data, nombre)
        elif texto_limpio in ["promo_t2_yes", "si", "sí", "agregar", "2", "si agregar", "agregar tramo", "si, agregar tramo"]:
            current_data = get_user_state(wa_id).get("temp_data", {})
            desc_1 = current_data.get("promo_desc_1", 30)
            set_user_state(wa_id, WAITING_FOR_PROMO_DISCOUNT_2, current_data)
            msg = (f"🎯 Paso 4 de 4: ¿De cuánto es el porcentaje de descuento para el 2do tramo?\n\n"
                   f"Debe ser menor al {desc_1}% (Por ejemplo: 15 para 15% OFF):")
            send_whatsapp_message(wa_id, msg)
        else:
            buttons = [
                {"id": "PROMO_T2_YES", "title": "➕ Sí, agregar tramo"},
                {"id": "PROMO_T2_NO", "title": "🚀 No, solo este"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor seleccioná si deseás agregar un segundo tramo con menor descuento:", buttons)

    elif estado_actual == WAITING_FOR_PROMO_DISCOUNT_2:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_message(wa_id, "⚠️ Por favor, ingresá un porcentaje válido entre 1 y 99 (por ejemplo: 15 para 15% OFF):")
            return
        desc_2 = int(clean_num)
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["promo_desc_2"] = desc_2
        set_user_state(wa_id, WAITING_FOR_PROMO_DATE_2, current_data)
        date_1_display = current_data.get("promo_date_1_display", "")
        msg = (f"⏳ ¿Hasta qué fecha límite es válido este {desc_2}% OFF?\n\n"
               f"Debe ser posterior al {date_1_display} (Por ejemplo: 15/11/2026):")
        send_whatsapp_message(wa_id, msg)

    elif estado_actual == WAITING_FOR_PROMO_DATE_2:
        parsed_date = parse_promo_date(texto)
        if not parsed_date:
            send_whatsapp_message(wa_id, "⚠️ No pude entender la fecha. Por favor escribí la fecha completa con día, mes y año (Por ejemplo: 15/11/2026):")
            return
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["promo_date_2_iso"] = parsed_date["iso"]
        current_data["promo_date_2_display"] = parsed_date["display"]
        generar_borrador_promocion(wa_id, current_data, nombre)

    elif estado_actual == CONFIRM_PROMO_DRAFT:
        if texto_limpio in ["confirm_promo_ok", "si", "sí", "activar", "publicar", "1", "ok", "confirmar"]:
            user_session = get_user_state(wa_id)
            temp_data = user_session.get("temp_data", {})
            promocion_data = temp_data.get("promocion_data")
            
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and promocion_data:
                content = web_info["content"]
                if "lista_precios" in content and isinstance(content["lista_precios"], dict):
                    content["lista_precios"]["promocion_fecha"] = promocion_data
                    if actualizar_web_content(web_info["version_id"], content):
                        clear_user_state(wa_id)
                        slug = web_info.get("slug", "mi-web")
                        public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"
                        msg = (f"🎉 ¡Promoción activada y publicada con éxito en tu web!\n\n"
                               f"Tus clientes ya verán los precios tachados, el banner de jornada y los descuentos en vivo.\n\n"
                               f"🔗 {public_url}\n\n"
                               f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                        buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                        send_whatsapp_buttons(wa_id, msg, buttons)
                    else:
                        send_whatsapp_message(wa_id, "❌ Hubo un error al guardar la promoción en la base de datos.")
                else:
                    send_whatsapp_message(wa_id, "⚠️ Tu web no cuenta con una lista de precios base válida.")
                    clear_user_state(wa_id)
            else:
                send_whatsapp_message(wa_id, "⚠️ No se encontró el borrador de la promoción o los datos de tu web. Por favor reintentá.")
                clear_user_state(wa_id)
        elif texto_limpio in ["confirm_promo_cancel", "cancelar", "no", "descartar", "2"]:
            clear_user_state(wa_id)
            send_whatsapp_message(wa_id, "❌ Publicación cancelada. El borrador de la promoción fue descartado y tus precios no sufrieron modificaciones.")
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        else:
            send_whatsapp_message(wa_id, "Por favor respondé *Activar* para confirmar la subida de la promo o *Cancelar* para descartar el borrador.")

    else:
        # Fallback si estamos en IDLE
        if estado_actual == IDLE:
            send_whatsapp_message(wa_id, "Hola 👋. Escribí la palabra *menu* para ver las opciones disponibles.")

