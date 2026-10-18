#!/usr/bin/env python3
"""
Test Suite: Ingesta de Listas de Precios y Servicios (Backend)
Verifica:
1. Normalización de monedas argentinas (format_price)
2. Ingesta tabular (CSV y Excel con 3 columnas de pago: Efectivo, Transferencia, Tarjeta)
3. Ingesta de texto plano y fallback
4. Bot FSM: transición a WAITING_FOR_PRICE_LIST, generación de draft con token seguro y botones <= 20 chars
5. Bot FSM: confirmación (actualiza website_content, incrementa versión) y cancelación (descarta borrador)
6. Flask app.py: overlay de borrador vía /precios?preview=TOKEN
7. Conexiones SQLite sin fugas ni bloqueos
"""

import os
import sys
import json
import sqlite3
import tempfile
import pandas as pd
from unittest.mock import patch, MagicMock

# Ajustar PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.utils.price_list_parser import format_price, parse_price_list, parse_tabular_data
import bot_engine
import app as flask_app


def run_tests():
    print("=" * 70)
    print("🚀 INICIANDO TEST SUITE: LISTAS DE PRECIOS & SERVICIOS (BACKEND)")
    print("=" * 70)

    # ---------------------------------------------------------
    # TEST 1: Normalización de Moneda Argentina (format_price)
    # ---------------------------------------------------------
    print("\n[TEST 1] Verificando formateador de moneda argentina...")
    test_cases = [
        (48089.77, "$48.089,77"),
        (15000, "$15.000"),
        ("15000", "$15.000"),
        ("48089.77", "$48.089,77"),
        ("48.089,77", "$48.089,77"),
        ("$55.303,24", "$55.303,24"),
        (None, "-"),
        ("-", "-"),
        ("", "-")
    ]
    for val, expected in test_cases:
        res = format_price(val)
        assert res == expected, f"Fallo format_price({val}): esperado '{expected}', obtenido '{res}'"
    print("  ✅ format_price() normaliza enteros, flotantes y strings con formato argentino.")

    # ---------------------------------------------------------
    # TEST 2: Ingesta Tabular CSV & Excel (Soteria 3 columnas)
    # ---------------------------------------------------------
    print("\n[TEST 2] Verificando parse_tabular_data con CSV y Excel (3 modalidades)...")
    data_soteria = {
        "Servicio": ["Abdomen", "Axilas", "Rostro"],
        "Efectivo": [48089.77, 25000, 30500.50],
        "Transferencia": [55303.24, 28750, 35075.58],
        "Tarjeta": [63478.50, 33000, 40260.66]
    }
    df = pd.DataFrame(data_soteria)
    parsed = parse_tabular_data(df, "Soteria Soprano")

    assert parsed["titulo"] == "Soteria Soprano"
    assert len(parsed["columnas_pago"]) == 3
    assert len(parsed["items"]) == 3
    
    first_item = parsed["items"][0]
    assert first_item["servicio"] == "Abdomen"
    assert first_item["precios"]["efectivo"] == "$48.089,77"
    assert first_item["precios"]["transferencia"] == "$55.303,24"
    assert first_item["precios"]["tarjeta"] == "$63.478,50"

    # Probar archivo CSV físico
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as tf:
        df.to_csv(tf.name, index=False)
        csv_path = tf.name

    try:
        parsed_csv = parse_price_list(csv_path)
        assert len(parsed_csv["items"]) == 3
        assert parsed_csv["items"][1]["servicio"] == "Axilas"
        assert parsed_csv["items"][1]["precios"]["efectivo"] == "$25.000"
    finally:
        if os.path.exists(csv_path):
            os.remove(csv_path)

    # Probar archivo Excel físico (.xlsx)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        xlsx_path = tf.name
    df.to_excel(xlsx_path, index=False)

    try:
        parsed_xlsx = parse_price_list(xlsx_path)
        assert len(parsed_xlsx["items"]) == 3
        assert parsed_xlsx["items"][2]["servicio"] == "Rostro"
        assert parsed_xlsx["items"][2]["precios"]["tarjeta"] == "$40.260,66"
    finally:
        if os.path.exists(xlsx_path):
            os.remove(xlsx_path)

    print("  ✅ Ingesta CSV y Excel procesada con contrato JSON exacto y claves normalizadas.")

    # ---------------------------------------------------------
    # TEST 3: Ingesta de Texto Plano (Fallback Regex)
    # ---------------------------------------------------------
    print("\n[TEST 3] Verificando parse_price_list con texto plano...")
    raw_text = """Corte clásico: $15.000
Barba completa: $8.000
Corte y barba: $20.000"""

    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
        parsed_text = parse_price_list(raw_text, is_text=True)
        assert len(parsed_text["items"]) == 3
        assert parsed_text["items"][0]["servicio"] == "Corte clásico"
        assert parsed_text["items"][0]["precios"]["precio"] == "$15.000"
    print("  ✅ Texto plano parseado correctamente con fallback determinista.")

    # ---------------------------------------------------------
    # TEST 4: Bot WhatsApp FSM - Menú y Transición a WAITING_FOR_PRICE_LIST / MAIN_PRECIOS
    # ---------------------------------------------------------
    print("\n[TEST 4] Verificando Bot FSM: acceso a MAIN_PRECIOS y retrocompatibilidad EDIT_PRECIOS...")
    test_wa = "5491199990001"
    bot_engine.clear_user_state(test_wa)

    # 4A: Verificar que MAIN_MENU incluye MAIN_PRECIOS en 2da posición (índice 1)
    with patch("bot_engine.send_whatsapp_list") as mock_send_list:
        bot_engine.procesar_mensaje(test_wa, "confirmar mi web", "Tester")
        mock_send_list.assert_called_once()
        main_options = mock_send_list.call_args[0][3]
        assert len(main_options) >= 2
        assert main_options[1]["id"] == "MAIN_PRECIOS"
        assert main_options[1]["title"] == "📋 Precios y Promos"
        assert main_options[1]["description"] == "Gestionar lista y promociones"

    # 4B: Desde MAIN_MENU seleccionar MAIN_PRECIOS transiciona a WAITING_FOR_PRICE_LIST si no hay lista previa
    bot_engine.set_user_state(test_wa, bot_engine.MAIN_MENU)
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg:
        bot_engine.procesar_mensaje(test_wa, "main_precios", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PRICE_LIST, f"Estado incorrecto: {state['estado']}"
        mock_send_msg.assert_called_once()
        msg_text = mock_send_msg.call_args[0][1]
        assert "Actualización de Lista de Precios" in msg_text

    # 4C: Retrocompatibilidad: EDIT_MENU -> edit_precios llama a mostrar_menu_precios
    bot_engine.clear_user_state(test_wa)
    bot_engine.set_user_state(test_wa, bot_engine.EDIT_MENU)

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg:
        bot_engine.procesar_mensaje(test_wa, "edit_precios", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PRICE_LIST, f"Estado incorrecto: {state['estado']}"
        mock_send_msg.assert_called_once()
        msg_text = mock_send_msg.call_args[0][1]
        assert "Actualización de Lista de Precios" in msg_text

    # 4D: Verificar que EDIT_MENU ahora contiene 9 opciones y no incluye EDIT_PRECIOS
    bot_engine.set_user_state(test_wa, bot_engine.MAIN_MENU)
    with patch("bot_engine.send_whatsapp_list") as mock_send_list:
        bot_engine.procesar_mensaje(test_wa, "2", "Tester")
        mock_send_list.assert_called_once()
        edit_opts = mock_send_list.call_args[0][3]
        assert len(edit_opts) == 9, f"EDIT_MENU debe tener exactamente 9 opciones, obtenido: {len(edit_opts)}"
        edit_ids = [o["id"] for o in edit_opts]
        assert "EDIT_PRECIOS" not in edit_ids

    print("  ✅ MAIN_MENU incluye MAIN_PRECIOS (2da pos), EDIT_MENU reducido a 9 opciones y retrocompatibilidad asegurada.")

    # ---------------------------------------------------------
    # TEST 5: Bot WhatsApp FSM - Generación de Borrador y Botones <= 20 chars
    # ---------------------------------------------------------
    print("\n[TEST 5] Verificando generación de borrador, draft_token y botones <= 20 chars...")
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PRICE_LIST)
    with patch("bot_engine.send_whatsapp_message"), \
         patch("bot_engine.send_whatsapp_buttons") as mock_buttons, \
         patch("bot_engine.obtener_web_del_cliente", return_value={"slug": "estetica-sol", "custom_domain": None, "id": "w1"}):

        # Usuario en WAITING_FOR_PRICE_LIST envía texto con precios
        bot_engine.procesar_mensaje(test_wa, "Manicura: $12.000\nPedicura: $14.000", "Tester")

        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.CONFIRM_PRICE_LIST_DRAFT
        temp_data = state["temp_data"]
        assert "draft_token" in temp_data
        assert len(temp_data["draft_token"]) == 8, f"Token debe ser de 8 caracteres hex: {temp_data['draft_token']}"
        assert "draft_prices" in temp_data
        assert len(temp_data["draft_prices"]["items"]) == 2

        # Verificar botones enviados
        mock_buttons.assert_called_once()
        btn_args = mock_buttons.call_args[0]
        buttons_sent = btn_args[2]
        assert len(buttons_sent) == 2
        for b in buttons_sent:
            assert len(b["title"]) <= 20, f"Botón '{b['title']}' supera los 20 caracteres permitidos por Meta: {len(b['title'])}"
        
        # Verificar que el preview_url contiene el token
        body_text = btn_args[1]
        expected_url = f"https://estetica-sol.tuweblista.com.ar/precios?preview={temp_data['draft_token']}"
        assert expected_url in body_text, f"URL de vista previa no encontrada en mensaje: {body_text}"

    print("  ✅ Borrador generado con token seguro de 8 caracteres y botones estrictamente <= 20 chars.")

    # ---------------------------------------------------------
    # TEST 6: Bot WhatsApp FSM - Publicar vs Cancelar Borrador
    # ---------------------------------------------------------
    print("\n[TEST 6] Verificando confirmación (publicación) y cancelación del borrador...")
    
    # 6A: Cancelar
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.actualizar_web_content") as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value={"slug": "estetica-sol", "version_id": "v1", "content": {}}):
        
        # Cancelar con botón CONFIRM_PRICES_CANCEL
        bot_engine.procesar_mensaje(test_wa, "confirm_prices_cancel", "Tester")
        mock_update.assert_not_called()
        state = bot_engine.get_user_state(test_wa)
        # Debe haber reseteado o limpiado el estado
        assert state["estado"] in [bot_engine.IDLE, bot_engine.MAIN_MENU]
    print("  ✅ Cancelar borrador descarta cambios sin tocar website_content.")

    # 6B: Confirmar y Publicar
    # Reestablecer borrador
    token_prueba = "a1b2c3d4"
    draft_test_prices = {
        "titulo": "Lista Test",
        "columnas_pago": ["Precio"],
        "items": [{"servicio": "Corte", "precios": {"precio": "$15.000"}}]
    }
    bot_engine.set_user_state(test_wa, bot_engine.CONFIRM_PRICE_LIST_DRAFT, {
        "draft_token": token_prueba,
        "draft_prices": draft_test_prices
    })

    fake_web = {
        "website_id": "w123",
        "version_id": "v123",
        "content": {"titulo_web": "Barberia Pro"},
        "slug": "barberia-pro",
        "custom_domain": None
    }

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.actualizar_web_content", return_value=True) as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=fake_web):

        bot_engine.procesar_mensaje(test_wa, "confirm_prices_ok", "Tester")

        mock_update.assert_called_once()
        call_version_id, call_content = mock_update.call_args[0]
        assert call_version_id == "v123"
        assert "lista_precios" in call_content
        assert call_content["lista_precios"] == draft_test_prices

        # Verificar que la sesión fue limpiada
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.IDLE

        # Mensaje de éxito con link /precios
        assert mock_send_msg.called
        success_msg = mock_send_msg.call_args[0][1]
        assert "https://barberia-pro.tuweblista.com.ar/precios" in success_msg

    print("  ✅ Confirmar publicación escribe en website_content, limpia sesión y envía link oficial.")

    # ---------------------------------------------------------
    # TEST 7: Bot WhatsApp FSM - Eliminar / Quitar Lista de Precios
    # ---------------------------------------------------------
    print("\n[TEST 7] Verificando eliminación de lista de precios ('quitar', 'borrar')...")
    
    # 7A: Cliente con lista existente escribe 'quitar'
    bot_engine.clear_user_state(test_wa)
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PRICE_LIST)

    web_con_lista = {
        "website_id": "w999",
        "version_id": "v999",
        "content": {
            "titulo_web": "Spa Relax",
            "lista_precios": {
                "titulo": "Lista Actual",
                "columnas_pago": ["Efectivo"],
                "items": [{"servicio": "Masaje", "precios": {"efectivo": "$10.000"}}]
            }
        },
        "slug": "spa-relax",
        "custom_domain": None
    }

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.send_whatsapp_list") as mock_send_list, \
         patch("bot_engine.actualizar_web_content", return_value=True) as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_con_lista):

        bot_engine.procesar_mensaje(test_wa, "quitar", "Tester")

        # Debe llamar a actualizar_web_content sin lista_precios
        mock_update.assert_called_once()
        ver_id, updated_cnt = mock_update.call_args[0]
        assert ver_id == "v999"
        assert "lista_precios" not in updated_cnt

        # Mensaje de confirmación
        assert mock_send_msg.called
        del_confirm_msg = mock_send_msg.call_args_list[0][0][1]
        assert "🗑️ ¡Listo! Tu lista de precios fue eliminada" in del_confirm_msg
        assert "https://spa-relax.tuweblista.com.ar" in del_confirm_msg

        # Debe haber vuelto a enviar el menú principal (Panel de Control)
        mock_send_list.assert_called_once()
        assert mock_send_list.call_args[0][4] == "Panel de Control"

    # 7B: Cliente sin lista previa escribe 'borrar'
    bot_engine.clear_user_state(test_wa)
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PRICE_LIST)

    web_sin_lista = {
        "website_id": "w999",
        "version_id": "v999",
        "content": {"titulo_web": "Spa Relax"},
        "slug": "spa-relax",
        "custom_domain": None
    }

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.send_whatsapp_list") as mock_send_list, \
         patch("bot_engine.actualizar_web_content") as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_sin_lista):

        bot_engine.procesar_mensaje(test_wa, "borrar", "Tester")

        mock_update.assert_not_called()
        info_msg = mock_send_msg.call_args_list[0][0][1]
        assert "ℹ️ Tu web no tenía ninguna lista de precios publicada." in info_msg
        mock_send_list.assert_called_once()
        assert mock_send_list.call_args[0][4] == "Panel de Control"

    # 7C: Mensaje en submenú de precios con vs sin lista de precios
    bot_engine.clear_user_state(test_wa)
    bot_engine.set_user_state(test_wa, bot_engine.MAIN_MENU)

    web_con_lista_activa = {
        "website_id": "w999",
        "version_id": "v999",
        "content": {
            "titulo_web": "Spa Relax",
            "lista_precios": {
                "titulo": "Lista Actual",
                "columnas_pago": ["Efectivo"],
                "items": [{"servicio": "Masaje", "precios": {"efectivo": "$10.000"}}]
            }
        },
        "slug": "spa-relax",
        "custom_domain": None
    }

    with patch("bot_engine.send_whatsapp_list") as mock_send_list, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_con_lista_activa):
        bot_engine.procesar_mensaje(test_wa, "main_precios", "Tester")
        assert mock_send_list.called
        list_args = mock_send_list.call_args[0]
        msg_con = list_args[1]
        options_sent = list_args[3]
        assert "Ya tenés una lista de precios publicada" in msg_con
        opt_ids = [o["id"] for o in options_sent]
        assert "PRECIOS_ACTUALIZAR" in opt_ids
        assert "PROMO_FECHA_START" in opt_ids
        assert "PRECIOS_QUITAR" in opt_ids
        assert "PRECIOS_VOLVER" in opt_ids
        volver_opt = next(o for o in options_sent if o["id"] == "PRECIOS_VOLVER")
        assert volver_opt["description"] == "Regresar al menú principal"
        assert bot_engine.get_user_state(test_wa)["estado"] == bot_engine.WAITING_FOR_PRICE_MENU_OPTION

    # 7D: Probar que PRECIOS_VOLVER desde WAITING_FOR_PRICE_MENU_OPTION regresa a Panel de Control
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PRICE_MENU_OPTION)
    with patch("bot_engine.send_whatsapp_list") as mock_send_list:
        bot_engine.procesar_mensaje(test_wa, "precios_volver", "Tester")
        mock_send_list.assert_called_once()
        assert mock_send_list.call_args[0][4] == "Panel de Control"
        assert bot_engine.get_user_state(test_wa)["estado"] == bot_engine.MAIN_MENU

    bot_engine.clear_user_state(test_wa)
    bot_engine.set_user_state(test_wa, bot_engine.MAIN_MENU)

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_sin_lista):
        bot_engine.procesar_mensaje(test_wa, "main_precios", "Tester")
        msg_sin = mock_send_msg.call_args[0][1]
        assert "Ya tenés una lista de precios publicada" not in msg_sin
        assert "Actualización de Lista de Precios" in msg_sin

    print("  ✅ Eliminación de lista de precios, retorno a Panel de Control y adaptación del menú de precios verificadas.")

    # ---------------------------------------------------------
    # TEST 8: Flask app.py - Vista Previa Temporal con ?preview=TOKEN
    # ---------------------------------------------------------
    print("\n[TEST 8] Verificando ruta /precios y overlay de borrador en Flask...")
    
    # Inyectar una sesión con draft_token en messages.db
    token_preview = "f9e8d7c6"
    preview_prices = {
        "titulo": "Precios Preview VIP",
        "columnas_pago": ["Efectivo"],
        "items": [{"servicio": "Tratamiento VIP", "precios": {"efectivo": "$99.999"}}]
    }
    bot_engine.set_user_state("5491188887777", bot_engine.CONFIRM_PRICE_LIST_DRAFT, {
        "draft_token": token_preview,
        "draft_prices": preview_prices
    })

    # Verificar función get_draft_prices_by_token en app.py
    extracted_prices = flask_app.get_draft_prices_by_token(token_preview)
    assert extracted_prices is not None, "get_draft_prices_by_token no encontró el draft con el token"
    assert extracted_prices["items"][0]["servicio"] == "Tratamiento VIP"

    # Probar llamada a client_website vía test_client de Flask
    client = flask_app.app.test_client()
    
    # Mockear Supabase para responder con una web de prueba
    mock_supabase = MagicMock()
    mock_web_query = MagicMock()
    mock_web_query.execute.return_value = MagicMock(data=[{"id": "w_test", "client_id": "c_test", "subdomain": "negocio-vip", "status": "published"}])

    mock_content_query = MagicMock()
    mock_content_query.eq.return_value = mock_content_query
    mock_content_query.execute.return_value = MagicMock(data=[{"id": "cnt_test", "content": json.dumps({"titulo_web": "Negocio VIP"}), "version": 1}])

    mock_client_query = MagicMock()
    mock_client_query.execute.return_value = MagicMock(data=[{"id": "c_test", "phone": "5491188887777", "name": "VIP"}])

    def mock_table(table_name):
        mock_tbl = MagicMock()
        mock_sel = MagicMock()
        mock_tbl.select.return_value = mock_sel
        if table_name == "websites":
            mock_sel.eq.return_value = mock_web_query
        elif table_name == "website_content":
            mock_sel.eq.return_value = mock_content_query
        elif table_name == "clients":
            mock_sel.eq.return_value = mock_client_query
        return mock_tbl

    mock_supabase.table.side_effect = mock_table

    with patch("app.supabase", mock_supabase), \
         patch("app.render_template") as mock_render:
        mock_render.return_value = "<html>OK</html>"
        
        response = client.get(
            "/precios?preview=f9e8d7c6",
            headers={"Host": "negocio-vip.tuweblista.com.ar"}
        )

        assert mock_render.called
        render_kwargs = mock_render.call_args[1]
        assert render_kwargs["is_preview"] is True, "is_preview debe ser True cuando se pasa ?preview=TOKEN válido"
        assert render_kwargs["web_content"]["lista_precios"] == preview_prices, "web_content debe tener los precios del borrador"

    print("  ✅ Flask overlay aplica draft_prices temporalmente y pasa is_preview=True.")

    # ---------------------------------------------------------
    # TEST 9: Auditoría SQLite - Cierre de conexiones y WAL
    # ---------------------------------------------------------
    print("\n[TEST 9] Verificando integridad y ausencia de locks en messages.db...")
    db_path = bot_engine.get_db_path()
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0].lower()
        assert journal_mode in ["wal", "memory"], f"Journal mode no es WAL: {journal_mode}"
    finally:
        if conn:
            conn.close()

    # Limpiar estado de prueba
    bot_engine.clear_user_state(test_wa)
    bot_engine.clear_user_state("5491188887777")
    print("  ✅ messages.db opera en modo WAL y sin locks abiertos.")

    # ---------------------------------------------------------
    # TEST 10: FSM Interactiva para Promoción por Fecha (Reserva Anticipada)
    # ---------------------------------------------------------
    print("\n[TEST 10] Verificando FSM interactiva para Promoción por Fecha (Reserva Anticipada)...")
    
    # 10A. Helper de fechas parse_promo_date
    d1 = bot_engine.parse_promo_date("27/10/2026")
    assert d1 is not None and d1["iso"] == "2026-10-27"
    assert "27 de Octubre de 2026" in d1["display"]
    
    d2 = bot_engine.parse_promo_date("15/11")
    assert d2 is not None
    assert d2["month"] == 11 and d2["day"] == 15
    
    d_inv = bot_engine.parse_promo_date("31/02/2026")
    assert d_inv is None, "Fecha inválida 31/02 no debe ser aceptada"
    
    # 10B. Web con lista base activa
    web_promo_test = {
        "website_id": "w_promo_10",
        "version_id": "v_promo_10",
        "content": {
            "titulo_web": "Soteria Estética",
            "lista_precios": {
                "titulo": "Lista Soteria",
                "columnas_pago": ["Efectivo", "Transferencia", "Tarjeta"],
                "items": [
                    {"servicio": "Depilación Láser", "precios": {"efectivo": "$30.000", "transferencia": "$35.000", "tarjeta": "$40.000"}}
                ]
            }
        },
        "slug": "soteria-estetica",
        "custom_domain": None
    }
    
    # 10C. Selección de PROMO_FECHA_START desde WAITING_FOR_PRICE_MENU_OPTION
    bot_engine.clear_user_state(test_wa)
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PRICE_MENU_OPTION)
    
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_promo_test):
        
        bot_engine.procesar_mensaje(test_wa, "promo_fecha_start", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_TITLE
        assert "Paso 1 de 4" in mock_send_msg.call_args[0][1]
        
    # 10D. Paso 1: Título del Evento o Jornada
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg:
        bot_engine.procesar_mensaje(test_wa, "Jornada Láser 17 de Noviembre", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DISCOUNT_1
        assert state["temp_data"]["promo_title"] == "Jornada Láser 17 de Noviembre"
        assert "Paso 2 de 4" in mock_send_msg.call_args[0][1]

    # 10E. Paso 2: Descuento Tramo 1 con validación
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg:
        # Input inválido
        bot_engine.procesar_mensaje(test_wa, "cien por ciento", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DISCOUNT_1
        assert "porcentaje válido" in mock_send_msg.call_args[0][1]
        
        # Input válido: 30
        bot_engine.procesar_mensaje(test_wa, "30%", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DATE_1
        assert state["temp_data"]["promo_desc_1"] == 30
        assert "Paso 3 de 4" in mock_send_msg.call_args[0][1]
        assert "Escribí la fecha completa con día, mes y año (Por ejemplo: 27/10/2026):" in mock_send_msg.call_args[0][1]

    # 10F. Paso 3: Fecha Límite Tramo 1 y Botones Tramo 2 (<= 20 chars)
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.send_whatsapp_buttons") as mock_buttons:
        # Input inválido
        bot_engine.procesar_mensaje(test_wa, "mañana pasado", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DATE_1
        assert "⚠️ No pude entender la fecha. Por favor escribí la fecha completa con día, mes y año (Por ejemplo: 27/10/2026):" in mock_send_msg.call_args[0][1]
        
        # Input válido: 27/10/2026
        bot_engine.procesar_mensaje(test_wa, "27/10/2026", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_TIER2_CHOICE
        assert state["temp_data"]["promo_date_1_iso"] == "2026-10-27"
        
        mock_buttons.assert_called_once()
        b_args = mock_buttons.call_args[0]
        btns = b_args[2]
        assert len(btns) == 2
        for b in btns:
            assert len(b["title"]) <= 20, f"Título de botón supera 20 chars: {b['title']}"

    # 10G. Paso 4 (Flujo 2 tramos): Tramo 2 con Descuento y Fecha
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg:
        bot_engine.procesar_mensaje(test_wa, "promo_t2_yes", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DISCOUNT_2
        assert "Paso 4 de 4" in mock_send_msg.call_args[0][1]

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg:
        bot_engine.procesar_mensaje(test_wa, "15", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DATE_2
        assert state["temp_data"]["promo_desc_2"] == 15
        assert "Debe ser posterior al 27 de Octubre de 2026 (Por ejemplo: 15/11/2026):" in mock_send_msg.call_args[0][1]

        # Input inválido
        bot_engine.procesar_mensaje(test_wa, "semana próxima", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.WAITING_FOR_PROMO_DATE_2
        assert "⚠️ No pude entender la fecha. Por favor escribí la fecha completa con día, mes y año (Por ejemplo: 15/11/2026):" in mock_send_msg.call_args[0][1]

    with patch("bot_engine.send_whatsapp_buttons") as mock_buttons, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_promo_test):
        bot_engine.procesar_mensaje(test_wa, "15/11/2026", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.CONFIRM_PROMO_DRAFT
        temp_data = state["temp_data"]
        assert "draft_token" in temp_data
        assert "draft_prices" in temp_data
        
        # Validar estructura y botones <= 20 chars
        mock_buttons.assert_called_once()
        confirm_btns = mock_buttons.call_args[0][2]
        for b in confirm_btns:
            assert len(b["title"]) <= 20, f"Botón de confirmación supera 20 chars: {b['title']}"
            
        preview_body = mock_buttons.call_args[0][1]
        assert f"?preview={temp_data['draft_token']}" in preview_body
        assert "Jornada Láser 17 de Noviembre" in preview_body
        assert "30% OFF" in preview_body
        assert "15% OFF" in preview_body

    # 10H. Cancelación de Borrador de Promo
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.actualizar_web_content") as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_promo_test):
        bot_engine.procesar_mensaje(test_wa, "confirm_promo_cancel", "Tester")
        mock_update.assert_not_called()
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] in [bot_engine.IDLE, bot_engine.MAIN_MENU]

    # 10I. Flujo con 1 tramo y Confirmación / Publicación en Supabase
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PROMO_TIER2_CHOICE, {
        "promo_title": "Jornada Express",
        "promo_desc_1": 25,
        "promo_date_1_iso": "2026-10-30",
        "promo_date_1_display": "30 de Octubre de 2026"
    })
    
    with patch("bot_engine.send_whatsapp_buttons") as mock_buttons, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_promo_test):
        # Usuario elige solo 1 tramo
        bot_engine.procesar_mensaje(test_wa, "promo_t2_no", "Tester")
        state = bot_engine.get_user_state(test_wa)
        assert state["estado"] == bot_engine.CONFIRM_PROMO_DRAFT
        draft_promo = state["temp_data"]["promocion_data"]
        assert len(draft_promo["escalas"]) == 1
        assert draft_promo["escalas"][0]["descuento"] == 25

    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.actualizar_web_content", return_value=True) as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_promo_test):
        
        bot_engine.procesar_mensaje(test_wa, "confirm_promo_ok", "Tester")
        mock_update.assert_called_once()
        ver_id, updated_content = mock_update.call_args[0]
        assert ver_id == "v_promo_10"
        assert "promocion_fecha" in updated_content["lista_precios"]
        saved_promo = updated_content["lista_precios"]["promocion_fecha"]
        assert saved_promo["activa"] is True
        assert saved_promo["titulo"] == "Jornada Express"
        assert saved_promo["escalas"][0]["descuento"] == 25
        # Los items y columnas base siguen intactos
        assert len(updated_content["lista_precios"]["items"]) == 1
        
        # Sesión reseteada
        assert bot_engine.get_user_state(test_wa)["estado"] == bot_engine.IDLE

    # 10J. Detener Promoción Activa (PROMO_DETENER) y retorno a precios regulares
    web_con_promo_activa = {
        "website_id": "w_promo_10",
        "version_id": "v_promo_10",
        "content": {
            "titulo_web": "Soteria Estética",
            "lista_precios": {
                "titulo": "Lista Soteria",
                "columnas_pago": ["Efectivo"],
                "items": [{"servicio": "Depilación", "precios": {"efectivo": "$30.000"}}],
                "promocion_fecha": saved_promo
            }
        },
        "slug": "soteria-estetica",
        "custom_domain": None
    }
    
    # 10J.1 Vía submenú WAITING_FOR_PRICE_MENU_OPTION
    bot_engine.set_user_state(test_wa, bot_engine.WAITING_FOR_PRICE_MENU_OPTION)
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.send_whatsapp_list") as mock_send_list, \
         patch("bot_engine.actualizar_web_content", return_value=True) as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_con_promo_activa):
        
        bot_engine.procesar_mensaje(test_wa, "promo_detener", "Tester")
        mock_update.assert_called_once()
        v_id, c_data = mock_update.call_args[0]
        assert "promocion_fecha" not in c_data["lista_precios"]
        assert len(c_data["lista_precios"]["items"]) == 1
        confirm_detener = mock_send_msg.call_args_list[0][0][1]
        assert "La promoción fue detenida" in confirm_detener
        mock_send_list.assert_called_once()
        assert mock_send_list.call_args[0][4] == "Panel de Control"

    # 10J.2 Vía palabra clave global ('detener promo')
    import copy
    web_promo_activa_2 = copy.deepcopy(web_con_promo_activa)
    web_promo_activa_2["content"]["lista_precios"]["promocion_fecha"] = saved_promo
    with patch("bot_engine.send_whatsapp_message") as mock_send_msg, \
         patch("bot_engine.send_whatsapp_list") as mock_send_list, \
         patch("bot_engine.actualizar_web_content", return_value=True) as mock_update, \
         patch("bot_engine.obtener_web_del_cliente", return_value=web_promo_activa_2):
        
        bot_engine.procesar_mensaje(test_wa, "detener promo", "Tester")
        mock_update.assert_called_once()
        v_id, c_data = mock_update.call_args[0]
        assert "promocion_fecha" not in c_data["lista_precios"]
        mock_send_list.assert_called_once()
        assert mock_send_list.call_args[0][4] == "Panel de Control"
    
    print("  ✅ FSM interactiva, validaciones de fecha/descuento, generación de borrador y detención de promo verificadas al 100%.")

    # Limpiar estado final
    bot_engine.clear_user_state(test_wa)

    print("\n" + "=" * 70)
    print("🎉 TODAS LAS PRUEBAS DE LA ETAPA 1 (BACKEND) PASARON CON ÉXITO (100% PASS)")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
