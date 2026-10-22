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
import time
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
    procesar_campana,
    STOP_SIGNAL_FILE,
    STATE_FILE
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

    # Limpieza previa de señales
    if os.path.exists(STOP_SIGNAL_FILE):
        os.remove(STOP_SIGNAL_FILE)
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

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

def test_extraer_localidad_comprehensive():
    banner("6. Extractor inteligente de localidades y mapeo de códigos postales")

    # a) Si fila tiene columna 'Zona' o 'zona'
    f1 = {"Zona": "Villa Devoto, CABA", "Dirección": "Habana 3000"}
    assert extraer_localidad(f1) == "Villa Devoto", f"Falla Zona con sufijo CABA: {extraer_localidad(f1)}"

    f2 = {"zona": "Palermo", "Dirección": "Gorriti 4500"}
    assert extraer_localidad(f2) == "Palermo", f"Falla zona minúscula: {extraer_localidad(f2)}"

    f3 = {"Zona": "Tandil, Buenos Aires", "Dirección": "Pinto 500"}
    assert extraer_localidad(f3) == "Tandil", f"Falla Zona interior: {extraer_localidad(f3)}"

    # Si Zona es genérica ('CABA'), debe recurrir a la dirección
    f_gen = {"Zona": "CABA", "Dirección": "Av. Cabildo 2500, Belgrano, CABA"}
    assert extraer_localidad(f_gen) == "Belgrano", f"Zona genérica debe recurrir a dirección: {extraer_localidad(f_gen)}"

    # b) Detección de CP de CABA en dirección
    d_cp1 = "Av. Triunvirato 4500, C1431 CABA"
    assert extraer_localidad(direccion=d_cp1) == "Villa Urquiza", f"Falla CP C1431: {extraer_localidad(direccion=d_cp1)}"

    d_cp2 = "Calle Cuenca 3000, CP 1417, CABA"
    assert extraer_localidad(direccion=d_cp2) == "Villa del Parque", f"Falla CP 1417: {extraer_localidad(direccion=d_cp2)}"

    d_cp3 = "Av. Santa Fe 3200, 1425 CABA"
    assert extraer_localidad(direccion=d_cp3) == "Palermo", f"Falla CP 1425: {extraer_localidad(direccion=d_cp3)}"

    d_cp4 = "Av. San Martín 1500, C1416 CABA"
    assert extraer_localidad(direccion=d_cp4) == "La Paternal", f"Falla CP 1416: {extraer_localidad(direccion=d_cp4)}"

    # c) Ciudades del interior sin CP
    d_int1 = "Calle 123, Tandil, Prov. de Buenos Aires, Argentina"
    assert extraer_localidad(direccion=d_int1) == "Tandil", f"Falla Tandil: {extraer_localidad(direccion=d_int1)}"

    d_int2 = "Bv. Lehmann 450, Rafaela, Santa Fe, Argentina"
    assert extraer_localidad(direccion=d_int2) == "Rafaela", f"Falla Rafaela: {extraer_localidad(direccion=d_int2)}"

    d_int3 = "Rivadavia 5678, Haedo"
    assert extraer_localidad(direccion=d_int3) == "Haedo", f"Falla Haedo: {extraer_localidad(direccion=d_int3)}"

    # d) Fallback inteligente
    d_ba = "Av. Corrientes 1234, CABA"
    assert extraer_localidad(direccion=d_ba) == "Buenos Aires", f"Falla fallback Buenos Aires: {extraer_localidad(direccion=d_ba)}"

    d_gen = "Ruta 2 Km 40"
    assert extraer_localidad(direccion=d_gen) == "tu zona", f"Falla fallback tu zona: {extraer_localidad(direccion=d_gen)}"

    # e) Llamada retrocompatible con un solo string
    assert extraer_localidad("Av. Santa Fe 1234, Palermo, CABA") == "Palermo"
    assert extraer_localidad(None, None) == "tu zona"
    assert extraer_localidad({}, "") == "tu zona"

    print("✅ TEST 6 PASADO: extraer_localidad mapea CPs de CABA, extrae ciudades del interior y aplica fallbacks defensivos.")

