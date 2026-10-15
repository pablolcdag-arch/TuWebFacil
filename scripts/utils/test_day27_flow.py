#!/usr/bin/env python3
"""
Test Suite: Flujo Interactivo del Día 27 (Cierre del Trial de 30 días)
Verifica la detección en upsell_cron.py, la máquina de estados en bot_engine.py,
la persistencia en SQLite y el envío de comprobantes.
"""

import os
import sys
import json
import sqlite3
import datetime
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import bot_engine
from scripts.ops import upsell_cron

def banner(title):
    print(f"\n{'='*70}\n🧪 TEST DÍA 27: {title}\n{'='*70}")

def cleanup_test_data(phones, website_ids):
    db_path = bot_engine.get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        if phones:
            p_placeholders = ",".join("?" for _ in phones)
            c.execute(f"DELETE FROM user_sessions WHERE phone IN ({p_placeholders})", phones)
        if website_ids:
            w_placeholders = ",".join("?" for _ in website_ids)
            c.execute(f"DELETE FROM upsell_logs WHERE website_id IN ({w_placeholders})", website_ids)
        conn.commit()
    except Exception as e:
        print(f"Error en cleanup_test_data: {e}")
    finally:
        if conn:
            conn.close()

    for p in phones:
        bot_engine.user_states.pop(p, None)

def test_cron_detection_and_filtering():
    banner("1. Detección y Filtrado de Clientes en upsell_cron.py")
    test_web_ids = ["web_day26_id", "web_day27_id", "web_day28_paid_id"]
    test_phones = ["5491100000026", "5491100000027", "5491100000028"]
    cleanup_test_data(test_phones, test_web_ids)

    now = datetime.datetime.now(datetime.timezone.utc)
    t26 = (now - datetime.timedelta(days=26, hours=1)).isoformat()
    t27 = (now - datetime.timedelta(days=27, hours=2)).isoformat()
    t28 = (now - datetime.timedelta(days=28, hours=5)).isoformat()

    mock_websites_data = [
        {
            "id": "web_day26_id",
            "created_at": t26,
            "client_id": "cli_26",
            "clients": {"id": "cli_26", "phone": "5491100000026", "name": "Cliente 26 Días"}
        },
        {
            "id": "web_day27_id",
            "created_at": t27,
            "client_id": "cli_27",
            "clients": {"id": "cli_27", "phone": "5491100000027", "name": "Cliente 27 Días"}
        },
        {
            "id": "web_day28_paid_id",
            "created_at": t28,
            "client_id": "cli_28",
            "clients": {"id": "cli_28", "phone": "5491100000028", "name": "Cliente Ya Pagando"}
        }
    ]

    sent_messages = []

    def mock_send_buttons(to_phone, msg, buttons):
        sent_messages.append({"phone": to_phone, "msg": msg, "buttons": buttons})
        return True

    # Mock supabase client
    mock_sb = MagicMock()
    
    # Mock websites query
    mock_sb_websites = MagicMock()
    mock_sb.table.return_value = mock_sb_websites
    
    def table_router(table_name):
        table_mock = MagicMock()
        if table_name == "websites":
            # select().eq().is_().execute()
            exec_mock = MagicMock()
            exec_mock.data = mock_websites_data
            table_mock.select.return_value.eq.return_value.is_.return_value.execute.return_value = exec_mock
        elif table_name == "subscriptions":
            def sub_select(*args, **kwargs):
                eq_client = MagicMock()
                def eq_client_fn(col, val):
                    eq_status = MagicMock()
                    def eq_status_fn(status_col, status_val):
                        res = MagicMock()
                        if val == "cli_28":
                            # Active paid subscription
                            res.data = [{"plan_type": "premium", "status": "active"}]
                        elif val == "cli_27":
                            # Only gratis or none
                            res.data = [{"plan_type": "gratis", "status": "active"}]
                        else:
                            res.data = []
                        return MagicMock(execute=MagicMock(return_value=res))
                    eq_status.eq = eq_status_fn
                    return eq_status
                eq_client.eq = eq_client_fn
                return eq_client
            table_mock.select = sub_select
        return table_mock

    mock_sb.table.side_effect = table_router

    with patch.object(upsell_cron, "supabase", mock_sb), \
         patch.object(upsell_cron, "send_whatsapp_buttons", side_effect=mock_send_buttons):
        
        # Ejecutar 1ra pasada
        upsell_cron.run_upsell_check()

        assert len(sent_messages) == 1, f"Se esperaba exactamente 1 mensaje enviado, pero se enviaron {len(sent_messages)}"
        sent = sent_messages[0]
        assert sent["phone"] == "5491100000027", f"El destinatario debió ser Cliente 27 Días, fue: {sent['phone']}"
        assert "3 días finalizan tus 30 días de prueba gratuita" in sent["msg"], "Texto de mensaje incorrecto"
        assert "$2.000" in sent["msg"] and "$10.500" in sent["msg"], "Montos no informados en el texto"
        assert "tuweblista" in sent["msg"], "Alias tuweblista no mencionado en el texto"

        # Verificar botones
        btn_ids = [b["id"] for b in sent["buttons"]]
        assert "TRIAL_SUBDOMINIO" in btn_ids, "Falta botón TRIAL_SUBDOMINIO"
        assert "TRIAL_DOMINIO" in btn_ids, "Falta botón TRIAL_DOMINIO"
        for b in sent["buttons"]:
            assert len(b["title"]) <= 20, f"Título de botón excede límite de 20 chars de WhatsApp: '{b['title']}' ({len(b['title'])})"

        # Verificar que se registró en upsell_logs
        db_path = bot_engine.get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT website_id FROM upsell_logs WHERE website_id = 'web_day27_id'")
        row = c.fetchone()
        conn.close()
        assert row is not None, "web_day27_id no fue registrada en upsell_logs"

        # Ejecutar 2da pasada (No debe reenviar nada)
        sent_messages.clear()
        upsell_cron.run_upsell_check()
        assert len(sent_messages) == 0, f"No debió reenviar mensaje a web ya registrada en upsell_logs (se enviaron {len(sent_messages)})"

    cleanup_test_data(test_phones, test_web_ids)
    print("✅ TEST 1 PASADO: Detección precisa de 27 días, exclusión de suscripciones pagas y sin duplicados.")

