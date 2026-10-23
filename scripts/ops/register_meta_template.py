#!/usr/bin/env python3
"""
Registra la plantilla oficial de prospección en Meta WhatsApp Cloud API.
Garantiza escape exacto de caracteres monetarios ($2.000) y formato UTF-8 limpio.
"""

import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

WABA_ID = "969347129180704"
TEMPLATE_NAME = "propuesta_web_oficial"

BODY_TEXT = """¡Hola {{1}}! 👋 Vimos lo que hacen en {{2}} y sabemos lo importante que es no depender solo de las redes sociales, donde el algoritmo cambia seguido.

Una página web es tu "casa propia" en internet: te da presencia profesional, mejor posicionamiento en Google en tu zona y pedidos directos a tu WhatsApp.

Para que lo veas en la práctica, les preparamos su web lista para usar:

🔗 {{3}}

✨ ¿Qué incluye?
• Catálogo / Lista de precios interactiva con carrito directo a WhatsApp.
• Ubicación en el mapa, horarios y botones de contacto.
• Mantenimiento 100% incluido: vos no tenés que aprender nada, nos mandás un WhatsApp y nosotros actualizamos tus fotos o precios.
• Tu dirección web: tunegocio.tuweblista.com.ar (o con tu propio .com.ar oficial).

✅ Los primeros 30 días son 100% gratis, sin tarjeta de crédito ni suscripciones. Si luego decidís mantenerla activa, el costo es de solo $2.000 al mes por transferencia bancaria (alias: tuweblista).

¿Te gustaría probarla para tu negocio?"""

def register_template():
    token = os.getenv("WHATSAPP_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        print("❌ Error: Ni WHATSAPP_TOKEN ni INSTAGRAM_ACCESS_TOKEN están definidos en .env")
        return False

    payload = {
        "name": TEMPLATE_NAME,
        "category": "MARKETING",
        "language": "es_AR",
        "components": [
            {
                "type": "BODY",
                "text": BODY_TEXT,
                "example": {
                    "body_text": [
                        ["Panadería San Pedro", "Caballito", "https://panaderiasanpedro.tuweblista.com.ar"]
                    ]
                }
            },
            {
                "type": "BUTTONS",
                "buttons": [
                    {
                        "type": "QUICK_REPLY",
                        "text": "Sí, me interesa"
                    },
                    {
                        "type": "QUICK_REPLY",
                        "text": "No me interesa"
                    }
                ]
            }
        ]
    }

    url = f"https://graph.facebook.com/v19.0/{WABA_ID}/message_templates"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"🎉 PLANTILLA REGISTRADA CON ÉXITO EN META:")
            print(json.dumps(data, indent=2))
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"❌ Error HTTP {e.code}: {err_body}")
        return False
    except Exception as e:
        print(f"❌ Error general: {e}")
        return False

if __name__ == "__main__":
    print(f"Longitud del texto: {len(BODY_TEXT)} caracteres (límite: 1024)")
    register_template()
