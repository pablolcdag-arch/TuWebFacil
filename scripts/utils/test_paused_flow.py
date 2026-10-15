#!/usr/bin/env python3
"""
Test Suite: Pantalla de Sitio Pausado (Día 30) y Flujo de Reactivación por WhatsApp
Verifica el renderizado de paused.html en app.py, el cron de suspensión en daily_billing_cron.py,
y la máquina de estados de reactivación en bot_engine.py.
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

import app
import bot_engine
import daily_billing_cron

def banner(title):
    print(f"\n{'='*70}\n🧪 TEST SITIO PAUSADO: {title}\n{'='*70}")

def cleanup_test_data(phones):
    db_path = bot_engine.get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()
        if phones:
            p_placeholders = ",".join("?" for _ in phones)
            c.execute(f"DELETE FROM user_sessions WHERE phone IN ({p_placeholders})", phones)
        conn.commit()
    except Exception as e:
        print(f"Error en cleanup_test_data: {e}")
    finally:
        if conn:
            conn.close()

    for p in phones:
        bot_engine.user_states.pop(p, None)

def test_paused_html_rendering_in_app():
    banner("1. Renderizado de paused.html en Subdominios y Custom Domains (app.py)")
    client = app.app.test_client()

    mock_maintenance_web = {
        "id": "web_paused_123",
        "client_id": "client_abc",
        "subdomain": "panaderiaperez",
        "custom_domain": "panaderiaperez.com.ar",
        "status": "maintenance"
    }

    # Mock supabase para simular búsqueda en websites
    mock_sb = MagicMock()
    
    def table_router(table_name):
        t_mock = MagicMock()
        if table_name == "websites":
            def select_fn(*args, **kwargs):
                s_mock = MagicMock()
                def eq_fn(col, val):
                    res_mock = MagicMock()
                    if col == "subdomain" and val == "panaderiaperez":
                        res_mock.data = [mock_maintenance_web]
                    elif col == "custom_domain" and val == "panaderiaperez.com.ar":
                        res_mock.data = [mock_maintenance_web]
                    else:
                        res_mock.data = []
                    return MagicMock(execute=MagicMock(return_value=res_mock))
                s_mock.eq = eq_fn
                return s_mock
            t_mock.select = select_fn
        return t_mock

    mock_sb.table.side_effect = table_router

    with patch.object(app, "supabase", mock_sb):
        # 1.A Probar subdominio en maintenance (panaderiaperez.tuweblista.com.ar)
        res_sub = client.get('/', headers={'Host': 'panaderiaperez.tuweblista.com.ar'})
        assert res_sub.status_code == 402, f"Se esperaba status 402, se obtuvo: {res_sub.status_code}"
        html_sub = res_sub.data.decode('utf-8')
        
        # Verificaciones de contenido en paused.html
        assert "Sitio en pausa temporal" in html_sub, "Título principal 'Sitio en pausa temporal' no encontrado"
        assert "Este sitio web se encuentra pausado temporalmente." in html_sub, "Bajada para visitantes no encontrada"
        assert "¿Sos el titular de este negocio?" in html_sub, "Bloque para el titular no encontrado"
        assert "$2.000/mes" in html_sub, "Monto de $2.000/mes no encontrado"
        assert "Reactivar mi web por WhatsApp" in html_sub, "Texto del botón no encontrado"
        assert "https://wa.me/" in html_sub, "Enlace de WhatsApp no encontrado"
        assert "text=Quiero%20reactivar%20mi%20web" in html_sub, "Texto predeterminado de WhatsApp no encontrado"
        assert "TuWebLista" in html_sub, "Marca TuWebLista no encontrada"
        assert "TuWebFacil" not in html_sub, "Aparece marca vieja TuWebFacil"
        assert "<h1>Sitio suspendido temporalmente.</h1>" not in html_sub, "Aparece texto plano hardcodeado viejo"

        # 1.B Probar custom domain en maintenance (panaderiaperez.com.ar)
        res_custom = client.get('/', headers={'Host': 'panaderiaperez.com.ar'})
        assert res_custom.status_code == 402, f"Se esperaba status 402 en custom domain, se obtuvo: {res_custom.status_code}"
        html_custom = res_custom.data.decode('utf-8')
        assert "Sitio en pausa temporal" in html_custom
        assert "Reactivar mi web por WhatsApp" in html_custom
        assert "TuWebLista" in html_custom
        assert "TuWebFacil" not in html_custom

    print("✅ TEST 1 PASADO: paused.html se renderiza con status 402, diseño moderno y datos correctos en subdominio y custom domain.")

def test_daily_billing_cron_detection():
    banner("2. Detección y Pausa de Webs con Trial Vencido (daily_billing_cron.py)")
    
    ahora = datetime.datetime.utcnow()
    t25 = (ahora - datetime.timedelta(days=25)).isoformat()
    t32 = (ahora - datetime.timedelta(days=32)).isoformat()
    t35 = (ahora - datetime.timedelta(days=35)).isoformat()

    mock_websites_list = [
        {
            "id": "web_25_days",
            "subdomain": "negocio-joven",
            "created_at": t25,
            "client_id": "cli_25",
            "status": "published",
            "clients": {"id": "cli_25", "name": "Cliente Joven", "phone": "5491125252525"}
        },
        {
            "id": "web_32_paid",
            "subdomain": "negocio-pago",
            "created_at": t32,
            "client_id": "cli_32",
            "status": "published",
            "clients": {"id": "cli_32", "name": "Cliente Pagando", "phone": "5491132323232"}
        },
        {
            "id": "web_35_unpaid",
            "subdomain": "negocio-vencido",
            "created_at": t35,
            "client_id": "cli_35",
            "status": "published",
            "clients": {"id": "cli_35", "name": "Cliente Vencido", "phone": "5491135353535"}
        }
    ]

    updated_to_maintenance = []
    sent_whatsapp = []

    mock_sb = MagicMock()
    
    def table_router(table_name):
        t_mock = MagicMock()
        if table_name == "subscriptions":
            def select_fn(*args, **kwargs):
                s_mock = MagicMock()
                def eq_fn(col, val):
                    res_mock = MagicMock()
                    if col == "status" and val == "payment_failed":
                        # No hay pagos fallidos en esta prueba
                        res_mock.data = []
                    elif col == "client_id":
                        eq_status = MagicMock()
                        def eq_status_fn(s_col, s_val):
                            sub_res = MagicMock()
                            if val == "cli_32":
                                # Activo con plan pagado
                                sub_res.data = [{"plan_type": "premium", "status": "active"}]
                            elif val == "cli_35":
                                # Sin suscripción paga (plan gratis o None)
                                sub_res.data = [{"plan_type": "gratis", "status": "active"}]
                            else:
                                sub_res.data = []
                            return MagicMock(execute=MagicMock(return_value=sub_res))
                        eq_status.eq = eq_status_fn
                        return eq_status
                    else:
                        res_mock.data = []
                    return MagicMock(execute=MagicMock(return_value=res_mock))
                s_mock.eq = eq_fn
                return s_mock
            t_mock.select = select_fn
        elif table_name == "websites":
            def select_fn(*args, **kwargs):
                s_mock = MagicMock()
                def eq_fn(col, val):
                    res_mock = MagicMock()
                    if col == "status" and val == "published":
                        res_mock.data = mock_websites_list
                    else:
                        res_mock.data = []
                    return MagicMock(execute=MagicMock(return_value=res_mock))
                s_mock.eq = eq_fn
                return s_mock
            t_mock.select = select_fn
            
            def update_fn(payload):
                u_mock = MagicMock()
                def eq_fn(col, val):
                    if payload.get("status") == "maintenance":
                        updated_to_maintenance.append(val)
                    return MagicMock(execute=MagicMock())
                u_mock.eq = eq_fn
                return u_mock
            t_mock.update = update_fn
        return t_mock

    mock_sb.table.side_effect = table_router

    with patch.object(daily_billing_cron, "supabase", mock_sb), \
         patch.object(daily_billing_cron, "send_whatsapp_message", side_effect=lambda to, msg: sent_whatsapp.append({"to": to, "msg": msg})):
        
        paused_webs = daily_billing_cron.run_billing_check()

        # Solo web_35_unpaid debe haber sido pausada
        assert "web_35_unpaid" in updated_to_maintenance, "web_35_unpaid no fue marcada como maintenance"
        assert "web_25_days" not in updated_to_maintenance, "web_25_days (<30 días) fue pausada indebidamente"
        assert "web_32_paid" not in updated_to_maintenance, "web_32_paid (con suscripción paga) fue pausada indebidamente"
        assert len(updated_to_maintenance) == 1, f"Se esperaba 1 web pausada, se pausaron: {len(updated_to_maintenance)}"

        # Verificar reporte al admin
        assert len(sent_whatsapp) >= 1, "No se envió reporte al admin"
        admin_report = sent_whatsapp[0]["msg"]
        assert "TuWebLista" in admin_report, "Reporte no usa marca TuWebLista"
        assert "TuWebFacil" not in admin_report, "Reporte sigue mencionando TuWebFacil"
        assert "negocio-vencido" in admin_report, "Reporte no incluye el slug de la web pausada"

    print("✅ TEST 2 PASADO: daily_billing_cron pausó únicamente la web vencida (>= 30 días sin pago) y notificó al admin con branding correcto.")

def test_reactivation_intent_in_bot():
    banner("3. Detección de Reactivación y Flujo de Pago en bot_engine.py")
    test_phone = "5491177770001"
    cleanup_test_data([test_phone])

    test_inputs = [
        "Quiero reactivar mi web",
        "quiero reactivar mi web",
        "reactivar mi web",
        "Reactivar",
        "  REACTIVAR MI WEB  ",
        "quiero reactivar"
    ]

    for user_input in test_inputs:
        bot_engine.clear_user_state(test_phone)
        assert bot_engine.get_user_state(test_phone)["estado"] == bot_engine.IDLE

        sent_messages = []
        with patch.object(bot_engine, "obtener_web_del_cliente", return_value={"slug": "mitienda", "website_id": "web_123"}), \
             patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):
            bot_engine.procesar_mensaje(test_phone, user_input, "Ana López")

        # Verificar estado
        state = bot_engine.get_user_state(test_phone)
        assert state["estado"] == bot_engine.WAITING_FOR_RECEIPT, f"Fallo con input '{user_input}': Estado es {state['estado']}"
        assert state["temp_data"].get("accion") == "reactivacion", f"Fallo en accion de temp_data: {state['temp_data']}"
        assert state["temp_data"].get("monto") == 2000, f"Fallo en monto de temp_data: {state['temp_data']}"

        # Verificar mensaje amigable
        assert len(sent_messages) >= 1
        msg = sent_messages[-1]
        assert "¡Hola Ana López! 👋 Tu web está guardada y lista para reactivarse." in msg
        assert "$2.000/mes" in msg
        assert "$10.500" in msg
        assert "tuweblista" in msg
        assert "comprobante" in msg.lower()

        # Verificar persistencia en SQLite
        db_path = bot_engine.get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT estado, temp_data FROM user_sessions WHERE phone = ?", (test_phone,))
        db_row = c.fetchone()
        conn.close()
        assert db_row[0] == bot_engine.WAITING_FOR_RECEIPT
        persisted = json.loads(db_row[1])
        assert persisted["accion"] == "reactivacion"
        assert persisted["monto"] == 2000

    # Simular envío de comprobante (imagen) en estado WAITING_FOR_RECEIPT de reactivación
    mock_supabase = MagicMock()
    mock_cli_res = MagicMock(data=[{"id": "client_reactivate_1"}])
    mock_supabase.table.return_value.select.return_value.ilike.return_value.execute.return_value = mock_cli_res
    mock_payments = MagicMock()
    mock_supabase.table.return_value.insert = mock_payments

    sent_messages.clear()
    with patch.object(bot_engine, "supabase", mock_supabase), \
         patch.object(bot_engine, "download_whatsapp_media", return_value=True), \
         patch.object(bot_engine, "send_whatsapp_message", side_effect=lambda w, m: sent_messages.append(m)):
        bot_engine.procesar_mensaje(
            test_phone,
            texto="",
            nombre="Ana López",
            msg_type="image",
            media_id="media_reactivate_receipt"
        )

    # Verificar registro en tabla payments y reseteo a IDLE
    mock_payments.assert_called_once()
    final_state = bot_engine.get_user_state(test_phone)
    assert final_state["estado"] == bot_engine.IDLE, f"El estado debió volver a IDLE tras enviar comprobante, quedó en {final_state['estado']}"

    cleanup_test_data([test_phone])
    print("✅ TEST 3 PASADO: Detección de reactivación, transición a WAITING_FOR_RECEIPT, guardado de comprobante y vuelta a IDLE.")

def test_reactivation_escape():
    banner("4. Palabras de Escape desde Flujo de Reactivación")
    test_phone = "5491177770002"
    cleanup_test_data([test_phone])

    for escape_cmd in ["cancelar", "menu", "volver"]:
        bot_engine.set_user_state(test_phone, bot_engine.WAITING_FOR_RECEIPT, {"accion": "reactivacion", "monto": 2000})
        with patch.object(bot_engine, "send_whatsapp_list") as mock_list, \
             patch.object(bot_engine, "send_whatsapp_message"):
            bot_engine.procesar_mensaje(test_phone, escape_cmd, "Ana López")

        state = bot_engine.get_user_state(test_phone)
        assert state["estado"] == bot_engine.MAIN_MENU, f"Fallo al escapar con '{escape_cmd}': Estado es {state['estado']}"

    cleanup_test_data([test_phone])
    print("✅ TEST 4 PASADO: Palabras de escape cancelan correctamente el flujo de reactivación.")

def run_all_tests():
    banner("EJECUTANDO SUITE COMPLETA DE SITIO PAUSADO Y REACTIVACIÓN")
    test_paused_html_rendering_in_app()
    test_daily_billing_cron_detection()
    test_reactivation_intent_in_bot()
    test_reactivation_escape()
    print(f"\n{'='*70}\n🎉 TODOS LOS TESTS DE SITIO PAUSADO Y REACTIVACIÓN PASARON EXITOSAMENTE (100% OK)\n{'='*70}\n")

if __name__ == "__main__":
    run_all_tests()

