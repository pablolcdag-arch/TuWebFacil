import requests
import json

# La URL local de tu servidor (donde corre app.py)
URL_LOCAL = "http://127.0.0.1:5001/webhook"

def simular_mensaje_whatsapp(texto):
    print(f"\n--- 🧪 SIMULANDO MENSAJE: '{texto}' ---")
    
    # Estructura idéntica a la que envía Meta
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "messages": [{
                        "from": "5491134710787",
                        "text": {"body": texto},
                        "type": "text"
                    }]
                }
            }]
        }]
    }

    try:
        response = requests.post(URL_LOCAL, json=payload)
        if response.status_code == 200:
            print("✅ El servidor recibió el mensaje correctamente.")
        else:
            print(f"❌ Error en el servidor: {response.status_code}")
    except Exception as e:
        print(f"❌ No se pudo conectar con el servidor: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando simulador de pruebas...")
    mensaje = input("Escribe el mensaje que quieres probar: ")
    simular_mensaje_whatsapp(mensaje)