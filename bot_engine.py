import os
import json
import sqlite3
import requests
from dotenv import load_dotenv
from supabase import create_client
from sender import send_whatsapp_message, send_whatsapp_image, download_whatsapp_media, send_whatsapp_buttons, send_whatsapp_list
import logging
import uuid
from datetime import datetime

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
        web_res = supabase.table("websites").select("id, subdomain").eq("client_id", client_id).order("created_at", desc=True).limit(1).execute()
        if not web_res.data:
            return None
            
        website_id = web_res.data[0]["id"]
        slug = web_res.data[0]["subdomain"]
        
        # 3. Buscar la versión actual de la web
        ver_res = supabase.table("website_content").select("id, content").eq("website_id", website_id).execute()
            
        if ver_res.data:
            return {
                "website_id": website_id,
                "version_id": ver_res.data[0]["id"],
                "content": json.loads(ver_res.data[0]["content"]) if isinstance(ver_res.data[0]["content"], str) else ver_res.data[0]["content"],
                "slug": slug
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

def procesar_mensaje(wa_id, texto, nombre, msg_type="text", media_id=None):
    """Función principal que enruta el mensaje según el estado actual."""
    print(f"DEBUG BOT: Mensaje recibido de {nombre} ({wa_id}): Tipo: {msg_type} - '{texto}'")
    
    user_session = get_user_state(wa_id)
    estado_actual = user_session["estado"]
    
    if msg_type not in ["text", "interactive", "image"]:
        send_whatsapp_message(wa_id, "Por favor, escribime por texto o enviame imágenes. Todavía no puedo escuchar audios. 😅")
        return

    texto_limpio = texto.strip().lower()
    print(f"DEBUG BOT: Estado actual: {estado_actual}")
    
    # 1. Palabra clave universal de reseteo
    if texto_limpio in ["menu", "menú", "volver", "inicio", "cancelar"]:
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
            
    # 2. Detectar intención de inicio (Confirmar mi web) - Esto resetea al MAIN MENU
    if "confirmar mi web" in texto_limpio:
        msg = (f"¡Hola {nombre}! 🎉 Qué bueno que te gustó tu demo.\n\n"
               f"📱 *TuWebLista - Panel de Control*\n\n"
               f"¿Qué te gustaría hacer con tu web hoy?\n\n"
               f"💡 _Tip: Podés escribir la palabra *'menu'* en cualquier momento para volver a ver estas opciones._")
        
        options = [
            {"id": "MAIN_VER_LINK", "title": "🌐 Ver mi página web"},
            {"id": "MAIN_EDITAR", "title": "🛠️ Textos / Imágenes", "description": "Editar textos e imágenes"},
            {"id": "MAIN_DOMAIN", "title": "🌐 Comprar Dominio", "description": "Buscador de dominios .com.ar"},
            {"id": "MAIN_TRANSFER", "title": "🔄 Transferir Admin", "description": "Cambiar número celular"},
            {"id": "MAIN_PUBLICAR", "title": "🚀 Publicar / Planes", "description": "Publicar página / ver planes"},
            {"id": "MAIN_CONTACT", "title": "💬 Hablar con Admin", "description": "Hablar con soporte / admin"}
        ]
        send_whatsapp_list(wa_id, msg, "Abrir Opciones", options, "Panel de Control")
        set_user_state(wa_id, MAIN_MENU, {})
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
                        send_whatsapp_message(wa_id, f"✅ ¡Imagen actualizada con éxito!\n\n🔗 *Refrescá tu web para verla:* https://{web_data['slug']}.tuweblista.com.ar")
                    else:
                        send_whatsapp_message(wa_id, "⚠️ No encontré tu web en el sistema.")
                else:
                    send_whatsapp_message(wa_id, "❌ Hubo un error al descargar la imagen. Volvé a intentarlo.")
            set_user_state(wa_id, MAIN_MENU, {})
            procesar_mensaje(wa_id, "2", nombre)
            return

    elif estado_actual == MAIN_MENU:
        if texto_limpio == "main_ver_link" or texto_limpio == "1":
            msg = "Aún no la hemos publicado oficialmente, pero este es tu link temporal de Demo. En breve estará 100% activa."
            send_whatsapp_message(wa_id, msg)
        elif texto_limpio == "main_soporte" or texto_limpio == "main_contact":
            send_whatsapp_message(wa_id, "Escribí el mensaje que le querés enviar al administrador.\n\n⚠️ *Aviso*: Esto no es un chat en vivo, pero tu mensaje quedará registrado y te responderemos por este mismo medio en el transcurso del día.")
            set_user_state(wa_id, WAITING_FOR_ADMIN_MESSAGE)

        elif texto_limpio == "main_transfer":
            msg = ("🔄 *Transferir Administración*\n\n"
                   "Para transferir la administración de esta web a otro número, escribí acá abajo el nuevo número de WhatsApp (Ej: 1131234567 o +5491131234567).\n\n"
                   "⚠️ Importante: Una vez confirmada la transferencia, perderás acceso a este menú.")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_TRANSFER_PHONE)

        elif texto_limpio == "main_domain":
            msg = ("🌐 *Buscador Oficial de Dominios (.com.ar)*\n\n"
                   "Escribí acá abajo el nombre que te gustaría tener para tu página (Ej: mipanaderia, estudiojuridico, etc).\n\n"
                   "No hace falta que escribas el '.com.ar', nosotros lo agregamos y verificamos si está disponible en NIC Argentina al instante.")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, WAITING_FOR_DOMAIN_NAME)
            
        elif texto_limpio == "main_editar" or texto_limpio == "2":
            msg = "✏️ *Menú de Edición*\n¿Qué parte de tu página web querés modificar?"
            options = [
                {"id": "EDIT_TITULO", "title": "📝 Editar Título"},
                {"id": "EDIT_SUBTITULO", "title": "📝 Editar Subtítulo"},
                {"id": "EDIT_SERVICIOS", "title": "💼 Editar Servicios"},
                {"id": "EDIT_LOCATION", "title": "📍 Editar Ubicación"},
                {"id": "EDIT_SCHEDULE", "title": "🕒 Editar Horarios"},
                {"id": "EDIT_IMAGENES", "title": "🖼️ Editar Imágenes"},
                {"id": "EDIT_WHATSAPP", "title": "💬 Editar WhatsApp"},
                {"id": "EDIT_EMAIL", "title": "✉️ Editar Email"},
                {"id": "EDIT_INSTAGRAM", "title": "📷 Editar Instagram"},
                {"id": "EDIT_VOLVER", "title": "⬅️ Volver"}
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
            send_whatsapp_message(wa_id, "Escribí el nuevo Título que querés para tu web (Por ejemplo: 'Estudio Jurídico Gonzalez'):")
            set_user_state(wa_id, WAITING_FOR_TITLE)
        elif texto_limpio == "edit_subtitulo" or texto_limpio == "2":
            send_whatsapp_message(wa_id, "Escribí el nuevo *Subtítulo*\n*(Por ejemplo: 'Más de 20 años ayudando a las personas'):*")
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
            send_whatsapp_message(wa_id, "Escribí la nueva Ubicación o Dirección (Por ejemplo: 'Avenida Corrientes 1000, CABA'. Mientras más exacto, mejor aparecerá en el mapa, tambien podes poner ciudad y provincia si no queres poner una direccion exacta):")
            set_user_state(wa_id, WAITING_FOR_LOCATION)
        elif texto_limpio == "edit_schedule" or texto_limpio == "5":
            send_whatsapp_message(wa_id, "Escribí tus *Horarios de Atención*\n*(Por ejemplo: 'Lunes a Viernes de 9 a 18hs').*\n\nSi no querés mostrar los horarios, escribí *Ocultar*:")
            set_user_state(wa_id, WAITING_FOR_SCHEDULE)
        elif texto_limpio == "edit_imagenes" or texto_limpio == "6":
            msg = ("💡 *Tamaños sugeridos:*\n"
                   "• *Foto Principal (Hero):* Horizontal apaisada (16:9) aprox 1920x1080 px.\n"
                   "• *Logo y Servicios:* Cuadradas (1:1) aprox 800x800 px.\n\n"
                   "📸 *¡Es súper fácil cambiar las fotos!*\n"
                   "Simplemente *enviame la foto por este chat ahora mismo* y te preguntaremos dónde querés ubicarla.")
            send_whatsapp_message(wa_id, msg)
            set_user_state(wa_id, IDLE, {})
        elif texto_limpio == "edit_whatsapp":
            send_whatsapp_message(wa_id, "Escribí el número de WhatsApp donde querés recibir las consultas de tus clientes (Ej: +54 9 1131234567 o 1131234567).")
            set_user_state(wa_id, WAITING_FOR_WHATSAPP)

        elif texto_limpio == "edit_email":
            send_whatsapp_message(wa_id, "Escribí la dirección de correo electrónico que querés mostrar en la sección de contacto de tu web (Ej: info@empresa.com).\n\nSi no querés mostrar ningún correo, simplemente escribí *Ocultar*.")
            set_user_state(wa_id, WAITING_FOR_EMAIL)
        elif texto_limpio == "edit_instagram" or texto_limpio == "9":
            send_whatsapp_message(wa_id, "Escribí tu usuario de Instagram (Ej: @minegocio) o pegá el enlace directo a tu perfil.\n\nSi no querés mostrar tu Instagram en la web, simplemente escribí *Ocultar*.")
            set_user_state(wa_id, WAITING_FOR_INSTAGRAM)

        elif texto_limpio == "edit_volver" or texto_limpio == "0":
            clear_user_state(wa_id)
            procesar_mensaje(wa_id, "quiero confirmar mi web", nombre) # Simulamos volver a entrar
        else:
            send_whatsapp_message(wa_id, "Por favor, elegí una opción de la lista.")
            
    elif estado_actual == "EDIT_MENU_SERVICIOS":
        if texto_limpio == "edit_srv_1" or texto_limpio == "1":
            send_whatsapp_message(wa_id, "Escribí el nuevo *Título* para el Servicio 1:")
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 0})
        elif texto_limpio == "edit_srv_2" or texto_limpio == "2":
            send_whatsapp_message(wa_id, "Escribí el nuevo *Título* para el Servicio 2:")
            set_user_state(wa_id, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 1})
        elif texto_limpio == "edit_srv_3" or texto_limpio == "3":
            send_whatsapp_message(wa_id, "Escribí el nuevo *Título* para el Servicio 3:")
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
        send_whatsapp_message(wa_id, "Excelente. Ahora escribí la *Descripción* para este servicio\n*(Por ejemplo: 'Asesoramiento legal integral personalizado'):*")
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
                set_user_state(wa_id, WAITING_FOR_RECEIPT, {"dominio": dominio_limpio})
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
                   "Una vez que reciba ese mensaje, la web se transferirá automáticamente.")
            send_whatsapp_message(wa_id, msg)
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
        
        send_whatsapp_message(wa_id, "✅ Tu mensaje fue enviado con éxito. En el transcurso del día un administrador revisará tu consulta y te responderá por acá.")
        send_whatsapp_message("5491134710787", f"✉️ NUEVO MENSAJE DE {nombre} ({wa_id}):\n\n{texto}\n\nRevisá el dashboard para contestarle.")
        set_user_state(wa_id, IDLE, {})

    else:
        # Fallback si estamos en IDLE
        if estado_actual == IDLE:
            send_whatsapp_message(wa_id, "Hola 👋. Escribí la palabra *menu* para ver las opciones disponibles.")