def test_campaign_api_endpoints():
    banner("7. Endpoints de control de campaña en Flask (/admin/campaign/*)")

    from app import app
    client = app.test_client()

    # 1. Sin autenticación -> 403
    res_start_unauth = client.post("/admin/campaign/start", json={"filename": "test.csv"})
    assert res_start_unauth.status_code == 403

    res_status_unauth = client.get("/admin/campaign/status")
    assert res_status_unauth.status_code == 403

    res_stop_unauth = client.post("/admin/campaign/stop")
    assert res_stop_unauth.status_code == 403

    # Crear sesión de admin
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True

    # 2. Status inicial -> idle
    res_status = client.get("/admin/campaign/status")
    assert res_status.status_code == 200
    st_data = res_status.get_json()
    assert st_data["status"] in ["idle", "completed", "stopped"]
    assert "total" in st_data
    assert "enviados" in st_data
    assert "current_contact" in st_data
    assert "logs" in st_data

    # 3. Start sin filename -> 400
    res_bad = client.post("/admin/campaign/start", json={})
    assert res_bad.status_code == 400

    # 4. Start con archivo inexistente -> 404
    res_not_found = client.post("/admin/campaign/start", json={"filename": "inexistente_12345.csv"})
    assert res_not_found.status_code == 404

    # 5. Crear archivo CSV de prueba en leads/
    leads_dir = os.path.join(BASE_DIR, "leads")
    os.makedirs(leads_dir, exist_ok=True)
    test_csv_name = "test_campaign_temp.csv"
    test_csv_path = os.path.join(leads_dir, test_csv_name)

    with open(test_csv_path, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Nombre del Local", "Teléfono", "Dirección", "slug"])
        writer.writerow(["Comercio Test API", "1133334444", "Av. Santa Fe 2000, Palermo, CABA", "comercio-test-api"])

    try:
        # Start válido con dry_run=True y delay=2
        res_start = client.post("/admin/campaign/start", json={
            "filename": test_csv_name,
            "limit": 5,
            "delay": 2,
            "dry_run": True
        })
        assert res_start.status_code == 200, f"Error iniciando campaña: {res_start.data}"
        data_started = res_start.get_json()
        assert data_started["status"] == "started"

        # 6. Intentar iniciar otra mientras corre -> 409
        res_conflict = client.post("/admin/campaign/start", json={
            "filename": test_csv_name
        })
        assert res_conflict.status_code == 409

        # 7. Consultar status mientras corre
        res_running = client.get("/admin/campaign/status")
        assert res_running.status_code == 200
        run_data = res_running.get_json()
        assert run_data["status"] in ["running", "completed"]

        # 8. Detener campaña
        res_stop = client.post("/admin/campaign/stop")
        assert res_stop.status_code == 200
        stop_data = res_stop.get_json()
        assert stop_data["status"] in ["stopping", "not_running", "completed"]

        # Esperar a que el hilo finalice para limpieza limpia del archivo de prueba
        for _ in range(20):
            st = client.get("/admin/campaign/status").get_json()
            if st.get("status") in ["stopped", "completed", "error"]:
                break
            time.sleep(0.1)

    finally:
        if os.path.exists(test_csv_path):
            os.remove(test_csv_path)

    print("✅ TEST 7 PASADO: Endpoints /admin/campaign/start, /status y /stop verificados con seguridad de sesión y concurrencia.")

def test_multi_worker_disk_sync():
    banner("8. Señal en disco y sincronización multi-worker (.campaign_stop y .campaign_state.json)")

    import threading
    import scripts.ops.send_outbound_campaign as outbound_mod
    from scripts.ops.send_outbound_campaign import (
        STOP_SIGNAL_FILE,
        STATE_FILE,
        _save_campaign_state_disk,
        _load_campaign_state_disk,
        start_campaign_task,
        stop_campaign_task,
        get_campaign_status,
        procesar_campana
    )

    # 1. Verificar definición de rutas
    assert STOP_SIGNAL_FILE.endswith(".campaign_stop")
    assert STATE_FILE.endswith(".campaign_state.json")

    # Limpieza inicial
    if os.path.exists(STOP_SIGNAL_FILE):
        os.remove(STOP_SIGNAL_FILE)
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

    try:
        # 2. Verificar que stop_campaign_task() cree STOP_SIGNAL_FILE en disco
        res_stop = stop_campaign_task()
        assert res_stop["status"] == "stopping"
        assert os.path.exists(STOP_SIGNAL_FILE), "stop_campaign_task debe crear STOP_SIGNAL_FILE en disco"

        # 3. Verificar que _save_campaign_state_disk y _load_campaign_state_disk funcionen
        mock_state = {
            "status": "running",
            "filename": "prospectos_test.csv",
            "total": 100,
            "enviados": 25,
            "opt_out": 2,
            "ya_enviados": 5,
            "errores": 0,
            "current_contact": "Comercio Simulado (5491100000000)",
            "logs": ["[10:00:00] Test log"]
        }
        _save_campaign_state_disk(mock_state)
        assert os.path.exists(STATE_FILE), "STATE_FILE debe existir en disco"

        loaded = _load_campaign_state_disk()
        assert loaded is not None
        assert loaded["status"] == "running"
        assert loaded["enviados"] == 25

        # 4. Simular worker alternativo de Gunicorn: _campaign_task es None en memoria
        # get_campaign_status() debe leer del disco
        backup_task = outbound_mod._campaign_task
        outbound_mod._campaign_task = None

        status_from_disk = get_campaign_status()
        assert status_from_disk["total"] == 100
        assert status_from_disk["enviados"] == 25
        assert status_from_disk["current_contact"] == "Comercio Simulado (5491100000000)"

        # Restaurar memoria
        outbound_mod._campaign_task = backup_task

        # 5. Probar que STOP_SIGNAL_FILE interrumpe procesar_campana de inmediato
        # Crear CSV temporal con 2 filas y delay largo (10 segundos)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', suffix='.csv', delete=False) as f_csv:
            tmp_csv_path = f_csv.name
            writer = csv.writer(f_csv)
            writer.writerow(["Nombre del Local", "Teléfono", "Dirección"])
            writer.writerow(["Local Uno", "1122334455", "Av. Santa Fe 1000"])
            writer.writerow(["Local Dos", "1166778899", "Av. Cabildo 2000"])

        # Crear STOP_SIGNAL_FILE antes de la segunda fila
        if os.path.exists(STOP_SIGNAL_FILE):
            os.remove(STOP_SIGNAL_FILE)

        thread_done = threading.Event()
        res_container = {}

        def run_proc():
            res_container["res"] = procesar_campana(
                input_path=tmp_csv_path,
                delay=5,
                dry_run=True
            )
            thread_done.set()

        t = threading.Thread(target=run_proc, daemon=True)
        t.start()

        # Esperar 0.3s a que procese la fila 1 y entre al delay de pacing
        time.sleep(0.3)
        # Emitir señal en disco (como lo haría otro worker de Gunicorn)
        with open(STOP_SIGNAL_FILE, 'w') as f_sig:
            f_sig.write("STOP")

        # La espera debe interrumpirse rápidamente (< 1.5 segundos en vez de esperar 5s)
        finished_fast = thread_done.wait(timeout=2.0)
        assert finished_fast, "procesar_campana debió interrumpir la espera por STOP_SIGNAL_FILE en disco"
        res_camp = res_container.get("res")
        assert res_camp is not None
        assert res_camp["enviados"] == 1, "Solo debió procesar 1 fila antes de detenerse"

        if os.path.exists(tmp_csv_path):
            os.remove(tmp_csv_path)

        # 6. Probar que start_campaign_task() elimina STOP_SIGNAL_FILE previo
        # Crear STOP_SIGNAL_FILE
        with open(STOP_SIGNAL_FILE, 'w') as f_sig:
            f_sig.write("STOP")
        assert os.path.exists(STOP_SIGNAL_FILE)

        # Crear archivo sintético en leads/
        leads_dir = os.path.join(BASE_DIR, "leads")
        dummy_lead_name = "test_lead_dummy_start.csv"
        dummy_lead_path = os.path.join(leads_dir, dummy_lead_name)
        with open(dummy_lead_path, mode='w', encoding='utf-8-sig', newline='') as f_d:
            writer = csv.writer(f_d)
            writer.writerow(["Nombre del Local", "Teléfono", "Dirección"])
            writer.writerow(["Local Test", "1144556677", "Av. Rivadavia 1000"])

        # Asegurar que _campaign_task no figure como running
        outbound_mod._campaign_task = None
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)

        res_start = start_campaign_task(
            filename=dummy_lead_name,
            limit=1,
            delay=0,
            dry_run=True
        )
        assert res_start["status"] == "started"
        assert not os.path.exists(STOP_SIGNAL_FILE), "start_campaign_task debió eliminar STOP_SIGNAL_FILE"

        # Esperar que finalice
        time.sleep(0.5)
        if os.path.exists(dummy_lead_path):
            os.remove(dummy_lead_path)

    finally:
        # Limpieza final
        if os.path.exists(STOP_SIGNAL_FILE):
            os.remove(STOP_SIGNAL_FILE)
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)

    print("✅ TEST 8 PASADO: Señal .campaign_stop y estado .campaign_state.json sincronizan workers de forma desacoplada.")

def main():
    print("\n" + "="*70)
    print("🚀 INICIANDO TEST SUITE: CAMPAÑA OUTBOUND & RESPUESTAS FSM")
    print("="*70)

    test_send_whatsapp_template_payload()
    test_receiver_button_extraction()
    test_bot_engine_intercept_si_me_interesa()
    test_bot_engine_intercept_no_me_interesa()
    test_send_outbound_campaign_script()
    test_extraer_localidad_comprehensive()
    test_campaign_api_endpoints()
    test_multi_worker_disk_sync()

    print("\n" + "="*70)
    print("🎉 TODOS LOS TESTS DE CAMPAÑA OUTBOUND PASARON (100% OK)")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

