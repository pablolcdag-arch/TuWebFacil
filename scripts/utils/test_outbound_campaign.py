#!/usr/bin/env python3
"""
scripts/utils/test_outbound_campaign.py
Suite de pruebas automatizadas para la campaña Outbound de TuWebLista:
1. Verificación del armado de payload en sender.send_whatsapp_template().
2. Extracción defensiva en receiver.py (button_reply.id, button_reply.title, type='button').
3. Interceptación de 'Sí, me interesa' en bot_engine.py (guía conversacional + alerta Super-Admin).
4. Interceptación de 'No me interesa' en bot_engine.py (despedida cordial + tabla opt_outs).
5. Despacho controlado en send_outbound_campaign.py (exclusión opt-outs, deduplicación, pacing).
"""

import os
import sys
import csv
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import sender
import receiver
import bot_engine
from scripts.ops.send_outbound_campaign import (
    extraer_localidad,
    procesar_campana
)

def banner(title):
    print(f"\n{'='*70}\n🧪 TEST CAMPAÑA OUTBOUND: {title}\n{'='*70}")

def test_send_whatsapp_template_payload():
    banner("1. Armado de payload en sender.send_whatsapp_template()")

    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        destinatario = "5491134710787"
        template_name = "propuesta_web_comercio"
        params = ["Panadería San Pedro", "Palermo", "https://panaderia-san-pedro.tuweblista.com.ar"]

        res = sender.send_whatsapp_template(
            to_number=destinatario,
            template_name=template_name,
            language_code="es_AR",
            body_parameters=params
        )

        assert res is True, "send_whatsapp_template debe retornar True ante HTTP 200"
        assert mock_post.called, "requests.post debe ser invocado"

        call_args = mock_post.call_args
        url = call_args[0][0]
        payload = call_args[1]["json"]
        headers = call_args[1]["headers"]

        assert "messages" in url, f"URL incorrecta: {url}"
        assert "Authorization" in headers and "Bearer" in headers["Authorization"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["recipient_type"] == "individual"
        assert payload["to"] == destinatario
        assert payload["type"] == "template"

        tpl = payload["template"]
        assert tpl["name"] == template_name
        assert tpl["language"]["code"] == "es_AR"
        assert len(tpl["components"]) == 1
        assert tpl["components"][0]["type"] == "body"

        tpl_params = tpl["components"][0]["parameters"]
        assert len(tpl_params) == 3
        assert tpl_params[0] == {"type": "text", "text": "Panadería San Pedro"}
        assert tpl_params[1] == {"type": "text", "text": "Palermo"}
        assert tpl_params[2] == {"type": "text", "text": "https://panaderia-san-pedro.tuweblista.com.ar"}

    print("✅ TEST 1 PASADO: Payload de WhatsApp Cloud API para plantillas verificado con componentes correctos.")

def test_receiver_button_extraction():
    banner("2. Extracción defensiva de botones interactivos y de plantilla en receiver.py")

    client = receiver.app.test_client()

    captured_args = []

    def fake_thread_start(target, args=()):
        captured_args.append(args)

    # Caso A: interactive -> button_reply con 'id'
    payload_a = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491122223333",
                        "type": "interactive",
                        "interactive": {
                            "type": "button_reply",
                            "button_reply": {"id": "btn_si", "title": "Sí, me interesa"}
                        }
                    }],
                    "contacts": [{"wa_id": "5491122223333", "profile": {"name": "Comercio A"}}]
                }
            }]
        }]
    }

    # Caso B: interactive -> button_reply sin 'id' pero con 'title' (típico de plantillas Meta)
    payload_b = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491144445555",
                        "type": "interactive",
                        "interactive": {
                            "type": "button_reply",
                            "button_reply": {"id": "", "title": "🚀 Sí, me interesa"}
                        }
                    }],
                    "contacts": [{"wa_id": "5491144445555", "profile": {"name": "Comercio B"}}]
                }
            }]
        }]
    }

    # Caso C: type == 'button' (evento nativo de Quick Reply en plantillas Meta)
    payload_c = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491166667777",
                        "type": "button",
                        "button": {"text": "❌ No me interesa", "payload": "opt_out"}
                    }],
                    "contacts": [{"wa_id": "5491166667777", "profile": {"name": "Comercio C"}}]
                }
            }]
        }]
    }

    with patch("threading.Thread") as mock_thread:
        # Mock de Thread para ejecutar sincrónicamente o capturar args
        mock_thread.side_effect = lambda target, args: MagicMock(start=lambda: target(*args))

        with patch("bot_engine.procesar_mensaje") as mock_bot:
            res_a = client.post("/webhook", json=payload_a)
            assert res_a.status_code == 200
            assert mock_bot.call_args[0][1] == "btn_si"

            res_b = client.post("/webhook", json=payload_b)
            assert res_b.status_code == 200
            assert mock_bot.call_args[0][1] == "🚀 Sí, me interesa"

            res_c = client.post("/webhook", json=payload_c)
            assert res_c.status_code == 200
            assert mock_bot.call_args[0][1] == "❌ No me interesa"

    print("✅ TEST 2 PASADO: receiver.py extrae defensivamente el texto desde button_reply.id, button_reply.title y type='button'.")