def test_option1_subdominio_flow():
    banner("2. Flujo Opción 1: Subdominio ($2.000)")
    test_phone = "5491155550001"
    cleanup_test_data([test_phone], [])

    inputs_to_test = [
        "TRIAL_SUBDOMINIO",   # Clic de botón
        "trial_subdominio",   # ID en minúscula
        "1",                  # Opción numérica desde IDLE
        "subdominio",         # Palabra clave
        "opcion 1",           # Texto sin tilde
        "Opción 1",           # Texto con tilde
        "  OPCION 1  "        # Con espacios y mayúsculas
    ]

    for user_input in inputs_to_test:
        bot_engine.clear_user_state(test_phone)
        assert bot_engine.get_user_state(test_phone)["estado"] == bot_engine.IDLE

        sent_messages = []
        with patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):
            bot_engine.procesar_mensaje(test_phone, user_input, "Juan Perez")

        # Verificar estado
        state = bot_engine.get_user_state(test_phone)
        assert state["estado"] == bot_engine.WAITING_FOR_RECEIPT, f"Fallo con input '{user_input}': Estado es {state['estado']}"
        assert state["temp_data"] == {"plan": "subdominio", "monto": 2000}, f"Fallo con input '{user_input}': temp_data es {state['temp_data']}"

        # Verificar persistencia en disco SQLite
        db_path = bot_engine.get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT estado, temp_data FROM user_sessions WHERE phone = ?", (test_phone,))
        db_row = c.fetchone()
        conn.close()
        assert db_row is not None, f"No se persistió en SQLite con input '{user_input}'"
        assert db_row[0] == bot_engine.WAITING_FOR_RECEIPT
        assert json.loads(db_row[1]) == {"plan": "subdominio", "monto": 2000}

        # Verificar mensaje enviado
        assert len(sent_messages) >= 1, f"No se envió mensaje con input '{user_input}'"
        last_msg = sent_messages[-1]
        assert "tuweblista" in last_msg.lower(), "Mensaje no contiene alias tuweblista"
        assert "2.000" in last_msg, "Mensaje no contiene monto 2.000"
        assert "comprobante" in last_msg.lower(), "Mensaje no solicita comprobante"

    cleanup_test_data([test_phone], [])
    print("✅ TEST 2 PASADO: Opción 1 transiciona correctamente a WAITING_FOR_RECEIPT ($2.000) con todas las variantes.")

