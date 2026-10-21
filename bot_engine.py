import os
import re
import json
import sqlite3
import requests
import secrets
from dotenv import load_dotenv
from supabase import create_client
from sender import send_whatsapp_message, send_whatsapp_image, download_whatsapp_media, send_whatsapp_buttons, send_whatsapp_list
from scripts.utils.price_list_parser import parse_price_list, format_price
import logging
import uuid
from datetime import datetime, date

logging.basicConfig(level=logging.INFO)

load_dotenv()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key) if supabase_url and supabase_key else None

ADMIN_PHONE = os.getenv("ADMIN_PHONE", "5491134710787")

def is_admin_phone(phone: str) -> bool:
    """Verifica si un número de teléfono corresponde al Administrador."""
    if not phone:
        return False
    clean = re.sub(r'[^\d]', '', str(phone))
    admin_clean = re.sub(r'[^\d]', '', str(ADMIN_PHONE))
    return len(clean) >= 10 and len(admin_clean) >= 10 and clean[-10:] == admin_clean[-10:]


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
WAITING_FOR_PROMO_ZONAS_DISCOUNT_1 = "WAITING_FOR_PROMO_ZONAS_DISCOUNT_1"
WAITING_FOR_PROMO_ZONAS_TIER2_CHOICE = "WAITING_FOR_PROMO_ZONAS_TIER2_CHOICE"
WAITING_FOR_PROMO_ZONAS_DISCOUNT_2 = "WAITING_FOR_PROMO_ZONAS_DISCOUNT_2"
WAITING_FOR_PROMO_ZONAS_ACUMULABLE = "WAITING_FOR_PROMO_ZONAS_ACUMULABLE"
CONFIRM_PROMO_ZONAS_DRAFT = "CONFIRM_PROMO_ZONAS_DRAFT"
WAITING_FOR_STOP_PROMO_CHOICE = "WAITING_FOR_STOP_PROMO_CHOICE"
WAITING_FOR_ADJUST_SELECTION = "WAITING_FOR_ADJUST_SELECTION"
WAITING_FOR_ADJUST_TYPE_ALL = "WAITING_FOR_ADJUST_TYPE_ALL"
WAITING_FOR_ADJUST_PERCENT_VALUE = "WAITING_FOR_ADJUST_PERCENT_VALUE"
WAITING_FOR_SINGLE_PRODUCT_ACTION = "WAITING_FOR_SINGLE_PRODUCT_ACTION"
WAITING_FOR_EXACT_PRICE_VALUE = "WAITING_FOR_EXACT_PRICE_VALUE"
WAITING_FOR_PROD_PROMO_PERCENT = "WAITING_FOR_PROD_PROMO_PERCENT"
WAITING_FOR_MULTI_PRODUCT_ACTION = "WAITING_FOR_MULTI_PRODUCT_ACTION"
CONFIRM_PRICE_ADJUST_DRAFT = "CONFIRM_PRICE_ADJUST_DRAFT"