def test_bot_engine_intercept_si_me_interesa():
    banner("3. Interceptación de 'Sí, me interesa' en bot_engine.py (guía conversacional + alerta Super-Admin)")

    test_wa = "5491177770001"
    test_nombre = "Heladería Artesanal Vivaldi"

    with patch("bot_engine.send_whatsapp_message") as mock_send, \
         patch("bot_engine.obtener_web_del_cliente") as mock_web:

        mock_web.return_value = {"slug": "heladeria-vivaldi", "version_id": "v1"}

        bot_engine.procesar_mensaje(test_wa, "🚀 Sí, me interesa", test_nombre)

        assert mock_send.call_count == 2, f"Se esperaban 2 mensajes enviados, se enviaron {mock_send.call_count}"

        # 1er mensaje: Guía al cliente
        cliente_call = mock_send.call_args_list[0]
        assert cliente_call[0][0] == test_wa
        cliente_msg = cliente_call[0][1]
        assert "¡Excelente elección! 🎉" in cliente_msg
        assert "1️⃣ Tus Precios" in cliente_msg
        assert "2️⃣ Tus Fotos" in cliente_msg
        assert "3️⃣ Dominio Propio" in cliente_msg
        assert "4️⃣ Dejarla activa como está" in cliente_msg

        # 2do mensaje: Alerta al Super-Admin
        admin_call = mock_send.call_args_list[1]
        assert admin_call[0][0] == bot_engine.ADMIN_PHONE
        admin_msg = admin_call[0][1]
        assert "🔥 ¡PROSPECTO INTERESADO!" in admin_msg
        assert test_nombre in admin_msg
        assert test_wa in admin_msg
        assert "heladeria-vivaldi" in admin_msg
        assert "web heladeria-vivaldi" in admin_msg

    print("✅ TEST 3 PASADO: 'Sí, me interesa' despacha la guía amigable al cliente y la alerta de acción inmediata al Super-Admin.")

def test_bot_engine_intercept_no_me_interesa():
    banner("4. Interceptación de 'No me interesa' en bot_engine.py (despedida cordial + tabla opt_outs)")

    test_wa = "5491177770002"
    test_nombre = "Bazar Don Pepe"

    # Asegurar que esté limpio antes del test
    db_path = bot_engine.get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM opt_outs WHERE phone = ?", (test_wa,))
    conn.commit()
    conn.close()

    assert not bot_engine.is_opted_out(test_wa), "El número no debe estar en opt-out al inicio"

    with patch("bot_engine.send_whatsapp_message") as mock_send:
        bot_engine.procesar_mensaje(test_wa, "❌ No me interesa", test_nombre)

        assert mock_send.call_count == 1, "Debe enviar exactamente un mensaje de despedida"
        call = mock_send.call_args
        assert call[0][0] == test_wa
        msg = call[0][1]
        assert "¡Entendido! Muchas gracias por tu respuesta" in msg
        assert "muchos éxitos con el negocio" in msg

        # Verificar persistencia en opt_outs
        assert bot_engine.is_opted_out(test_wa), "El teléfono debe quedar registrado en la tabla opt_outs"
        # También con formato local o formateado
        assert bot_engine.is_opted_out("+54 9 11 7777-0002")

    # Limpieza
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM opt_outs WHERE phone = ?", (test_wa,))
    conn.commit()
    conn.close()

    print("✅ TEST 4 PASADO: 'No me interesa' despacha mensaje cordial de despedida y registra el número en la tabla opt_outs.")