def test_option2_dominio_flow():
    banner("3. Flujo Opción 2: Dominio Propio ($10.500) y Búsqueda")
    test_phone = "5491155550002"
    cleanup_test_data([test_phone], [])

    inputs_to_test = [
        "TRIAL_DOMINIO",      # Clic de botón
        "trial_dominio",      # ID en minúscula
        "2",                  # Opción numérica desde IDLE
        "dominio",            # Palabra clave
        "opcion 2",           # Texto sin tilde
        "Opción 2",           # Texto con tilde
        "  OPCION 2  ",       # Con espacios y mayúsculas
        "dominio propio"      # Frase completa
    ]

    for user_input in inputs_to_test:
        bot_engine.clear_user_state(test_phone)
        assert bot_engine.get_user_state(test_phone)["estado"] == bot_engine.IDLE

        sent_messages = []
        with patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):
            bot_engine.procesar_mensaje(test_phone, user_input, "Juan Perez")

        # Verificar transición inicial a WAITING_FOR_DOMAIN_NAME
        state = bot_engine.get_user_state(test_phone)
        assert state["estado"] == bot_engine.WAITING_FOR_DOMAIN_NAME, f"Fallo con input '{user_input}': Estado es {state['estado']}"
        assert state["temp_data"] == {"plan": "custom_domain", "monto": 10500}, f"Fallo con input '{user_input}': temp_data es {state['temp_data']}"

        # Verificar mensaje solicitando nombre de dominio
        assert len(sent_messages) >= 1
        assert "dominio .com.ar" in sent_messages[-1].lower()

    # Ahora simular la búsqueda del nombre del dominio
    # Caso 1: Dominio disponible en NIC.ar
    mock_whois_available = MagicMock(stdout="El dominio no se encuentra registrado en NIC Argentina")
    sent_messages.clear()
    with patch("subprocess.run", return_value=mock_whois_available), \
         patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):
        bot_engine.procesar_mensaje(test_phone, "panaderiasanpedro", "Juan Perez")

    # Debe pasar a WAITING_FOR_RECEIPT con dominio, plan y monto
    state = bot_engine.get_user_state(test_phone)
    assert state["estado"] == bot_engine.WAITING_FOR_RECEIPT, f"Estado tras whois disponible debió ser WAITING_FOR_RECEIPT, fue {state['estado']}"
    assert state["temp_data"].get("dominio") == "panaderiasanpedro.com.ar"
    assert state["temp_data"].get("plan") == "custom_domain"
    assert state["temp_data"].get("monto") == 10500

    # Verificar persistencia en SQLite
    db_path = bot_engine.get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT estado, temp_data FROM user_sessions WHERE phone = ?", (test_phone,))
    db_row = c.fetchone()
    conn.close()
    assert db_row[0] == bot_engine.WAITING_FOR_RECEIPT
    persisted_data = json.loads(db_row[1])
    assert persisted_data.get("dominio") == "panaderiasanpedro.com.ar"
    assert persisted_data.get("monto") == 10500

    cleanup_test_data([test_phone], [])
    print("✅ TEST 3 PASADO: Opción 2 transiciona a WAITING_FOR_DOMAIN_NAME y tras búsqueda exitosa a WAITING_FOR_RECEIPT con datos completos.")

