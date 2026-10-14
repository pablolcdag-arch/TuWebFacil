import os
import json
import logging
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
from supabase import create_client, Client
from sender import send_whatsapp_message
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

if not supabase_url or not supabase_key or not gemini_key:
    logging.error("Faltan credenciales (Supabase o Gemini).")
    exit(1)

supabase: Client = create_client(supabase_url, supabase_key)
genai.configure(api_key=gemini_key)

# Usamos el modelo multimodal
model = genai.GenerativeModel('gemini-1.5-flash')

def read_bank_statements(directory="resumenes_banco"):
    """Lee todos los CSV o Excel de la carpeta y devuelve un solo string con los datos."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        return ""
        
    all_data = []
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        try:
            if filename.endswith(".csv"):
                df = pd.read_csv(filepath)
                all_data.append(df.to_string(index=False))
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                df = pd.read_excel(filepath)
                all_data.append(df.to_string(index=False))
        except Exception as e:
            logging.error(f"No se pudo leer {filename}: {e}")
            
    return "\n\n".join(all_data)

def verify_receipt(image_path, bank_statement_text):
    if not os.path.exists(image_path):
        return {"matched": False, "reason": "La imagen del comprobante no existe en el disco."}
        
    try:
        img = Image.open(image_path)
        
        prompt = f"""
        Eres un asistente financiero de validación de pagos.
        Aquí tienes una imagen de un comprobante de transferencia bancaria enviado por un cliente.
        Y aquí está el texto del resumen bancario reciente de nuestra cuenta (puede tener múltiples transacciones):
        
        --- RESUMEN BANCARIO ---
        {bank_statement_text}
        ------------------------
        
        Tu tarea: Verifica si el pago que se muestra en el comprobante coincide con alguna transacción de ingreso en el resumen bancario. 
        Busca montos idénticos, fechas cercanas, y nombres que coincidan total o parcialmente.
        
        Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura (sin bloques de código extra):
        {{
            "matched": true o false,
            "confidence": número del 0 al 100,
            "amount_found": número con el monto encontrado,
            "reason": "Explicación breve de por qué coincide o por qué no"
        }}
        """
        
        response = model.generate_content([prompt, img])
        
        # Limpiar la respuesta
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
            
        return json.loads(text_resp.strip())
        
    except Exception as e:
        logging.error(f"Error procesando Gemini para {image_path}: {e}")
        return {"matched": False, "reason": f"Error interno de IA: {e}"}

def run_verification():
    logging.info("Iniciando Verificación de Pagos con Inteligencia Artificial...")
    
    bank_text = read_bank_statements()
    if not bank_text.strip():
        logging.warning("No hay datos en 'resumenes_banco/'. Coloca un Excel o CSV ahí primero.")
        return
        
    # Obtener pagos pendientes
    pendientes = []
    try:
        res = supabase.table("pending_payments").select("*").eq("status", "uploaded").execute()
        pendientes = res.data
    except Exception as e:
        logging.warning(f"No se pudo conectar a Supabase (posible URL de prueba): {e}")
        logging.info("Usando modo Fallback: leyendo directamente la carpeta 'receipts/'...")
        
        if os.path.exists("receipts"):
            for filename in os.listdir("receipts"):
                if filename.endswith(".jpg") or filename.endswith(".png"):
                    # Extraer un teléfono ficticio del nombre del archivo si es posible
                    phone = "Cliente Frecuente"
                    if "_" in filename:
                        parts = filename.split("_")
                        if len(parts) >= 2:
                            phone = parts[1]
                    pendientes.append({
                        "id": "mock_id",
                        "client_id": "mock_client",
                        "phone": phone,
                        "receipt_path": os.path.join("receipts", filename)
                    })
    
    if not pendientes:
        logging.info("No hay pagos pendientes de verificación.")
        return
        
    logging.info(f"Se encontraron {len(pendientes)} pagos pendientes. Cruzando con el resumen bancario...")
    
    for pending in pendientes:
        phone = pending["phone"]
        client_id = pending["client_id"]
        receipt_path = pending["receipt_path"]
        
        logging.info(f"Analizando comprobante de {phone}...")
        
        result = verify_receipt(receipt_path, bank_text)
        logging.info(f"Resultado IA: {result}")
        
        if result.get("matched") and result.get("confidence", 0) > 70:
            # PAGO APROBADO
            logging.info(f"✅ Pago APROBADO para {phone}.")
            
            try:
                # Actualizar pending_payments
                supabase.table("pending_payments").update({"status": "verified"}).eq("id", pending["id"]).execute()
                
                # Buscar suscripción pending de este cliente
                sub_res = supabase.table("subscriptions").select("id").eq("client_id", client_id).eq("status", "pending_verification").execute()
                if sub_res.data:
                    sub_id = sub_res.data[0]["id"]
                    supabase.table("subscriptions").update({"status": "active"}).eq("id", sub_id).execute()
                    
                # Activar web si estaba en mantenimiento
                web_res = supabase.table("websites").select("id").eq("client_id", client_id).execute()
                if web_res.data:
                    supabase.table("websites").update({"status": "active"}).eq("id", web_res.data[0]["id"]).execute()
            except Exception as e:
                logging.warning(f"No se pudo guardar la aprobación en BD (modo prueba local): {e}")
                
            # Avisar al cliente
            try:
                send_whatsapp_message(phone, "✅ ¡Pago verificado con éxito! Tu web ya está 100% activa. ¡Gracias por confiar en TuWebFacil!")
            except Exception as e:
                logging.warning(f"No se pudo enviar WhatsApp (posible error de API o número falso): {e}")
            
        else:
            logging.warning(f"❌ Pago RECHAZADO o NO ENCONTRADO para {phone}. Razón: {result.get('reason')}")
            # Queda en 'uploaded' para reintentar más tarde o verificar manual
            
    logging.info("Verificación finalizada.")

if __name__ == "__main__":
    run_verification()