def test_send_outbound_campaign_script():
    banner("5. Despacho controlado en send_outbound_campaign.py (exclusión opt-outs, deduplicación, pacing)")

    # Registrar previamente un número en opt_outs
    opt_out_phone = "5491155550003"
    bot_engine.register_opt_out(opt_out_phone)

    # Crear archivo CSV sintético temporal
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', suffix='.csv', delete=False) as f_in:
        input_csv_path = f_in.name
        writer = csv.writer(f_in)
        writer.writerow(["Nombre del Local", "Teléfono", "Dirección", "slug", "link_demo", "enviado_fecha"])
        # Fila 1: Prospecto válido a contactar
        writer.writerow(["Panadería San Pedro", "+54 11 3471-0787", "Av. Santa Fe 1234, Palermo, CABA", "panaderia-san-pedro", "https://panaderia-san-pedro.tuweblista.com.ar", ""])
        # Fila 2: Prospecto ya contactado anteriormente (debe omitirse)
        writer.writerow(["Ferretería El Tornillo", "011 4455-6677", "Rivadavia 5678, Haedo", "ferreteria-el-tornillo", "https://ferreteria-el-tornillo.tuweblista.com.ar", "2026-10-20 12:00:00"])
        # Fila 3: Prospecto en opt-out (debe omitirse)
        writer.writerow(["Bazar Sol", opt_out_phone, "Caballito, CABA", "bazar-sol", "https://bazar-sol.tuweblista.com.ar", ""])

    output_csv_path = input_csv_path.replace(".csv", "_out.csv")

    try:
        with patch("scripts.ops.send_outbound_campaign.send_whatsapp_template") as mock_template:
            mock_template.return_value = True

            res = procesar_campana(
                input_path=input_csv_path,
                output_path=output_csv_path,
                limit=None,
                delay=0,
                dry_run=False
            )

            # Verificaciones del resumen
            assert res["total"] == 3
            assert res["enviados"] == 1, f"Se esperaba 1 envío exitoso, se obtuvo: {res['enviados']}"
            assert res["ya_enviados"] == 1, f"Se esperaba 1 ya enviado, se obtuvo: {res['ya_enviados']}"
            assert res["opt_out"] == 1, f"Se esperaba 1 omitido por opt-out, se obtuvo: {res['opt_out']}"

            # Verificar llamada a la plantilla Meta
            assert mock_template.call_count == 1, f"send_whatsapp_template debía llamarse 1 vez, se llamó {mock_template.call_count}"
            call_k = mock_template.call_args
            assert call_k.kwargs["to_number"] == "5491134710787"
            assert call_k.kwargs["template_name"] == "propuesta_web_comercio"
            body_params = call_k.kwargs["body_parameters"]
            assert body_params[0] == "Panadería San Pedro"
            assert body_params[1] == "Palermo"
            assert body_params[2] == "https://panaderia-san-pedro.tuweblista.com.ar"

            # Verificar persistencia en CSV de salida
            with open(output_csv_path, mode='r', encoding='utf-8-sig') as f_out:
                reader = csv.DictReader(f_out)
                filas_out = list(reader)

            assert len(filas_out) == 3
            assert filas_out[0]["estado_envio"] == "enviado"
            assert len(filas_out[0]["enviado_fecha"]) > 0
            assert filas_out[1]["enviado_fecha"] == "2026-10-20 12:00:00"
            assert filas_out[2]["estado_envio"] == "opt_out"
            assert filas_out[2]["enviado_fecha"] == ""

    finally:
        # Limpieza de archivos temporales y BD
        if os.path.exists(input_csv_path):
            os.remove(input_csv_path)
        if os.path.exists(output_csv_path):
            os.remove(output_csv_path)
        db_path = bot_engine.get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM opt_outs WHERE phone = ?", (opt_out_phone,))
        conn.commit()
        conn.close()

    print("✅ TEST 5 PASADO: send_outbound_campaign.py excluye opt-outs, evita duplicados y registra timestamps.")

def main():
    print("\n" + "="*70)
    print("🚀 INICIANDO TEST SUITE: CAMPAÑA OUTBOUND & RESPUESTAS FSM")
    print("="*70)

    test_send_whatsapp_template_payload()
    test_receiver_button_extraction()
    test_bot_engine_intercept_si_me_interesa()
    test_bot_engine_intercept_no_me_interesa()
    test_send_outbound_campaign_script()

    print("\n" + "="*70)
    print("🎉 TODOS LOS TESTS DE CAMPAÑA OUTBOUND PASARON (100% OK)")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