# Botón interactivo universal para evitar dead-ends
BTN_VOLVER_MENU = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
btn_volver_menu = BTN_VOLVER_MENU


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
        c.execute("""
            CREATE TABLE IF NOT EXISTS opt_outs (
                phone TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    except Exception as e:
        logging.error(f"Error al inicializar tablas SQLite en {get_db_path()}: {e}")
    finally:
        if conn:
            conn.close()


# Inicializar la tabla al cargar el módulo
init_sessions_db()


def is_opted_out(phone) -> bool:
    """Verifica si un número telefónico está en la lista de opt-outs (no contactar)."""
    if not phone:
        return False
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return False
    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("SELECT phone FROM opt_outs WHERE phone = ? OR phone LIKE ?", 
                  (digits, f"%{digits[-10:]}" if len(digits) >= 10 else digits))
        return c.fetchone() is not None
    except Exception as e:
        logging.error(f"Error consultando opt_outs para {phone}: {e}")
        return False
    finally:
        if conn:
            conn.close()


def register_opt_out(phone) -> bool:
    """Registra un número telefónico en la lista de opt-outs."""
    if not phone:
        return False
    digits = re.sub(r'\D', '', str(phone))
    if not digits:
        return False
    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO opt_outs (phone) VALUES (?)", (digits,))
        conn.commit()
        logging.info(f"Registrado opt-out para {digits}")
        return True
    except Exception as e:
        logging.error(f"Error registrando opt_out para {phone}: {e}")
        return False
    finally:
        if conn:
            conn.close()


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
    Preserva admin_active_web_id si el usuario es el Administrador.
    """
    clean_wa_id = str(wa_id).strip()
    current_temp = user_states.get(clean_wa_id, {}).get("temp_data", {})
    admin_active_web_id = current_temp.get("admin_active_web_id") if is_admin_phone(clean_wa_id) else None

    new_temp = {"admin_active_web_id": admin_active_web_id} if admin_active_web_id else {}
    user_states[clean_wa_id] = {"estado": IDLE, "temp_data": new_temp}

    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        if admin_active_web_id:
            c.execute("""
                INSERT OR REPLACE INTO user_sessions (phone, estado, temp_data, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (clean_wa_id, IDLE, json.dumps(new_temp)))
        else:
            c.execute("DELETE FROM user_sessions WHERE phone = ?", (clean_wa_id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Error al limpiar user_state para {clean_wa_id} en SQLite: {e}")
    finally:
        if conn:
            conn.close()

def obtener_web_del_cliente(phone):
    """Busca la web actual del cliente en Supabase usando su teléfono o el contexto activo del admin."""
    if not supabase:
        return None
    try:
        # Caso A: Si es el Administrador y tiene una web activa fijada en sesión
        if is_admin_phone(phone):
            user_session = get_user_state(phone)
            active_web_id = user_session.get("temp_data", {}).get("admin_active_web_id")
            if not active_web_id and phone != ADMIN_PHONE:
                user_session_alt = get_user_state(ADMIN_PHONE)
                active_web_id = user_session_alt.get("temp_data", {}).get("admin_active_web_id")

            if active_web_id:
                web_res = supabase.table("websites").select("id, subdomain, custom_domain, client_id").eq("id", active_web_id).execute()
                if web_res.data:
                    w = web_res.data[0]
                    website_id = w["id"]
                    slug = w["subdomain"]
                    custom_domain = w.get("custom_domain")
                    client_id = w.get("client_id")

                    client_name = "Cliente"
                    client_phone = None
                    if client_id:
                        cli_res = supabase.table("clients").select("id, name, phone").eq("id", client_id).execute()
                        if cli_res.data:
                            client_name = cli_res.data[0].get("name", "Cliente")
                            client_phone = cli_res.data[0].get("phone")

                    ver_res = supabase.table("website_content").select("id, content").eq("website_id", website_id).execute()
                    if ver_res.data:
                        return {
                            "id": website_id,
                            "website_id": website_id,
                            "version_id": ver_res.data[0]["id"],
                            "content": json.loads(ver_res.data[0]["content"]) if isinstance(ver_res.data[0]["content"], str) else ver_res.data[0]["content"],
                            "slug": slug,
                            "custom_domain": custom_domain,
                            "client_id": client_id,
                            "client_name": client_name,
                            "client_phone": client_phone
                        }

        # Caso B: Cliente regular (o admin sin web activa en sesión)
        clean_phone = str(phone).replace("+", "").strip()
        base_phone = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
        cli_res = supabase.table("clients").select("id, name, phone").ilike("phone", f"%{base_phone}").execute()

        if not cli_res.data:
            return None

        client_data = cli_res.data[0]
        client_id = client_data["id"]
        client_name = client_data.get("name", "Cliente")
        client_phone = client_data.get("phone", phone)

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
                "id": website_id,
                "website_id": website_id,
                "version_id": ver_res.data[0]["id"],
                "content": json.loads(ver_res.data[0]["content"]) if isinstance(ver_res.data[0]["content"], str) else ver_res.data[0]["content"],
                "slug": slug,
                "custom_domain": custom_domain,
                "client_id": client_id,
                "client_name": client_name,
                "client_phone": client_phone
            }
    except Exception as e:
        logging.error(f"Error al buscar web en BD: {e}")
    return None

def notificar_cliente_cambio_publicado(wa_id_editor, web_info, descripcion_cambio):
    """
    Si el cambio fue realizado por el Super-Admin en una web ajena,
    notifica automáticamente al titular del comercio con su link.
    """
    if not is_admin_phone(wa_id_editor):
        return  # Si el cliente editó su propia web, no hace falta mandarle mensaje extra

    if not web_info or not isinstance(web_info, dict):
        return

    client_phone = web_info.get("client_phone")
    if not client_phone:
        return

    # Verificar que el teléfono del cliente no sea el mismo del admin
    if is_admin_phone(client_phone):
        return

    try:
        client_name = web_info.get("client_name", "Hola")
        slug = web_info.get("slug", "tu-web")
        custom_domain = web_info.get("custom_domain")
        public_url = f"https://{custom_domain}" if custom_domain else f"https://{slug}.tuweblista.com.ar"

        msg_cliente = (
            f"¡Hola {client_name}! 👋\n\n"
            f"Te avisamos que el cambio en tu página web (*{descripcion_cambio}*) ya fue realizado con éxito y se encuentra publicado. 🚀\n\n"
            f"🔗 *Mirá cómo quedó acá:*\n{public_url}"
        )
        send_whatsapp_message(client_phone, msg_cliente)
    except Exception as e:
        logging.error(f"Error al notificar al cliente sobre cambio publicado: {e}")

def fijar_web_activa_admin(wa_id, website_id, web_data=None):
    """Fija la web activa en el contexto de sesión del Administrador y envía confirmación con botones rápidos."""
    if not supabase:
        send_whatsapp_message(wa_id, "⚠️ No hay conexión con la base de datos.")
        return False
    try:
        if not web_data:
            res = supabase.table("websites").select("id, subdomain, seo_title, custom_domain, client_id").eq("id", website_id).execute()
            if not res.data:
                send_whatsapp_message(wa_id, "⚠️ No se encontró la web solicitada.")
                return False
            web_data = res.data[0]

        slug = web_data.get("subdomain", "sin-slug")
        nombre_web = web_data.get("seo_title") or slug
        client_id = web_data.get("client_id")

        nombre_cliente = "Sin registrar"
        telefono_cliente = "Sin registrar"
        if client_id:
            cli_res = supabase.table("clients").select("name, phone").eq("id", client_id).execute()
            if cli_res.data:
                nombre_cliente = cli_res.data[0].get("name", nombre_cliente)
                telefono_cliente = cli_res.data[0].get("phone", telefono_cliente)

        # Guardar en user_sessions.temp_data["admin_active_web_id"]
        current_state = get_user_state(wa_id)
        temp = current_state.get("temp_data", {})
        temp["admin_active_web_id"] = str(website_id)
        set_user_state(wa_id, IDLE, temp)

        url = f"https://{web_data['custom_domain']}" if web_data.get("custom_domain") else f"https://{slug}.tuweblista.com.ar"

        msg = (f"🔄 *Web Activa Seleccionada:*\n"
               f"🏪 *Comercio:* {nombre_web} ({slug})\n"
               f"👤 *Titular:* {nombre_cliente} ({telefono_cliente})\n"
               f"🌐 {url}\n\n"
               f"A partir de ahora, todas las fotos, precios, textos y configuraciones se aplicarán a este sitio.")

        buttons = [
            {"id": "main_precios", "title": "📋 Precios/Promos"},
            {"id": "main_editar", "title": "🛠️ Textos/Fotos"},
            {"id": "btn_menu", "title": "📱 Menú Completo"}
        ]
        send_whatsapp_buttons(wa_id, msg, buttons)
        return True
    except Exception as e:
        logging.error(f"Error fijando web activa para admin: {e}")
        send_whatsapp_message(wa_id, f"❌ Error al seleccionar web: {e}")
        return False

def mostrar_menu_edicion(wa_id):
    """Muestra el submenú de edición de contenidos para el sitio activo."""
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
            if lp.get("promocion_fecha") or lp.get("promocion_zonas"):
                tiene_promo = True

    if tiene_lista:
        options = [
            {"id": "PRECIOS_ACTUALIZAR", "title": "📄 Actualizar Precios", "description": "Subir nuevo Excel, PDF o texto"},
            {"id": "PRECIOS_AJUSTAR", "title": "✏️ Ajustar Precios/Promos", "description": "Aumentar, rebajar o poner promos a productos"},
            {"id": "PROMO_FECHA_START", "title": "📅 Promo por Fecha", "description": "Reserva anticipada con % de descuento"},
            {"id": "PROMO_ZONAS_START", "title": "🎯 Promo por Zonas", "description": "Descuento por cantidad de zonas"}
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
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        set_user_state(wa_id, WAITING_FOR_PRICE_LIST)

def detener_promocion_activa(wa_id, nombre):
    """Detiene y retira las promociones activas (fecha y/o zonas) de la web del cliente."""
    web_info = obtener_web_del_cliente(wa_id)
    if not web_info or not web_info.get("content"):
        send_whatsapp_message(wa_id, "⚠️ No encontramos tu página web en el sistema.")
        set_user_state(wa_id, MAIN_MENU, {})
        return False

    content = web_info["content"]
    lp = content.get("lista_precios")
    if not lp or not isinstance(lp, dict):
        send_whatsapp_message(wa_id, "ℹ️ Tu lista de precios no tiene ninguna promoción activa en este momento.")
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        return False

    tiene_fecha = bool(lp.get("promocion_fecha"))
    tiene_zonas = bool(lp.get("promocion_zonas"))

    if tiene_fecha and tiene_zonas:
        msg = ("🎯 *Detener Promociones Activas*\n\n"
               "Tenés activas tanto la *Promo por Fecha* como la *Promo por Zonas*.\n\n"
               "¿Cuál de ellas querés frenar?")
        buttons = [
            {"id": "frenar_promo_fecha", "title": "📅 Frenar Fecha"},
            {"id": "frenar_promo_zonas", "title": "🎯 Frenar Zonas"},
            {"id": "frenar_promo_ambas", "title": "🛑 Frenar Ambas"}
        ]
        send_whatsapp_buttons(wa_id, msg, buttons)
        set_user_state(wa_id, WAITING_FOR_STOP_PROMO_CHOICE, {})
        return True

    elif tiene_fecha:
        lp.pop("promocion_fecha", None)
        if actualizar_web_content(web_info["version_id"], content):
            notificar_cliente_cambio_publicado(wa_id, web_info, "promoción por fecha finalizada")
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

    elif tiene_zonas:
        lp.pop("promocion_zonas", None)
        if actualizar_web_content(web_info["version_id"], content):
            notificar_cliente_cambio_publicado(wa_id, web_info, "promoción por zonas finalizada")
            slug = web_info.get("slug", "mi-web")
            public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"
            msg = (f"⏹️ ¡Listo! La promoción por zonas fue detenida y retirada de tu web.\n\n"
                   f"Tus combos volvieron a sus valores regulares sin descuentos adicionales.\n\n"
                   f"🔗 Refrescá tu web: {public_url}\n\n"
                   f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
            buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
            send_whatsapp_buttons(wa_id, msg, buttons)
            set_user_state(wa_id, MAIN_MENU, {})
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

def generar_borrador_promocion_zonas(wa_id, temp_data, nombre):
    """
    Construye la estructura promocion_zonas, inyecta en draft_prices,
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

    desc_1 = temp_data.get("promo_zonas_desc_1", 10)
    has_tier2 = "promo_zonas_desc_2" in temp_data
    desc_2 = temp_data.get("promo_zonas_desc_2")
    bool_acumulable = temp_data.get("promo_zonas_acumulable", False)

    escalas = [
        {
            "cantidad": 2,
            "descuento": desc_1,
            "label": f"2 zonas: {desc_1}% OFF"
        }
    ]
    if has_tier2:
        escalas.append({
            "cantidad": 3,
            "descuento": desc_2,
            "label": f"3 o más zonas: {desc_2}% OFF"
        })

    promocion_zonas_data = {
        "titulo": "Promo Combos de Zonas",
        "activa": True,
        "acumulable": bool_acumulable,
        "escalas": escalas
    }

    draft_prices = json.loads(json.dumps(current_lp))
    draft_prices["promocion_zonas"] = promocion_zonas_data

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
        logging.error(f"Error guardando price_draft de promoción por zonas en SQLite: {e}")
    finally:
        if conn:
            conn.close()

    temp_data["draft_token"] = draft_token
    temp_data["draft_prices"] = draft_prices
    temp_data["promocion_zonas_data"] = promocion_zonas_data
    set_user_state(wa_id, CONFIRM_PROMO_ZONAS_DRAFT, temp_data)

    slug = web_info.get("slug", "mi-web")
    if web_info.get("custom_domain"):
        preview_url = f"https://{web_info['custom_domain']}/precios?preview={draft_token}"
    else:
        preview_url = f"https://{slug}.tuweblista.com.ar/precios?preview={draft_token}"

    tramo_2_txt = f"🟢 *Tramo 2:* 3 o más zonas ➔ {desc_2}% OFF\n" if has_tier2 else ""
    acum_txt = "Sí (se suma con promo por fecha)" if bool_acumulable else "No (aplica el descuento mayor)"

    msg = (f"🎉 *¡Borrador de Promo por Zonas generado!*\n\n"
           f"🎯 *Beneficio por Combos:*\n"
           f"🟢 *Tramo 1:* 2 zonas ➔ {desc_1}% OFF\n"
           f"{tramo_2_txt}"
           f"🔄 *Acumulable con fechas:* {acum_txt}\n\n"
           f"🔗 *Mirá cómo se ve tu promo y los precios en tu web:*\n"
           f"{preview_url}\n\n"
           f"¿Deseás activarla en tu web ahora mismo?")

    buttons = [
        {"id": "btn_activar_promo_zonas", "title": "✅ Activar Promo"},
        {"id": "btn_cancelar_promo_zonas", "title": "❌ Cancelar"}
    ]
    send_whatsapp_buttons(wa_id, msg, buttons)
    return True


def extract_numeric_price(val):
    """Extrae el valor numérico (float) de un string o número de precio."""
    if val is None:
        return 0.0
    val_str = str(val).strip()
    if not val_str or val_str in ["-", "nan", "none", "null"]:
        return 0.0
    cleaned = val_str.replace("$", "").replace("ARS", "").replace("USD", "").strip()
    try:
        if "," in cleaned and "." in cleaned:
            return float(cleaned.replace(".", "").replace(",", "."))
        elif "," in cleaned and "." not in cleaned:
            return float(cleaned.replace(",", "."))
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts[-1]) == 3:
                return float(cleaned.replace(".", ""))
            else:
                return float(cleaned)
        else:
            return float(cleaned)
    except Exception:
        digits = re.sub(r"[^\d]", "", val_str)
        return float(digits) if digits else 0.0


def round_clean_price(num):
    """Redondea importes al múltiplo de 50 o 100 más cercano para evitar números desprolijos."""
    if num <= 0:
        return 0
    if num >= 5000:
        return int(round(num / 100.0) * 100)
    elif num >= 100:
        return int(round(num / 50.0) * 50)
    return int(round(num))


def get_item_primary_price(item):
    """Obtiene el precio representativo (generalmente efectivo) para mostrar en listas."""
    if not isinstance(item, dict):
        return "-"
    precios = item.get("precios", {})
    if isinstance(precios, dict):
        if "efectivo" in precios and precios["efectivo"] and precios["efectivo"] != "-":
            return precios["efectivo"]
        for p in precios.values():
            if p and p != "-":
                return p
    elif isinstance(precios, (str, int, float)):
        return format_price(precios)
    return "-"


def iniciar_ajuste_precios(wa_id, nombre):
    """Inicia el asistente guiado para ajustar precios o promociones."""
    web_info = obtener_web_del_cliente(wa_id)
    if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios") or not web_info["content"]["lista_precios"].get("items"):
        send_whatsapp_message(wa_id, "⚠️ Necesitás tener una lista de precios publicada antes de poder ajustar precios o promociones.")
        set_user_state(wa_id, MAIN_MENU, {})
        procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        return False

    items = web_info["content"]["lista_precios"]["items"]
    lines = ["📋 *Tus Servicios y Precios Actuales:*\n"]
    num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, item in enumerate(items, 1):
        prefix = num_emoji[idx - 1] if idx <= 10 else f"{idx}️⃣"
        price_str = get_item_primary_price(item)
        promo_badge = f" (🏷️ {item['descuento']}% OFF)" if item.get("descuento") else ""
        lines.append(f"{prefix} *{item.get('servicio', 'Servicio')}:* {price_str}{promo_badge}")

    lines.append("\n👉 *¿Qué producto(s) deseás modificar?*")
    lines.append("• Escribí el número de un producto (ej: *1*).")
    lines.append("• O varios separados por coma (ej: *1, 3* o *1 y 3*).")
    lines.append("• O escribí *todos* para toda la lista.\n")
    lines.append("💡 _(Tocá el botón abajo para cancelar)_")

    msg = "\n".join(lines)
    send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
    set_user_state(wa_id, WAITING_FOR_ADJUST_SELECTION, {})
    return True


def guardar_y_enviar_borrador_ajuste(wa_id, web_info, draft_prices, resumen_ajuste, nombre):
    """Guarda el borrador de ajuste en price_drafts SQLite y envía mensaje con preview."""
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
        logging.error(f"Error guardando price_draft de ajuste en SQLite: {e}")
    finally:
        if conn:
            conn.close()

    temp_data = {
        "draft_token": draft_token,
        "draft_prices": draft_prices,
        "resumen_ajuste": resumen_ajuste
    }
    set_user_state(wa_id, CONFIRM_PRICE_ADJUST_DRAFT, temp_data)

    slug = web_info.get("slug", "mi-web")
    if web_info.get("custom_domain"):
        preview_url = f"https://{web_info['custom_domain']}/precios?preview={draft_token}"
    else:
        preview_url = f"https://{slug}.tuweblista.com.ar/precios?preview={draft_token}"

    msg = (f"🎉 *¡Borrador de Ajuste de Precios generado!*\n\n"
           f"{resumen_ajuste}\n\n"
           f"🔗 *Mirá cómo quedaron tus precios en tu web antes de publicar:*\n"
           f"{preview_url}\n\n"
           f"¿Deseás publicar estos cambios en tu web ahora mismo?")

    buttons = [
        {"id": "btn_adj_confirm", "title": "✅ Publicar Precios"},
        {"id": "btn_adj_cancel", "title": "❌ Cancelar"}
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

    # 1.1 Comandos Super-Admin Multisitio (solo si el emisor es el Administrador)
    if is_admin_phone(wa_id):
        # a. web actual / info web
        if texto_limpio in ["web actual", "info web", "web activa", "mi web actual"]:
            user_session = get_user_state(wa_id)
            active_web_id = user_session.get("temp_data", {}).get("admin_active_web_id")
            if active_web_id and supabase:
                try:
                    web_res = supabase.table("websites").select("id, subdomain, seo_title, custom_domain, client_id").eq("id", active_web_id).execute()
                    if web_res.data:
                        w = web_res.data[0]
                        slug = w.get("subdomain", "")
                        title = w.get("seo_title") or slug
                        c_name = "Sin titular"
                        c_phone = "Sin teléfono"
                        if w.get("client_id"):
                            cli_res = supabase.table("clients").select("name, phone").eq("id", w["client_id"]).execute()
                            if cli_res.data:
                                c_name = cli_res.data[0].get("name", c_name)
                                c_phone = cli_res.data[0].get("phone", c_phone)
                        url = f"https://{w['custom_domain']}" if w.get("custom_domain") else f"https://{slug}.tuweblista.com.ar"
                        msg = (f"🔄 *Web Activa Actualmente:*\n\n"
                               f"🏪 *Comercio:* {title} ({slug})\n"
                               f"👤 *Titular:* {c_name} ({c_phone})\n"
                               f"🌐 {url}\n\n"
                               f"Podés editarla con los botones de abajo o cambiar con *web <slug>* o *mis webs*.")
                        buttons = [
                            {"id": "main_precios", "title": "📋 Precios/Promos"},
                            {"id": "main_editar", "title": "🛠️ Textos/Fotos"},
                            {"id": "btn_menu", "title": "📱 Menú Completo"}
                        ]
                        send_whatsapp_buttons(wa_id, msg, buttons)
                        return
                except Exception as e:
                    logging.error(f"Error consultando web actual admin: {e}")
            send_whatsapp_message(wa_id, "ℹ️ No tenés ninguna web seleccionada actualmente.\n\nEscribí *mis webs* o *web <slug>* para seleccionar una.")
            return

        # b. deseleccionar / salir web
        if texto_limpio in ["web salir", "salir web", "deseleccionar web", "cerrar web"]:
            current_state = get_user_state(wa_id)
            temp = current_state.get("temp_data", {})
            temp.pop("admin_active_web_id", None)
            set_user_state(wa_id, IDLE, temp)
            send_whatsapp_message(wa_id, "ℹ️ Has deseleccionado la web activa. Ahora estás en tu contexto habitual.")
            return

        # c. mis webs / admin webs
        if texto_limpio in ["mis webs", "admin webs", "ver webs", "listar webs"]:
            if not supabase:
                send_whatsapp_message(wa_id, "⚠️ No hay conexión con la base de datos.")
                return
            try:
                web_res = supabase.table("websites").select("id, subdomain, seo_title, created_at").order("created_at", desc=True).limit(10).execute()
                if not web_res.data:
                    send_whatsapp_message(wa_id, "ℹ️ No se encontraron webs registradas en el sistema.")
                    return

                options = []
                for w in web_res.data:
                    w_id = w["id"]
                    slug = w.get("subdomain", "sin-slug")
                    title = w.get("seo_title") or slug
                    row_title = f"🏪 {slug}"[:24]
                    row_desc = str(title)[:72]
                    options.append({
                        "id": f"admin_select_{w_id}",
                        "title": row_title,
                        "description": row_desc
                    })

                msg = ("🏢 *Panel Super-Admin: Mis Webs*\n\n"
                       "Seleccioná una web de la lista para tomar el control y editar sus contenidos, fotos o precios:")
                send_whatsapp_list(wa_id, msg, "Seleccionar Web", options, "Últimas 10 Webs")
                return
            except Exception as e:
                logging.error(f"Error en comando mis webs: {e}")
                send_whatsapp_message(wa_id, f"❌ Error al consultar las webs: {e}")
                return

        # d. buscar <termino>
        if texto_limpio.startswith("buscar "):
            term = texto_limpio[7:].strip()
            if not term:
                send_whatsapp_message(wa_id, "⚠️ Por favor indicá el término a buscar (ej: *buscar panaderia*).")
                return
            if not supabase:
                send_whatsapp_message(wa_id, "⚠️ No hay conexión con la base de datos.")
                return
            try:
                res1 = supabase.table("websites").select("id, subdomain, seo_title").ilike("subdomain", f"%{term}%").limit(10).execute()
                res2 = supabase.table("websites").select("id, subdomain, seo_title").ilike("seo_title", f"%{term}%").limit(10).execute()

                found_map = {}
                for w in (res1.data or []):
                    found_map[w["id"]] = w
                for w in (res2.data or []):
                    found_map[w["id"]] = w

                results = list(found_map.values())[:10]
                if not results:
                    send_whatsapp_message(wa_id, f"🔍 No se encontraron webs con el término '{term}'.\n\nProbá con otra palabra o usá *mis webs*.")
                    return

                options = []
                for w in results:
                    w_id = w["id"]
                    slug = w.get("subdomain", "sin-slug")
                    title = w.get("seo_title") or slug
                    row_title = f"🏪 {slug}"[:24]
                    row_desc = str(title)[:72]
                    options.append({
                        "id": f"admin_select_{w_id}",
                        "title": row_title,
                        "description": row_desc
                    })

                msg = (f"🔍 *Resultados de Búsqueda ('{term}'):*\n\n"
                       "Tocá una web para seleccionarla como activa:")
                send_whatsapp_list(wa_id, msg, "Ver Coincidencias", options, "Resultados")
                return
            except Exception as e:
                logging.error(f"Error en comando buscar: {e}")
                send_whatsapp_message(wa_id, f"❌ Error al buscar webs: {e}")
                return

        # e. admin_select_<website_id>
        if texto_limpio.startswith("admin_select_"):
            target_id = texto_limpio.replace("admin_select_", "").strip()
            fijar_web_activa_admin(wa_id, target_id)
            return

        # f. web <slug> o slug <slug>
        is_web_cmd = (texto_limpio.startswith("web ") and texto_limpio not in ["web actual", "web activa", "web salir"]) or texto_limpio.startswith("slug ")
        if is_web_cmd:
            term = texto_limpio.split(maxsplit=1)[1].strip()
            if not term:
                send_whatsapp_message(wa_id, "⚠️ Por favor indicá el slug o nombre de la web (ej: *web panaderiasanpedro*).")
                return
            if not supabase:
                send_whatsapp_message(wa_id, "⚠️ No hay conexión con la base de datos.")
                return
            try:
                res = supabase.table("websites").select("id, subdomain, seo_title, custom_domain, client_id").ilike("subdomain", f"%{term}%").limit(5).execute()
                if not res.data:
                    res = supabase.table("websites").select("id, subdomain, seo_title, custom_domain, client_id").ilike("seo_title", f"%{term}%").limit(5).execute()

                if not res.data:
                    send_whatsapp_message(wa_id, f"⚠️ No encontramos ninguna web con el término '{term}'.\n\nPodés usar *buscar <texto>* o escribir *mis webs* para ver las últimas.")
                    return

                target_web = res.data[0]
                fijar_web_activa_admin(wa_id, target_web["id"], web_data=target_web)
                return
            except Exception as e:
                logging.error(f"Error buscando web para admin: {e}")
                send_whatsapp_message(wa_id, f"❌ Error al buscar la web: {e}")
                return

    # 1.3 Acceso directo a menús si el usuario pulsa botones rápidos desde IDLE
    if estado_actual == IDLE:
        if texto_limpio in ["main_precios", "precios", "promos", "promociones", "lista de precios"]:
            mostrar_menu_precios(wa_id)
            return
        elif texto_limpio in ["main_editar", "editar"]:
            mostrar_menu_edicion(wa_id)
            return

    # 1.4 Interceptar respuestas a la campaña Outbound ("propuesta_web_comercio")
    # 1.4.1 Opt-Out: [ ❌ No me interesa ]
    if "no me interesa" in texto_limpio or "no, por ahora no" in texto_limpio:
        register_opt_out(wa_id)
        clear_user_state(wa_id)
        msg_despedida = ("¡Entendido! Muchas gracias por tu respuesta y muchos éxitos con el negocio.\n\n"
                         "Si en algún momento necesitás tu página web, acá estamos a disposición. ¡Saludos! 👋")
        send_whatsapp_message(wa_id, msg_despedida)
        return

    # 1.4.2 Afirmativo: [ 🚀 Sí, me interesa ]
    if any(k in texto_limpio for k in ["si me interesa", "sí, me interesa", "me interesa"]):
        clear_user_state(wa_id)
        guia_msg = ("¡Excelente elección! 🎉 Nosotros nos encargamos de dejártela lista sin que tengas que aprender nada raro.\n\n"
                    "👉 ¿Por dónde querés arrancar?\n\n"
                    "1️⃣ Tus Precios: Mandanos una foto de tu pizarra, un archivo (Excel/PDF) o simplemente escribilos acá.\n"
                    "2️⃣ Tus Fotos: Mandanos las fotos de tu local o productos directo por este chat.\n"
                    "3️⃣ Dominio Propio: Si querés tu propio .com.ar (nosotros nos encargamos de todo el registro en NIC.ar por $8.500/año sin costo extra de mantenimiento), escribí el nombre acá (por ejemplo: mipanaderia) y te digo al instante si está disponible.\n"
                    "4️⃣ Dejarla activa como está: Decinos \"activar\" y te pasamos el Alias bancario para que abones los $2.000 mensuales.\n\n"
                    "¿Qué preferís hacer primero?")
        send_whatsapp_message(wa_id, guia_msg)

        # Alerta inmediata al Administrador
        web_info = obtener_web_del_cliente(wa_id)
        slug = web_info.get("slug", "sin-web") if web_info else "sin-web"
        admin_msg = (f"🔥 ¡PROSPECTO INTERESADO!\n"
                     f"👤 Comercio: {nombre} ({wa_id})\n"
                     f"🏪 Web: {slug}\n"
                     f"👉 Para tomar el control y editar esta web, respondé:\n"
                     f"web {slug}")
        send_whatsapp_message(ADMIN_PHONE, admin_msg)
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
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        return

    if is_trial_dominio:
        set_user_state(wa_id, WAITING_FOR_DOMAIN_NAME, {"plan": "custom_domain", "monto": 10500})
        msg = ("¡Excelente! 💎 Vamos a registrar tu propio dominio .com.ar.\n\n"
               "Escribí el nombre que te gustaría tener (por ejemplo: 'minegocio.com.ar' o 'minegocio'):")
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        return

    # 1.7 Interceptar intención de activación o reactivación de web ("activar", "reactivar mi web", "reactivar")
    if texto_limpio in ["activar", "activar mi web", "dejarla activa"] or "reactivar mi web" in texto_limpio or "reactivar" in texto_limpio:
        web_info = obtener_web_del_cliente(wa_id)
        accion = "reactivacion" if "reactivar" in texto_limpio else "activacion"
        verbo = "reactivarse" if "reactivar" in texto_limpio else "activarse"
        accion_txt = "volver a ponerla online" if "reactivar" in texto_limpio else "dejarla activa online"
        msg = (f"¡Hola {nombre}! 👋 Tu web está guardada y lista para {verbo}.\n\n"
               f"Para {accion_txt} hoy mismo por solo $2.000/mes (o con dominio .com.ar propio por $10.500), transferí el monto al siguiente Alias:\n"
               "*tuweblista*\n\n"
               "Una vez que transfieras, envianos la foto del comprobante por acá y la activaremos de inmediato. 🚀")
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        temp_data = {"accion": accion, "monto": 2000}
        if web_info:
            if "slug" in web_info:
                temp_data["slug"] = web_info["slug"]
            if "website_id" in web_info:
                temp_data["website_id"] = web_info["website_id"]
        set_user_state(wa_id, WAITING_FOR_RECEIPT, temp_data)
        return

    # 1.8 Interceptar intención de detener promoción activa ("detener promo", "frenar promo", "pausar promo")
    if estado_actual != WAITING_FOR_STOP_PROMO_CHOICE and any(k in texto_limpio for k in ["detener promo", "frenar promo", "pausar promo", "detener promocion", "pausar promocion"]):
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
                        send_whatsapp_buttons(wa_id, "⚠️ No pude detectar una lista de precios válida en el documento. Podés escribir *soporte* para que te ayudemos a cargarla, o probar enviándola en formato Excel, CSV o texto.", btn_volver_menu)
                except Exception as e:
                    logging.error(f"Error parseando documento de precios: {e}")
                    send_whatsapp_buttons(wa_id, "❌ No pudimos procesar el archivo. Podés escribir *soporte* para que lo carguemos juntos o probar enviarlo en formato Excel o CSV.", btn_volver_menu)
            else:
                send_whatsapp_buttons(wa_id, "❌ Hubo un error al descargar el archivo. Por favor intentá nuevamente.", btn_volver_menu)
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
            
            msg = ("✅ Recibimos el comprobante muchas gracias, en el transcurso del día recibirás una notificación con el 'Pago verificado'. Tu web va a seguir activa, no te preocupes.\n\n"
                   "📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, IDLE, {})
            
            logging.info(f"NUEVO PAGO: {nombre} ({wa_id}) mandó un comprobante.")
            send_whatsapp_message(ADMIN_PHONE, f"💰 NUEVO PAGO DE {nombre} ({wa_id}). Revisá el servidor.")
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
                        send_whatsapp_buttons(wa_id, "⚠️ No pude detectar precios legibles en la imagen. Probá con una foto más nítida o pegando el texto.", btn_volver_menu)
                except Exception as e:
                    logging.error(f"Error procesando imagen de precios: {e}")
                    send_whatsapp_buttons(wa_id, "❌ Error al procesar la imagen de precios.", btn_volver_menu)
            else:
                send_whatsapp_buttons(wa_id, "❌ Error al descargar la imagen.", btn_volver_menu)
            return
        else:
            if not is_admin_phone(wa_id) and estado_actual == IDLE:
                sla_msg = ("¡Recibido! 📸 Tu solicitud ya ingresó a la fila de edición y estará visible en tu web en el transcurso de las próximas 24 hs hábiles (Lunes a Viernes).\n\n"
                           "Te avisaremos por acá en cuanto esté publicado. 🚀")
                send_whatsapp_message(wa_id, sla_msg)
                web_info = obtener_web_del_cliente(wa_id)
                slug = web_info.get("slug", "sin-slug") if web_info else "sin-slug"
                admin_alert = (f"🔔 SOLICITUD DE CAMBIO RECIBIDA:\n"
                               f"👤 Cliente: {nombre} ({wa_id})\n"
                               f"🏪 Web: {slug}\n"
                               f"💬 Detalle: 📸 [Imagen adjunta]\n\n"
                               f"👉 Para tomar el control y editar esta web, respondé:\n"
                               f"web {slug}")
                send_whatsapp_message(ADMIN_PHONE, admin_alert)

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
                        notificar_cliente_cambio_publicado(wa_id, web_data, "nueva imagen")
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
                buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
            else:
                msg = ("⚠️ No encontramos una página web activa vinculada a tu número de teléfono.\n\n"
                       "📲 _Tocá el botón abajo o escribí *menu* para ver las opciones disponibles._")
                buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
        elif texto_limpio in ["main_precios", "precios", "promos", "promociones", "lista de precios"]:
            mostrar_menu_precios(wa_id)
        elif texto_limpio == "main_soporte" or texto_limpio == "main_contact":
            msg = ("Escribí el mensaje que le querés enviar al administrador.\n\n⚠️ *Aviso*: Esto no es un chat en vivo, pero tu mensaje quedará registrado y te responderemos por este mismo medio en el transcurso del día.\n\n💡 _Si no querés enviar ningún mensaje ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_ADMIN_MESSAGE)

        elif texto_limpio == "main_transfer":
            msg = ("🔄 *Transferir Administración*\n\n"
                   "Para transferir la administración de esta web a otro número, escribí acá abajo el nuevo número de WhatsApp (Ej: 1131234567 o +5491131234567).\n\n"
                   "⚠️ Importante: Una vez confirmada la transferencia, perderás acceso a este menú.\n\n"
                   "💡 _Si no querés transferirla ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_TRANSFER_PHONE)

        elif texto_limpio == "main_domain":
            msg = ("🌐 *Buscador Oficial de Dominios (.com.ar)*\n\n"
                   "Escribí acá abajo el nombre que te gustaría tener para tu página (Ej: mipanaderia, estudiojuridico, etc).\n\n"
                   "No hace falta que escribas el '.com.ar', nosotros lo agregamos y verificamos si está disponible en NIC Argentina al instante.\n\n"
                   "💡 _Si preferís hacerlo en otro momento, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_DOMAIN_NAME)
            
        elif texto_limpio in ["main_editar", "editar", "2"]:
            mostrar_menu_edicion(wa_id)
            
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
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_TITLE)
        elif texto_limpio == "edit_subtitulo" or texto_limpio == "2":
            msg = ("Escribí el nuevo *Subtítulo*\n*(Por ejemplo: 'Más de 20 años ayudando a las personas'):*\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
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
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_LOCATION)
        elif texto_limpio == "edit_schedule" or texto_limpio == "5":
            msg = ("Escribí tus *Horarios de Atención*\n*(Por ejemplo: 'Lunes a Viernes de 9 a 18hs').*\n\nSi no querés mostrar los horarios, escribí *Ocultar*.\n\n"
                   "💡 _Si no querés cambiarlos ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_SCHEDULE)
        elif texto_limpio == "edit_imagenes" or texto_limpio == "6":
            msg = ("💡 *Tamaños sugeridos:*\n"
                   "• *Foto Principal (Hero):* Horizontal apaisada (16:9) aprox 1920x1080 px.\n"
                   "• *Logo y Servicios:* Cuadradas (1:1) aprox 800x800 px.\n\n"
                   "📸 *¡Es súper fácil cambiar las fotos!*\n"
                   "Simplemente *enviame la foto por este chat ahora mismo* y te preguntaremos dónde querés ubicarla.\n\n"
                   "📲 _O tocá el botón abajo si preferís volver al panel de control:_")
            buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
            send_whatsapp_buttons(wa_id, msg, buttons)
            set_user_state(wa_id, IDLE, {})
        elif texto_limpio in ["edit_precios", "precios", "lista de precios", "7"]:
            mostrar_menu_precios(wa_id)
        elif texto_limpio == "edit_whatsapp":
            msg = ("Escribí el número de WhatsApp donde querés recibir las consultas de tus clientes (Ej: +54 9 1131234567 o 1131234567).\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_WHATSAPP)

        elif texto_limpio == "edit_email":
            msg = ("Escribí la dirección de correo electrónico que querés mostrar en la sección de contacto de tu web (Ej: info@empresa.com).\n\nSi no querés mostrar ningún correo, simplemente escribí *Ocultar*.\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_EMAIL)
        elif texto_limpio == "edit_instagram" or texto_limpio == "9":
            msg = ("Escribí tu usuario de Instagram (Ej: @minegocio) o pegá el enlace directo a tu perfil.\n\nSi no querés mostrar tu Instagram en la web, simplemente escribí *Ocultar*.\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
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
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 0})
        elif texto_limpio == "edit_srv_2" or texto_limpio == "2":
            msg = ("Escribí el nuevo *Título* para el Servicio 2:\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 1})
        elif texto_limpio == "edit_srv_3" or texto_limpio == "3":
            msg = ("Escribí el nuevo *Título* para el Servicio 3:\n\n"
                   "💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
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
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
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
                notificar_cliente_cambio_publicado(wa_id, web_data, "servicios actualizados")
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
                notificar_cliente_cambio_publicado(wa_id, web_data, "título de la web")
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
                notificar_cliente_cambio_publicado(wa_id, web_data, "subtítulo de la web")
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
                notificar_cliente_cambio_publicado(wa_id, web_data, "ubicación y mapa")
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
                notificar_cliente_cambio_publicado(wa_id, web_data, "horarios de atención")
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
                    notificar_cliente_cambio_publicado(wa_id, web_info, "número de WhatsApp de contacto")
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
                    notificar_cliente_cambio_publicado(wa_id, web_info, "email de contacto")
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
                    notificar_cliente_cambio_publicado(wa_id, web_info, "cuenta de Instagram")
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
            
            if "El dominio no se encuentra registrado en NIC Argentina" in output or "no match" in output.lower() or "disponible" in output.lower():
                current_temp = get_user_state(wa_id).get("temp_data") or {}
                monto = current_temp.get("monto", 8500)
                monto_str = f"${monto:,}".replace(",", ".") if monto != 8500 else "$8.500"
                msg = (f"¡Buenas noticias! {dominio_limpio} está disponible para registrarlo a tu nombre. 🎉\n\n"
                       f"Ese arancel de $8.500 anuales es el arancel oficial que cobra directamente el organismo nacional (NIC Argentina). Si lo hicieras por tu cuenta en AFIP te costaría exactamente lo mismo.\n\n"
                       f"🔗 Podés chequear el arancel oficial del gobierno acá:\n"
                       f"https://nic.ar/aranceles\n\n"
                       f"🎁 Nosotros te hacemos todo el trámite, alta y configuración técnica 100% GRATIS, sin ningún cargo extra. (El trámite entre que se abona el arancel y la web queda activa bajo tu .com.ar demora aproximadamente 48 hs por la delegación oficial de DNS).\n\n"
                       f"Para que lo registremos hoy mismo, transferí los {monto_str} al Alias:\n"
                       f"👉 tuweblista\n\n"
                       f"En cuanto nos mandes el comprobante por acá, te lo dejamos registrado y conectado a tu web. 🚀")
                send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
                current_temp["dominio"] = dominio_limpio
                if "plan" not in current_temp:
                    current_temp["plan"] = "custom_domain"
                current_temp["monto"] = monto
                set_user_state(wa_id, WAITING_FOR_RECEIPT, current_temp)
            else:
                msg = (f"❌ Lo sentimos, **{dominio_limpio}** ya está registrado por otra persona.\n\n"
                       "¡Escribí otro nombre para volver a intentar!")
                send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
                # Sigue esperando otro nombre
        except Exception as e:
            logging.error(f"Error whois: {e}")
            send_whatsapp_buttons(wa_id, "⚠️ Hubo un error temporal conectando con NIC.ar. Por favor intentá en unos minutos.", btn_volver_menu)

    elif estado_actual == WAITING_FOR_TRANSFER_PHONE:
        import random
        import sqlite3
        nuevo_numero = texto_limpio.replace("+", "").replace(" ", "").replace("-", "").strip()
        if not nuevo_numero.isdigit() or len(nuevo_numero) < 10:
            send_whatsapp_buttons(wa_id, "❌ El número no parece válido. Por favor ingresá solo números (Ej: 5491131234567).", btn_volver_menu)
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
            buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
            send_whatsapp_buttons(wa_id, msg, buttons)
            set_user_state(wa_id, IDLE, {})
        except Exception as e:
            logging.error(f"Error saving transfer: {e}")
            send_whatsapp_buttons(wa_id, "⚠️ Hubo un error al procesar la transferencia. Intentá nuevamente.", btn_volver_menu)
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
        buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
        send_whatsapp_buttons(wa_id, msg_confirm, buttons)
        send_whatsapp_message(ADMIN_PHONE, f"✉️ NUEVO MENSAJE DE {nombre} ({wa_id}):\n\n{texto}\n\nRevisá el dashboard para contestarle.")
        set_user_state(wa_id, IDLE, {})

    elif estado_actual == WAITING_FOR_RECEIPT:
        msg = ("📸 Por favor, enviame la foto o captura del comprobante de transferencia por acá para que podamos verificarlo.\n\n"
               "💡 _Tocá el botón abajo o escribí *menu* si preferís volver al menú principal._")
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)

    elif estado_actual == WAITING_FOR_PRICE_LIST:
        if texto_limpio in ["btn_go_adjust", "ajustar", "ajustar precios"]:
            iniciar_ajuste_precios(wa_id, nombre)
            return

        if texto_limpio in ["quitar", "borrar", "eliminar", "ocultar"]:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("content") and "lista_precios" in web_info["content"] and web_info["content"]["lista_precios"]:
                content = web_info["content"]
                content.pop("lista_precios", None)
                actualizar_web_content(web_info["version_id"], content)
                notificar_cliente_cambio_publicado(wa_id, web_info, "lista de precios retirada")
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

        # Protección anti-confusión: detectar intenciones humanas de ajuste antes del parser
        intenciones_ajuste = [
            "aumentar", "subir precio", "subir precios", "cambiar precio", "cambiar precios",
            "bajar precio", "bajar precios", "poner promo", "poner en promo", "descuento",
            "descuentos", "rebajar", "modificar precio", "modificar precios", "ajustar precio", "ajustar precios"
        ]
        if any(k in texto_limpio for k in intenciones_ajuste):
            msg = ("💡 Veo que querés ajustar precios o promociones de tu lista.\n\n"
                   "Podés entrar al asistente guiado o volver al menú principal:")
            buttons = [
                {"id": "btn_go_adjust", "title": "✏️ Ajustar Precios"},
                {"id": "btn_menu", "title": "📱 Menú Principal"}
            ]
            send_whatsapp_buttons(wa_id, msg, buttons)
            return

        send_whatsapp_message(wa_id, "⏳ Analizando tu lista de precios... aguardá unos segundos.")
        try:
            parsed = parse_price_list(texto, is_text=True)
            if parsed and parsed.get("items"):
                procesar_borrador_lista_precios(wa_id, parsed, nombre)
            else:
                send_whatsapp_buttons(wa_id, "⚠️ No pude detectar una lista de precios en el texto. Asegurate de incluir nombres de servicios y montos (por ejemplo: 'Corte $15.000 / Barba $8.000').", btn_volver_menu)
        except Exception as e:
            logging.error(f"Error parseando texto de precios: {e}")
            send_whatsapp_buttons(wa_id, "❌ Hubo un error al procesar el texto. Por favor reintentá.", btn_volver_menu)

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
                    notificar_cliente_cambio_publicado(wa_id, web_info, "lista de precios actualizada")
                    if web_info.get("custom_domain"):
                        public_url = f"https://{web_info['custom_domain']}/precios"
                    else:
                        slug = web_info.get("slug", "mi-web")
                        public_url = f"https://{slug}.tuweblista.com.ar/precios"
                    msg = (f"✅ ¡Lista de precios publicada con éxito! 🎉\n\n"
                           f"Tus clientes ya pueden ver tus precios actualizados en:\n"
                           f"🔗 {public_url}\n\n"
                           f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                    buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
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
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_PRICE_LIST, {})
        elif texto_limpio in ["precios_ajustar", "ajustar precios", "ajustar", "btn_go_adjust", "ajustar_precios"]:
            iniciar_ajuste_precios(wa_id, nombre)
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
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_PROMO_TITLE, {})
        elif texto_limpio in ["promo_zonas_start", "promo zonas", "zonas", "combos", "promo por zonas", "3"]:
            web_info = obtener_web_del_cliente(wa_id)
            if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
                send_whatsapp_message(wa_id, "⚠️ Necesitás tener una lista de precios publicada antes de configurar una promoción.")
                set_user_state(wa_id, MAIN_MENU, {})
                procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
                return
            msg = ("🎯 *Promoción por Cantidad de Zonas (Combos)*\n\n"
                   "Paso 1 de 3: ¿De cuánto es el porcentaje de descuento llevando *2 zonas o servicios*?\n\n"
                   "Escribí solo el número (Por ejemplo: 10 para 10% OFF):")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
            set_user_state(wa_id, WAITING_FOR_PROMO_ZONAS_DISCOUNT_1, {})
        elif texto_limpio in ["promo_detener", "detener promo", "frenar promo", "pausar promo", "detener", "4"]:
            detener_promocion_activa(wa_id, nombre)
        elif texto_limpio in ["precios_quitar", "quitar", "borrar", "eliminar", "ocultar", "4", "5"]:
            web_info = obtener_web_del_cliente(wa_id)
            if web_info and web_info.get("content") and "lista_precios" in web_info["content"] and web_info["content"]["lista_precios"]:
                content = web_info["content"]
                content.pop("lista_precios", None)
                actualizar_web_content(web_info["version_id"], content)
                notificar_cliente_cambio_publicado(wa_id, web_info, "lista de precios retirada")
                slug = web_info.get("slug", "mi-web")
                page_url = f"https://{web_info['custom_domain']}" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar"
                msg = (f"🗑️ ¡Listo! Tu lista de precios fue eliminada de tu web y ya no aparece publicada.\n\n"
                       f"🔗 Refrescá tu página para ver los cambios: {page_url}")
                send_whatsapp_message(wa_id, msg)
            else:
                send_whatsapp_message(wa_id, "ℹ️ Tu web no tenía ninguna lista de precios publicada.")
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        elif texto_limpio in ["precios_volver", "volver", "cancelar", "5", "6"]:
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
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)

    elif estado_actual == WAITING_FOR_PROMO_DISCOUNT_1:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_buttons(wa_id, "⚠️ Por favor, ingresá un porcentaje válido entre 1 y 99 (por ejemplo: 30 para 30% OFF):", btn_volver_menu)
            return
        desc_1 = int(clean_num)
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["promo_desc_1"] = desc_1
        set_user_state(wa_id, WAITING_FOR_PROMO_DATE_1, current_data)
        msg = (f"⏳ Paso 3 de 4: ¿Hasta qué fecha es válido ese {desc_1}% OFF inicial?\n\n"
               "Escribí la fecha completa con día, mes y año (Por ejemplo: 27/10/2026):")
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)

    elif estado_actual == WAITING_FOR_PROMO_DATE_1:
        parsed_date = parse_promo_date(texto)
        if not parsed_date:
            send_whatsapp_buttons(wa_id, "⚠️ No pude entender la fecha. Por favor escribí la fecha completa con día, mes y año (Por ejemplo: 27/10/2026):", btn_volver_menu)
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
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        else:
            buttons = [
                {"id": "PROMO_T2_YES", "title": "➕ Sí, agregar tramo"},
                {"id": "PROMO_T2_NO", "title": "🚀 No, solo este"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor seleccioná si deseás agregar un segundo tramo con menor descuento:", buttons)

    elif estado_actual == WAITING_FOR_PROMO_DISCOUNT_2:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_buttons(wa_id, "⚠️ Por favor, ingresá un porcentaje válido entre 1 y 99 (por ejemplo: 15 para 15% OFF):", btn_volver_menu)
            return
        desc_2 = int(clean_num)
        current_data = get_user_state(wa_id).get("temp_data", {})
        current_data["promo_desc_2"] = desc_2
        set_user_state(wa_id, WAITING_FOR_PROMO_DATE_2, current_data)
        date_1_display = current_data.get("promo_date_1_display", "")
        msg = (f"⏳ ¿Hasta qué fecha límite es válido este {desc_2}% OFF?\n\n"
               f"Debe ser posterior al {date_1_display} (Por ejemplo: 15/11/2026):")
        send_whatsapp_buttons(wa_id, msg, btn_volver_menu)

    elif estado_actual == WAITING_FOR_PROMO_DATE_2:
        parsed_date = parse_promo_date(texto)
        if not parsed_date:
            send_whatsapp_buttons(wa_id, "⚠️ No pude entender la fecha. Por favor escribí la fecha completa con día, mes y año (Por ejemplo: 15/11/2026):", btn_volver_menu)
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
                        notificar_cliente_cambio_publicado(wa_id, web_info, "promoción por fecha activada")
                        slug = web_info.get("slug", "mi-web")
                        public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"
                        msg = (f"🎉 ¡Promoción activada y publicada con éxito en tu web!\n\n"
                                f"Tus clientes ya verán los precios tachados, el banner de jornada y los descuentos en vivo.\n\n"
                                f"🔗 {public_url}\n\n"
                                f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                        buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
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

    elif estado_actual == WAITING_FOR_PROMO_ZONAS_DISCOUNT_1:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_buttons(wa_id, "⚠️ Por favor, ingresá un porcentaje válido entre 1 y 99 (por ejemplo: 10 para 10% OFF):", btn_volver_menu)
            return
        desc_1 = int(clean_num)
        temp_data = {"promo_zonas_desc_1": desc_1}
        set_user_state(wa_id, WAITING_FOR_PROMO_ZONAS_TIER2_CHOICE, temp_data)
        msg = (f"¿Querés agregar un 2do tramo con mayor descuento para 3 o más zonas?\n\n"
               f"(Por ejemplo: 20% OFF llevando 3 o más zonas)")
        buttons = [
            {"id": "btn_zonas_t2_si", "title": "➕ Sí, agregar tramo"},
            {"id": "btn_zonas_t2_no", "title": "🚀 Solo 2 zonas"}
        ]
        send_whatsapp_buttons(wa_id, msg, buttons)

    elif estado_actual == WAITING_FOR_PROMO_ZONAS_TIER2_CHOICE:
        if texto_limpio in ["btn_zonas_t2_no", "no", "solo 2 zonas", "solo 2", "solo", "1"]:
            current_data = get_user_state(wa_id).get("temp_data", {})
            set_user_state(wa_id, WAITING_FOR_PROMO_ZONAS_ACUMULABLE, current_data)
            msg = ("¿Querés que esta promoción por zonas sea *acumulable* con las promociones por fecha (reserva anticipada/jornadas)?\n\n"
                   "• *Acumulables:* Se suman ambos descuentos.\n"
                   "• *No acumulables:* Se aplica el mayor descuento al cliente.")
            buttons = [
                {"id": "btn_acum_si", "title": "➕ Sí, acumulables"},
                {"id": "btn_acum_no", "title": "🚫 No acumulables"}
            ]
            send_whatsapp_buttons(wa_id, msg, buttons)
        elif texto_limpio in ["btn_zonas_t2_si", "si", "sí", "agregar", "agregar tramo", "2"]:
            current_data = get_user_state(wa_id).get("temp_data", {})
            desc_1 = current_data.get("promo_zonas_desc_1", 10)
            set_user_state(wa_id, WAITING_FOR_PROMO_ZONAS_DISCOUNT_2, current_data)
            msg = (f"🎯 ¿De cuánto es el porcentaje de descuento para *3 o más zonas*?\n\n"
                   f"Debe ser mayor al {desc_1}% (Por ejemplo: {desc_1 + 10} para {desc_1 + 10}% OFF):")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        else:
            buttons = [
                {"id": "btn_zonas_t2_si", "title": "➕ Sí, agregar tramo"},
                {"id": "btn_zonas_t2_no", "title": "🚀 Solo 2 zonas"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor seleccioná si deseás agregar un segundo tramo para 3 o más zonas:", buttons)

    elif estado_actual == WAITING_FOR_PROMO_ZONAS_DISCOUNT_2:
        clean_num = re.sub(r'[^\d]', '', texto)
        current_data = get_user_state(wa_id).get("temp_data", {})
        desc_1 = current_data.get("promo_zonas_desc_1", 10)
        if not clean_num or not (int(clean_num) > desc_1 and int(clean_num) <= 99):
            send_whatsapp_buttons(wa_id, f"⚠️ Por favor, ingresá un porcentaje mayor al primer tramo ({desc_1}%) y menor o igual a 99 (por ejemplo: {desc_1 + 10} para {desc_1 + 10}% OFF):", btn_volver_menu)
            return
        desc_2 = int(clean_num)
        current_data["promo_zonas_desc_2"] = desc_2
        set_user_state(wa_id, WAITING_FOR_PROMO_ZONAS_ACUMULABLE, current_data)
        msg = ("¿Querés que esta promoción por zonas sea *acumulable* con las promociones por fecha (reserva anticipada/jornadas)?\n\n"
               "• *Acumulables:* Se suman ambos descuentos.\n"
               "• *No acumulables:* Se aplica el mayor descuento al cliente.")
        buttons = [
            {"id": "btn_acum_si", "title": "➕ Sí, acumulables"},
            {"id": "btn_acum_no", "title": "🚫 No acumulables"}
        ]
        send_whatsapp_buttons(wa_id, msg, buttons)

    elif estado_actual == WAITING_FOR_PROMO_ZONAS_ACUMULABLE:
        current_data = get_user_state(wa_id).get("temp_data", {})
        if texto_limpio in ["btn_acum_si", "si", "sí", "acumulable", "acumulables", "1", "si, acumulables"]:
            current_data["promo_zonas_acumulable"] = True
            generar_borrador_promocion_zonas(wa_id, current_data, nombre)
        elif texto_limpio in ["btn_acum_no", "no", "no acumulable", "no acumulables", "2"]:
            current_data["promo_zonas_acumulable"] = False
            generar_borrador_promocion_zonas(wa_id, current_data, nombre)
        else:
            buttons = [
                {"id": "btn_acum_si", "title": "➕ Sí, acumulables"},
                {"id": "btn_acum_no", "title": "🚫 No acumulables"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor seleccioná si deseás que los descuentos sean acumulables con promociones por fecha:", buttons)

    elif estado_actual == CONFIRM_PROMO_ZONAS_DRAFT:
        if texto_limpio in ["btn_activar_promo_zonas", "activar", "si", "sí", "confirmar", "publicar", "1", "ok", "activar promo"]:
            user_session = get_user_state(wa_id)
            temp_data = user_session.get("temp_data", {})
            promocion_zonas_data = temp_data.get("promocion_zonas_data")

            web_info = obtener_web_del_cliente(wa_id)
            if web_info and promocion_zonas_data:
                content = web_info["content"]
                if "lista_precios" in content and isinstance(content["lista_precios"], dict):
                    content["lista_precios"]["promocion_zonas"] = promocion_zonas_data
                    if actualizar_web_content(web_info["version_id"], content):
                        clear_user_state(wa_id)
                        notificar_cliente_cambio_publicado(wa_id, web_info, "promoción por zonas activada")
                        slug = web_info.get("slug", "mi-web")
                        public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"
                        msg = (f"🎉 ¡Promoción por zonas activada y publicada con éxito en tu web!\n\n"
                               f"Tus clientes ya pueden combinar servicios con descuentos por cantidad.\n\n"
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
        elif texto_limpio in ["btn_cancelar_promo_zonas", "cancelar", "no", "descartar", "2"]:
            clear_user_state(wa_id)
            send_whatsapp_message(wa_id, "❌ Publicación cancelada. El borrador de la promoción por zonas fue descartado y tus precios no sufrieron modificaciones.")
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        else:
            buttons = [
                {"id": "btn_activar_promo_zonas", "title": "✅ Activar Promo"},
                {"id": "btn_cancelar_promo_zonas", "title": "❌ Cancelar"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor respondé *Activar* para confirmar la subida de la promo o *Cancelar* para descartar el borrador.", buttons)

    elif estado_actual == WAITING_FOR_STOP_PROMO_CHOICE:
        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content"):
            send_whatsapp_message(wa_id, "⚠️ No encontramos tu página web en el sistema.")
            set_user_state(wa_id, MAIN_MENU, {})
            return
        content = web_info["content"]
        lp = content.get("lista_precios")
        if not lp or not isinstance(lp, dict):
            send_whatsapp_message(wa_id, "ℹ️ Tu lista de precios no tiene ninguna promoción activa en este momento.")
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
            return

        slug = web_info.get("slug", "mi-web")
        public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"

        if texto_limpio in ["frenar_promo_fecha", "fecha", "frenar fecha", "1"]:
            lp.pop("promocion_fecha", None)
            if actualizar_web_content(web_info["version_id"], content):
                clear_user_state(wa_id)
                notificar_cliente_cambio_publicado(wa_id, web_info, "promoción por fecha finalizada")
                msg = (f"⏹️ ¡Listo! La promoción por fecha fue detenida y retirada de tu web.\n\n"
                       f"La promoción por zonas continúa activa.\n\n"
                       f"🔗 Refrescá tu web: {public_url}\n\n"
                       f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
            else:
                send_whatsapp_message(wa_id, "❌ Hubo un error al actualizar tu web en la base de datos.")
                clear_user_state(wa_id)
        elif texto_limpio in ["frenar_promo_zonas", "zonas", "frenar zonas", "2"]:
            lp.pop("promocion_zonas", None)
            if actualizar_web_content(web_info["version_id"], content):
                clear_user_state(wa_id)
                notificar_cliente_cambio_publicado(wa_id, web_info, "promoción por zonas finalizada")
                msg = (f"⏹️ ¡Listo! La promoción por zonas fue detenida y retirada de tu web.\n\n"
                       f"La promoción por fecha continúa activa.\n\n"
                       f"🔗 Refrescá tu web: {public_url}\n\n"
                       f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
            else:
                send_whatsapp_message(wa_id, "❌ Hubo un error al actualizar tu web en la base de datos.")
                clear_user_state(wa_id)
        elif texto_limpio in ["frenar_promo_ambas", "ambas", "frenar ambas", "todas", "3"]:
            lp.pop("promocion_fecha", None)
            lp.pop("promocion_zonas", None)
            if actualizar_web_content(web_info["version_id"], content):
                clear_user_state(wa_id)
                notificar_cliente_cambio_publicado(wa_id, web_info, "promociones finalizadas")
                msg = (f"⏹️ ¡Listo! Ambas promociones fueron detenidas y retiradas de tu web.\n\n"
                       f"Tus precios volvieron a mostrarse en su valor regular sin descuentos ni banners.\n\n"
                       f"🔗 Refrescá tu web: {public_url}\n\n"
                       f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                buttons = [{"id": "btn_menu", "title": "📱 Menú Principal"}]
                send_whatsapp_buttons(wa_id, msg, buttons)
            else:
                send_whatsapp_message(wa_id, "❌ Hubo un error al actualizar tu web en la base de datos.")
                clear_user_state(wa_id)
        else:
            buttons = [
                {"id": "frenar_promo_fecha", "title": "📅 Frenar Fecha"},
                {"id": "frenar_promo_zonas", "title": "🎯 Frenar Zonas"},
                {"id": "frenar_promo_ambas", "title": "🛑 Frenar Ambas"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor seleccioná qué promoción deseás detener:", buttons)

    elif estado_actual == WAITING_FOR_ADJUST_SELECTION:
        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
            send_whatsapp_message(wa_id, "⚠️ No se encontró la lista de precios. Escribí *menu* para volver.")
            set_user_state(wa_id, MAIN_MENU, {})
            return

        items = web_info["content"]["lista_precios"].get("items", [])

        # Caso A: Toda la lista ("todos")
        if texto_limpio in ["todos", "todas", "todo", "all", "toda la lista"]:
            temp_data = {"target": "all"}
            set_user_state(wa_id, WAITING_FOR_ADJUST_TYPE_ALL, temp_data)
            msg = ("📈 *Ajuste General de Precios*\n\n"
                   "¿Qué tipo de ajuste deseás aplicar a toda tu lista?")
            buttons = [
                {"id": "btn_adj_all_inc", "title": "📈 Aumentar Precios"},
                {"id": "btn_adj_all_dec", "title": "📉 Bajar Precios"},
                {"id": "btn_menu", "title": "📱 Volver al Menú"}
            ]
            send_whatsapp_buttons(wa_id, msg, buttons)
            return

        # Caso B: Índices de productos
        clean_input = re.sub(r'\by\b', ',', texto_limpio)
        raw_nums = re.findall(r'\d+', clean_input)
        indices = []
        for n in raw_nums:
            idx = int(n) - 1
            if 0 <= idx < len(items) and idx not in indices:
                indices.append(idx)

        if len(indices) == 1:
            temp_data = {"target": "indices", "indices": indices}
            set_user_state(wa_id, WAITING_FOR_SINGLE_PRODUCT_ACTION, temp_data)
            item = items[indices[0]]
            price_str = get_item_primary_price(item)
            promo_badge = f" (🏷️ {item['descuento']}% OFF)" if item.get("descuento") else ""
            msg = (f"👉 *Producto Seleccionado:*\n\n"
                   f"*{item.get('servicio', 'Servicio')}* - {price_str}{promo_badge}\n\n"
                   f"¿Qué acción deseás realizar sobre este producto?")
            has_promo = bool(item.get("descuento"))
            buttons = [
                {"id": "btn_prod_exact", "title": "💰 Precio Exacto"},
                {"id": "btn_prod_promo", "title": "🏷️ Poner en Promo"}
            ]
            if has_promo:
                buttons.append({"id": "btn_prod_remove_promo", "title": "⏹️ Quitar Promo"})
            else:
                buttons.append({"id": "btn_prod_percent", "title": "📈 Aumentar por %"})
            send_whatsapp_buttons(wa_id, msg, buttons)
            return

        elif len(indices) > 1:
            temp_data = {"target": "indices", "indices": indices}
            set_user_state(wa_id, WAITING_FOR_MULTI_PRODUCT_ACTION, temp_data)
            num_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
            sel_lines = []
            for i in indices:
                it = items[i]
                prefix = num_emoji[i] if i < 10 else f"{i+1}️⃣"
                p_str = get_item_primary_price(it)
                p_badge = f" (🏷️ {it['descuento']}% OFF)" if it.get("descuento") else ""
                sel_lines.append(f"{prefix} *{it.get('servicio', 'Servicio')}:* {p_str}{p_badge}")

            msg = ("📋 *Productos Seleccionados:*\n\n" +
                   "\n".join(sel_lines) +
                   "\n\n¿Qué acción deseás realizar sobre estos productos?")
            has_any_promo = any(items[i].get("descuento") for i in indices)
            buttons = [
                {"id": "btn_multi_promo", "title": "🏷️ Poner en Promo"},
                {"id": "btn_multi_percent", "title": "📈 Ajustar por %"}
            ]
            if has_any_promo:
                buttons.append({"id": "btn_multi_remove_promo", "title": "⏹️ Quitar Promos"})
            else:
                buttons.append({"id": "btn_menu", "title": "📱 Volver al Menú"})
            send_whatsapp_buttons(wa_id, msg, buttons)
            return

        else:
            send_whatsapp_buttons(wa_id, "⚠️ No pude identificar los productos. Por favor escribí el número de un producto (ej: *1*), varios separados por coma (ej: *1, 3*) o la palabra *todos*:", btn_volver_menu)

    elif estado_actual == WAITING_FOR_ADJUST_TYPE_ALL:
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        target = temp_data.get("target", "all")
        target_desc = "a toda la lista" if target == "all" else "a los productos seleccionados"

        if texto_limpio in ["btn_adj_all_inc", "btn_adj_inc", "aumentar", "subir", "1"]:
            temp_data["direction"] = "inc"
            set_user_state(wa_id, WAITING_FOR_ADJUST_PERCENT_VALUE, temp_data)
            msg = (f"📈 *Aumento de Precios*\n\n"
                   f"¿Qué porcentaje deseás aumentar {target_desc}?\n"
                   f"*(Solo escribí el número, ej: 10, 15, 20):*\n\n"
                   f"💡 _(Escribí volver para cancelar)_")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        elif texto_limpio in ["btn_adj_all_dec", "btn_adj_dec", "bajar", "rebajar", "2"]:
            temp_data["direction"] = "dec"
            set_user_state(wa_id, WAITING_FOR_ADJUST_PERCENT_VALUE, temp_data)
            msg = (f"📉 *Rebaja de Precios*\n\n"
                   f"¿Qué porcentaje deseás rebajar {target_desc}?\n"
                   f"*(Solo escribí el número, ej: 10, 15, 20):*\n\n"
                   f"💡 _(Escribí volver para cancelar)_")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        else:
            buttons = [
                {"id": "btn_adj_all_inc", "title": "📈 Aumentar Precios"},
                {"id": "btn_adj_all_dec", "title": "📉 Bajar Precios"},
                {"id": "btn_menu", "title": "📱 Volver al Menú"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor seleccioná si deseás aumentar o bajar los precios:", buttons)

    elif estado_actual == WAITING_FOR_ADJUST_PERCENT_VALUE:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_buttons(wa_id, "⚠️ Por favor ingresá un porcentaje válido entre 1 y 99 (por ejemplo: 15 para 15%):", btn_volver_menu)
            return

        pct = int(clean_num)
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        target = temp_data.get("target", "all")
        direction = temp_data.get("direction", "inc")
        indices = temp_data.get("indices", [])

        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
            send_whatsapp_message(wa_id, "⚠️ No pudimos encontrar tu lista de precios activa.")
            set_user_state(wa_id, MAIN_MENU, {})
            return

        current_lp = web_info["content"]["lista_precios"]
        draft_prices = json.loads(json.dumps(current_lp))

        if target == "all":
            target_items = draft_prices.get("items", [])
            resumen = f"{'Aumento' if direction == 'inc' else 'Rebaja'} general del *{pct}%* aplicado a todos los productos."
        else:
            target_items = [draft_prices["items"][i] for i in indices if i < len(draft_prices.get("items", []))]
            resumen = f"{'Aumento' if direction == 'inc' else 'Rebaja'} del *{pct}%* aplicado a {len(target_items)} producto(s)."

        for item in target_items:
            precios = item.get("precios", {})
            for col, val in list(precios.items()):
                num = extract_numeric_price(val)
                if num > 0:
                    if direction == "inc":
                        new_num = num * (1.0 + pct / 100.0)
                    else:
                        new_num = num * (1.0 - pct / 100.0)
                    cleaned = round_clean_price(new_num)
                    precios[col] = format_price(cleaned)

        guardar_y_enviar_borrador_ajuste(wa_id, web_info, draft_prices, resumen, nombre)

    elif estado_actual == WAITING_FOR_SINGLE_PRODUCT_ACTION:
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        indices = temp_data.get("indices", [0])

        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
            send_whatsapp_message(wa_id, "⚠️ No se encontró la lista de precios.")
            set_user_state(wa_id, MAIN_MENU, {})
            return

        current_lp = web_info["content"]["lista_precios"]
        item = current_lp["items"][indices[0]]

        if texto_limpio in ["btn_prod_exact", "precio exacto", "exacto", "1"]:
            set_user_state(wa_id, WAITING_FOR_EXACT_PRICE_VALUE, temp_data)
            p_str = get_item_primary_price(item)
            msg = (f"💰 *Modificar Precio Exacto*\n\n"
                   f"Producto: *{item.get('servicio', 'Servicio')}*\n"
                   f"Precio actual: {p_str}\n\n"
                   f"Escribí el nuevo precio que querés ponerle\n"
                   f"*(Por ejemplo: 18000 o $18.000):*\n\n"
                   f"💡 _(Escribí volver para cancelar)_")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        elif texto_limpio in ["btn_prod_promo", "poner en promo", "promo", "2"]:
            set_user_state(wa_id, WAITING_FOR_PROD_PROMO_PERCENT, temp_data)
            msg = (f"🏷️ *Poner en Promoción*\n\n"
                   f"Producto: *{item.get('servicio', 'Servicio')}*\n\n"
                   f"¿Qué porcentaje de descuento querés asignarle?\n"
                   f"*(Solo escribí el número, ej: 15 o 20 para 20% OFF):*\n\n"
                   f"💡 _(Escribí volver para cancelar)_")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        elif texto_limpio in ["btn_prod_remove_promo", "quitar promo", "remover promo", "3"] and item.get("descuento"):
            draft_prices = json.loads(json.dumps(current_lp))
            draft_prices["items"][indices[0]].pop("descuento", None)
            resumen = f"Se quitó la promoción de *{item.get('servicio', 'Servicio')}* (vuelve a precio regular)."
            guardar_y_enviar_borrador_ajuste(wa_id, web_info, draft_prices, resumen, nombre)
        elif texto_limpio in ["btn_prod_percent", "aumentar por %", "porcentaje", "3"]:
            set_user_state(wa_id, WAITING_FOR_ADJUST_TYPE_ALL, temp_data)
            msg = (f"📈 *Ajustar por Porcentaje*\n\n"
                   f"Producto: *{item.get('servicio', 'Servicio')}*\n\n"
                   f"¿Deseás aumentar o rebajar el precio de este producto?")
            buttons = [
                {"id": "btn_adj_all_inc", "title": "📈 Aumentar Precios"},
                {"id": "btn_adj_all_dec", "title": "📉 Bajar Precios"},
                {"id": "btn_menu", "title": "📱 Volver al Menú"}
            ]
            send_whatsapp_buttons(wa_id, msg, buttons)
        else:
            has_promo = bool(item.get("descuento"))
            buttons = [
                {"id": "btn_prod_exact", "title": "💰 Precio Exacto"},
                {"id": "btn_prod_promo", "title": "🏷️ Poner en Promo"}
            ]
            if has_promo:
                buttons.append({"id": "btn_prod_remove_promo", "title": "⏹️ Quitar Promo"})
            else:
                buttons.append({"id": "btn_prod_percent", "title": "📈 Aumentar por %"})
            send_whatsapp_buttons(wa_id, "Por favor seleccioná una de las opciones disponibles:", buttons)

    elif estado_actual == WAITING_FOR_EXACT_PRICE_VALUE:
        num = extract_numeric_price(texto)
        if num <= 0:
            send_whatsapp_buttons(wa_id, "⚠️ Por favor ingresá un monto válido mayor a 0 (ejemplo: 18000 o $18.000):", btn_volver_menu)
            return

        fmt = format_price(num)
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        indices = temp_data.get("indices", [0])

        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
            send_whatsapp_message(wa_id, "⚠️ No se encontró la lista de precios.")
            set_user_state(wa_id, MAIN_MENU, {})
            return

        current_lp = web_info["content"]["lista_precios"]
        draft_prices = json.loads(json.dumps(current_lp))
        item = draft_prices["items"][indices[0]]
        precios = item.get("precios", {})

        if "efectivo" in precios:
            old_efectivo = extract_numeric_price(precios["efectivo"])
            precios["efectivo"] = fmt
            if old_efectivo > 0 and len(precios) > 1:
                ratio = num / old_efectivo
                for col in precios:
                    if col != "efectivo":
                        old_col = extract_numeric_price(precios[col])
                        if old_col > 0:
                            precios[col] = format_price(round_clean_price(old_col * ratio))
        else:
            for col in precios:
                precios[col] = fmt

        resumen = f"Nuevo precio para *{item.get('servicio', 'Servicio')}*: {fmt}."
        guardar_y_enviar_borrador_ajuste(wa_id, web_info, draft_prices, resumen, nombre)

    elif estado_actual == WAITING_FOR_PROD_PROMO_PERCENT:
        clean_num = re.sub(r'[^\d]', '', texto)
        if not clean_num or not (1 <= int(clean_num) <= 99):
            send_whatsapp_buttons(wa_id, "⚠️ Por favor ingresá un porcentaje de descuento válido entre 1 y 99 (por ejemplo: 20 para 20% OFF):", btn_volver_menu)
            return

        pct = int(clean_num)
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        indices = temp_data.get("indices", [])

        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
            send_whatsapp_message(wa_id, "⚠️ No se encontró la lista de precios.")
            set_user_state(wa_id, MAIN_MENU, {})
            return

        current_lp = web_info["content"]["lista_precios"]
        draft_prices = json.loads(json.dumps(current_lp))

        nom_items = []
        for i in indices:
            if i < len(draft_prices.get("items", [])):
                draft_prices["items"][i]["descuento"] = pct
                nom_items.append(draft_prices["items"][i].get("servicio", f"Producto {i+1}"))

        if len(nom_items) == 1:
            resumen = f"Promoción de *{pct}% OFF* asignada a *{nom_items[0]}*."
        else:
            resumen = f"Promoción de *{pct}% OFF* asignada a {len(nom_items)} productos."

        guardar_y_enviar_borrador_ajuste(wa_id, web_info, draft_prices, resumen, nombre)

    elif estado_actual == WAITING_FOR_MULTI_PRODUCT_ACTION:
        user_session = get_user_state(wa_id)
        temp_data = user_session.get("temp_data", {})
        indices = temp_data.get("indices", [])

        web_info = obtener_web_del_cliente(wa_id)
        if not web_info or not web_info.get("content") or not web_info["content"].get("lista_precios"):
            send_whatsapp_message(wa_id, "⚠️ No se encontró la lista de precios.")
            set_user_state(wa_id, MAIN_MENU, {})
            return

        current_lp = web_info["content"]["lista_precios"]

        if texto_limpio in ["btn_multi_promo", "poner en promo", "promo", "1"]:
            set_user_state(wa_id, WAITING_FOR_PROD_PROMO_PERCENT, temp_data)
            msg = (f"🏷️ *Poner en Promoción*\n\n"
                   f"Se aplicará a los {len(indices)} productos seleccionados.\n\n"
                   f"¿Qué porcentaje de descuento querés asignarles?\n"
                   f"*(Solo escribí el número, ej: 15 o 20 para 20% OFF):*\n\n"
                   f"💡 _(Escribí volver para cancelar)_")
            send_whatsapp_buttons(wa_id, msg, btn_volver_menu)
        elif texto_limpio in ["btn_multi_percent", "ajustar por %", "porcentaje", "2"]:
            set_user_state(wa_id, WAITING_FOR_ADJUST_TYPE_ALL, temp_data)
            msg = (f"📈 *Ajustar por Porcentaje*\n\n"
                   f"¿Deseás aumentar o rebajar el precio de los {len(indices)} productos seleccionados?")
            buttons = [
                {"id": "btn_adj_all_inc", "title": "📈 Aumentar Precios"},
                {"id": "btn_adj_all_dec", "title": "📉 Bajar Precios"},
                {"id": "btn_menu", "title": "📱 Volver al Menú"}
            ]
            send_whatsapp_buttons(wa_id, msg, buttons)
        elif texto_limpio in ["btn_multi_remove_promo", "quitar promos", "remover promos", "3"]:
            draft_prices = json.loads(json.dumps(current_lp))
            for i in indices:
                if i < len(draft_prices.get("items", [])):
                    draft_prices["items"][i].pop("descuento", None)
            resumen = f"Se quitaron las promociones de los {len(indices)} productos seleccionados."
            guardar_y_enviar_borrador_ajuste(wa_id, web_info, draft_prices, resumen, nombre)
        else:
            has_any_promo = any(current_lp["items"][i].get("descuento") for i in indices if i < len(current_lp.get("items", [])))
            buttons = [
                {"id": "btn_multi_promo", "title": "🏷️ Poner en Promo"},
                {"id": "btn_multi_percent", "title": "📈 Ajustar por %"}
            ]
            if has_any_promo:
                buttons.append({"id": "btn_multi_remove_promo", "title": "⏹️ Quitar Promos"})
            else:
                buttons.append({"id": "btn_menu", "title": "📱 Volver al Menú"})
            send_whatsapp_buttons(wa_id, "Por favor seleccioná una de las opciones disponibles:", buttons)

    elif estado_actual == CONFIRM_PRICE_ADJUST_DRAFT:
        if texto_limpio in ["btn_adj_confirm", "publicar", "confirmar", "si", "sí", "aplicar", "1", "ok"]:
            user_session = get_user_state(wa_id)
            temp_data = user_session.get("temp_data", {})
            draft_prices = temp_data.get("draft_prices")

            web_info = obtener_web_del_cliente(wa_id)
            if web_info and draft_prices:
                content = web_info["content"]
                content["lista_precios"] = draft_prices
                if actualizar_web_content(web_info["version_id"], content):
                    clear_user_state(wa_id)
                    notificar_cliente_cambio_publicado(wa_id, web_info, "precios y promociones actualizados")
                    slug = web_info.get("slug", "mi-web")
                    public_url = f"https://{web_info['custom_domain']}/precios" if web_info.get("custom_domain") else f"https://{slug}.tuweblista.com.ar/precios"
                    msg = (f"🎉 ¡Tus nuevos precios y promociones fueron publicados con éxito en tu web!\n\n"
                           f"Tus clientes ya pueden ver los valores actualizados.\n\n"
                           f"🔗 {public_url}\n\n"
                           f"📲 _Tocá el botón abajo o escribí *menu* para volver al panel de control._")
                    buttons = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]
                    send_whatsapp_buttons(wa_id, msg, buttons)
                else:
                    send_whatsapp_message(wa_id, "❌ Hubo un error al guardar los precios en la base de datos.")
            else:
                send_whatsapp_message(wa_id, "⚠️ No se encontró el borrador de precios o los datos de tu web. Por favor reintentá.")
                clear_user_state(wa_id)
        elif texto_limpio in ["btn_adj_cancel", "cancelar", "descartar", "no", "2"]:
            clear_user_state(wa_id)
            send_whatsapp_message(wa_id, "❌ Cambios cancelados. El borrador fue descartado y tus precios no sufrieron modificaciones.")
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre)
        else:
            buttons = [
                {"id": "btn_adj_confirm", "title": "✅ Publicar Precios"},
                {"id": "btn_adj_cancel", "title": "❌ Cancelar"}
            ]
            send_whatsapp_buttons(wa_id, "Por favor respondé *Publicar* para confirmar los cambios o *Cancelar* para descartar el borrador.", buttons)

    else:
        # Fallback si estamos en IDLE
        if estado_actual == IDLE:
            if not is_admin_phone(wa_id):
                palabras_cambio = [
                    "cambi", "modific", "actualiz", "agreg", "edit", "subir", "sacar", "quitar", "borrar",
                    "precio", "foto", "imagen", "texto", "horario", "ubicaci", "direcci", "servicio",
                    "telefono", "teléfono", "whatsapp", "mail", "email", "instagram", "logo", "portada",
                    "promo", "solicitud"
                ]
                if any(p in texto_limpio for p in palabras_cambio):
                    sla_msg = ("¡Recibido! 📸 Tu solicitud ya ingresó a la fila de edición y estará visible en tu web en el transcurso de las próximas 24 hs hábiles (Lunes a Viernes).\n\n"
                               "Te avisaremos por acá en cuanto esté publicado. 🚀")
                    send_whatsapp_message(wa_id, sla_msg)
                    web_info = obtener_web_del_cliente(wa_id)
                    slug = web_info.get("slug", "sin-slug") if web_info else "sin-slug"
                    admin_alert = (f"🔔 SOLICITUD DE CAMBIO RECIBIDA:\n"
                                   f"👤 Cliente: {nombre} ({wa_id})\n"
                                   f"🏪 Web: {slug}\n"
                                   f"💬 Detalle: {texto}\n\n"
                                   f"👉 Para tomar el control y editar esta web, respondé:\n"
                                   f"web {slug}")
                    send_whatsapp_message(ADMIN_PHONE, admin_alert)
                    return
            send_whatsapp_message(wa_id, "Hola 👋. Escribí la palabra *menu* para ver las opciones disponibles.")