def test_receipt_submission_flow():
    banner("4. Recepción de Comprobante de Pago y Persistencia")
    test_phone = "5491155550003"
    cleanup_test_data([test_phone], [])

    # Preparar usuario en WAITING_FOR_RECEIPT (Simulando que eligió Subdominio)
    bot_engine.set_user_state(test_phone, bot_engine.WAITING_FOR_RECEIPT, {"plan": "subdominio", "monto": 2000, "dominio": ""})

    # Simular envío de imagen (comprobante)
    mock_supabase = MagicMock()
    # Mock client lookup
    mock_cli_res = MagicMock(data=[{"id": "client_abc_123"}])
    mock_supabase.table.return_value.select.return_value.ilike.return_value.execute.return_value = mock_cli_res

    # Mock payment insert
    mock_payments = MagicMock()
    mock_supabase.table.return_value.insert = mock_payments

    sent_messages = []
    with patch.object(bot_engine, "supabase", mock_supabase), \
         patch.object(bot_engine, "download_whatsapp_media", return_value=True), \
         patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):

        bot_engine.procesar_mensaje(
            test_phone,
            texto="",
            nombre="Carlos Gomez",
            msg_type="image",
            media_id="media_img_9999"
        )

    # Verificar que el pago se registró
    mock_payments.assert_called_once()
    payment_payload = mock_payments.call_args[0][0]
    assert payment_payload["client_id"] == "client_abc_123"
    assert payment_payload["status"] == "uploaded"
    assert "receipt_" in payment_payload["payment_method"]

    # Verificar que el estado del usuario volvió a IDLE
    final_state = bot_engine.get_user_state(test_phone)
    assert final_state["estado"] == bot_engine.IDLE, f"El estado debió resetearse a IDLE, quedó en: {final_state['estado']}"

    # Verificar persistencia de IDLE en SQLite
    db_path = bot_engine.get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT estado FROM user_sessions WHERE phone = ?", (test_phone,))
    db_row = c.fetchone()
    conn.close()
    assert db_row[0] == bot_engine.IDLE

    # Verificar confirmación al usuario
    assert any("pago verificado" in m.lower() or "recibimos el comprobante" in m.lower() for m in sent_messages)

    cleanup_test_data([test_phone], [])
    print("✅ TEST 4 PASADO: Comprobante registrado en payments, confirmación enviada y sesión reseteada a IDLE.")

def test_escape_words():
    banner("5. Palabras de Escape ('menu', 'cancelar', 'volver')")
    test_phone = "5491155550004"
    cleanup_test_data([test_phone], [])

    for escape_word in ["cancelar", "menu", "volver", "inicio"]:
        bot_engine.set_user_state(test_phone, bot_engine.WAITING_FOR_RECEIPT, {"plan": "subdominio", "monto": 2000})
        
        sent_messages = []
        with patch.object(bot_engine, "send_whatsapp_list") as mock_list, \
             patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):
            bot_engine.procesar_mensaje(test_phone, escape_word, "Usuario")

        state = bot_engine.get_user_state(test_phone)
        assert state["estado"] == bot_engine.MAIN_MENU, f"Fallo al escapar con '{escape_word}': Estado es {state['estado']}"

    cleanup_test_data([test_phone], [])
    print("✅ TEST 5 PASADO: Palabras de escape limpian el estado y muestran el menú principal.")

def run_all_tests():
    banner("EJECUTANDO SUITE COMPLETA DÍA 27 (TRIAL CLOSING)")
    test_cron_detection_and_filtering()
    test_option1_subdominio_flow()
    test_option2_dominio_flow()
    test_receipt_submission_flow()
    test_escape_words()
    print(f"\n{'='*70}\n🎉 TODOS LOS TESTS DEL DÍA 27 PASARON EXITOSAMENTE (100% OK)\n{'='*70}\n")

if __name__ == "__main__":
    run_all_tests()

