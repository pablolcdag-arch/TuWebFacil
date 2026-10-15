import os
import sys
import json
import sqlite3
import subprocess

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import bot_engine

TEST_PHONE_1 = "5491100000001"
TEST_PHONE_2 = "5491100000002"
TEST_PHONE_3 = "5491100000003"


def cleanup():
    """Limpia los números de prueba de user_sessions."""
    db_path = bot_engine.get_db_path()
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM user_sessions WHERE phone IN (?, ?, ?)",
                  (TEST_PHONE_1, TEST_PHONE_2, TEST_PHONE_3))
        conn.commit()
    bot_engine.user_states.pop(TEST_PHONE_1, None)
    bot_engine.user_states.pop(TEST_PHONE_2, None)
    bot_engine.user_states.pop(TEST_PHONE_3, None)


def test_schema():
    print("\n--- TEST 1: Verificando esquema de user_sessions en messages.db ---")
    bot_engine.init_sessions_db()
    db_path = bot_engine.get_db_path()
    
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        columns = c.execute("PRAGMA table_info(user_sessions)").fetchall()
        col_names = {col[1]: col[2] for col in columns}
        
    print(f"Columnas encontradas: {col_names}")
    assert "phone" in col_names, "Falta columna phone"
    assert "estado" in col_names, "Falta columna estado"
    assert "temp_data" in col_names, "Falta columna temp_data"
    assert "updated_at" in col_names, "Falta columna updated_at"
    print("✅ Esquema verificado correctamente.")


def test_helpers_and_persistence():
    print("\n--- TEST 2: Verificando helpers get_user_state, set_user_state, clear_user_state ---")
    
    # 1. Estado inicial default para usuario nuevo
    state = bot_engine.get_user_state(TEST_PHONE_1)
    assert state["estado"] == bot_engine.IDLE, f"Esperaba IDLE, obtuve {state['estado']}"
    assert state["temp_data"] == {}, f"Esperaba {{}}, obtuve {state['temp_data']}"
    print("✅ get_user_state devuelve IDLE por defecto.")
    
    # 2. Guardar estado con temp_data
    bot_engine.set_user_state(TEST_PHONE_1, bot_engine.WAITING_FOR_TITLE, {"test_key": "test_val"})
    assert bot_engine.user_states[TEST_PHONE_1]["estado"] == bot_engine.WAITING_FOR_TITLE
    
    # 3. Simular caída de memoria borrando la caché RAM
    bot_engine.user_states.clear()
    assert TEST_PHONE_1 not in bot_engine.user_states
    
    # 4. Leer de nuevo: debe rescatar de SQLite y repoblar la caché
    reloaded = bot_engine.get_user_state(TEST_PHONE_1)
    assert reloaded["estado"] == bot_engine.WAITING_FOR_TITLE, f"Esperaba WAITING_FOR_TITLE, obtuve {reloaded['estado']}"
    assert reloaded["temp_data"] == {"test_key": "test_val"}, f"Esperaba temp_data guardado, obtuve {reloaded['temp_data']}"
    assert TEST_PHONE_1 in bot_engine.user_states, "La caché no se repobló tras lectura de SQLite"
    print("✅ set_user_state persiste en SQLite y get_user_state recupera tras pérdida de RAM.")
    
    # 5. Modificar estado preservando temp_data (temp_data=None)
    bot_engine.set_user_state(TEST_PHONE_1, bot_engine.WAITING_FOR_SUBTITLE)
    bot_engine.user_states.clear()
    preserved = bot_engine.get_user_state(TEST_PHONE_1)
    assert preserved["estado"] == bot_engine.WAITING_FOR_SUBTITLE
    assert preserved["temp_data"] == {"test_key": "test_val"}
    print("✅ set_user_state preserva temp_data existente cuando temp_data es None.")
    
    # 6. Limpiar estado con clear_user_state
    bot_engine.clear_user_state(TEST_PHONE_1)
    db_path = bot_engine.get_db_path()
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        row = c.execute("SELECT * FROM user_sessions WHERE phone = ?", (TEST_PHONE_1,)).fetchone()
        assert row is None, "clear_user_state no eliminó la fila de SQLite"
    
    state_after_clear = bot_engine.get_user_state(TEST_PHONE_1)
    assert state_after_clear["estado"] == bot_engine.IDLE
    print("✅ clear_user_state elimina correctamente de SQLite y resetea memoria.")


def test_simulation_restarts():
    print("\n--- TEST 3: Simulación de reinicio de proceso para WAITING_FOR_TITLE y WAITING_FOR_DOMAIN_NAME ---")
    
    # Caso A: Usuario 2 entra en WAITING_FOR_TITLE
    print("-> Proceso 1: Usuario entra a WAITING_FOR_TITLE")
    bot_engine.set_user_state(TEST_PHONE_2, bot_engine.WAITING_FOR_TITLE)
    
    # Simulamos el reinicio absoluto ejecutando un subproceso de Python fresco
    code_check_title = f"""
import sys, os
sys.path.insert(0, '{BASE_DIR}')
import bot_engine

# Simular que recibimos el mensaje con el nuevo título
state = bot_engine.get_user_state('{TEST_PHONE_2}')
assert state['estado'] == bot_engine.WAITING_FOR_TITLE, f"Estado incorrecto tras reinicio: {{state['estado']}}"
print("SUBPROCESO: Estado recuperado con éxito:", state['estado'])
"""
    res = subprocess.run([sys.executable, "-c", code_check_title], capture_output=True, text=True)
    print("Salida del subproceso (TITLE):", res.stdout.strip())
    assert res.returncode == 0, f"Fallo en subproceso de TITLE: {res.stderr}"
    print("✅ WAITING_FOR_TITLE sobrevive al reinicio completo del proceso.")

    # Caso B: Usuario 3 entra en WAITING_FOR_DOMAIN_NAME
    print("-> Proceso 1: Usuario entra a WAITING_FOR_DOMAIN_NAME")
    bot_engine.set_user_state(TEST_PHONE_3, bot_engine.WAITING_FOR_DOMAIN_NAME)
    
    code_check_domain = f"""
import sys, os
sys.path.insert(0, '{BASE_DIR}')
import bot_engine

state = bot_engine.get_user_state('{TEST_PHONE_3}')
assert state['estado'] == bot_engine.WAITING_FOR_DOMAIN_NAME, f"Estado incorrecto tras reinicio: {{state['estado']}}"
print("SUBPROCESO: Estado recuperado con éxito:", state['estado'])
"""
    res = subprocess.run([sys.executable, "-c", code_check_domain], capture_output=True, text=True)
    print("Salida del subproceso (DOMAIN):", res.stdout.strip())
    assert res.returncode == 0, f"Fallo en subproceso de DOMAIN: {res.stderr}"
    print("✅ WAITING_FOR_DOMAIN_NAME sobrevive al reinicio completo del proceso.")


def test_escape_words():
    print("\n--- TEST 4: Verificando palabras de escape en procesar_mensaje ---")
    # Ponemos al usuario 2 en WAITING_FOR_TITLE
    bot_engine.set_user_state(TEST_PHONE_2, bot_engine.WAITING_FOR_TITLE, {"dummy": 123})
    
    # Mockeamos send_whatsapp_list y send_whatsapp_message para evitar llamadas a Meta
    sent_msgs = []
    bot_engine.send_whatsapp_message = lambda wa_id, msg: sent_msgs.append(("msg", wa_id, msg))
    bot_engine.send_whatsapp_list = lambda wa_id, msg, btn, opts, title: sent_msgs.append(("list", wa_id, opts))
    bot_engine.send_whatsapp_buttons = lambda wa_id, msg, btns: sent_msgs.append(("buttons", wa_id, btns))
    
    # Enviamos "menu"
    bot_engine.procesar_mensaje(TEST_PHONE_2, "cancelar", "Test User")
    
    # El usuario debe haber sido reseteado al MAIN_MENU
    curr_state = bot_engine.get_user_state(TEST_PHONE_2)
    assert curr_state["estado"] == bot_engine.MAIN_MENU, f"Esperaba MAIN_MENU tras cancelar, obtuve {curr_state['estado']}"
    assert curr_state["temp_data"] == {}, f"Esperaba temp_data vacio, obtuve {curr_state['temp_data']}"
    print("✅ Las palabras de escape resetean la sesión correctamente a MAIN_MENU.")


def test_multiturn_flow_with_restarts():
    print("\n--- TEST 5: Flujo multi-paso de edición de servicio con reinicios entre cada paso ---")
    
    # Paso 1: Usuario elige Servicio 2 (índice 1)
    bot_engine.set_user_state(TEST_PHONE_1, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": 1})
    
    # Paso 2: El proceso se cae/reinicia. Se ejecuta un nuevo subproceso que procesa el título
    code_step2 = f"""
import sys, os
sys.path.insert(0, '{BASE_DIR}')
import bot_engine

# Mock de WhatsApp para no enviar llamadas reales
bot_engine.send_whatsapp_message = lambda wa_id, msg: None

# El usuario manda el título en este proceso fresco
bot_engine.procesar_mensaje('{TEST_PHONE_1}', 'Plomería Integral 24hs', 'Test User')

state = bot_engine.get_user_state('{TEST_PHONE_1}')
assert state['estado'] == 'WAITING_FOR_SERVICE_DESC', f"Esperaba WAITING_FOR_SERVICE_DESC, obtuve {{state['estado']}}"
assert state['temp_data'].get('servicio_idx') == 1, f"Se perdió servicio_idx: {{state['temp_data']}}"
assert state['temp_data'].get('nuevo_titulo_srv') == 'Plomería Integral 24hs', f"Se perdió nuevo_titulo_srv: {{state['temp_data']}}"
print("SUBPROCESO PASO 2: Título guardado en sesión persistente.")
"""
    res2 = subprocess.run([sys.executable, "-c", code_step2], capture_output=True, text=True)
    print(res2.stdout.strip())
    assert res2.returncode == 0, f"Error en paso 2: {res2.stderr}"

    # Paso 3: El proceso se vuelve a caer/reiniciar. Se ejecuta un nuevo subproceso que procesa la descripción
    code_step3 = f"""
import sys, os
sys.path.insert(0, '{BASE_DIR}')
import bot_engine

# Mock de WhatsApp y Supabase
bot_engine.send_whatsapp_message = lambda wa_id, msg: None
bot_engine.send_whatsapp_list = lambda *args, **kwargs: None
bot_engine.obtener_web_del_cliente = lambda phone: {{
    'version_id': 'fake-version-123',
    'slug': 'test-demo',
    'content': {{'servicios_sugeridos': ['S1', 'S2', 'S3'], 'descripciones_servicios': ['D1', 'D2', 'D3']}}
}}
updated_content = {{}}
bot_engine.actualizar_web_content = lambda ver_id, content: updated_content.update(content) or True

# El usuario manda la descripción en este segundo proceso fresco
bot_engine.procesar_mensaje('{TEST_PHONE_1}', 'Destapaciones y arreglos de cañerías urgentes', 'Test User')

assert updated_content['servicios_sugeridos'][1] == 'Plomería Integral 24hs', f"Título no actualizado en servicio 1: {{updated_content}}"
assert updated_content['descripciones_servicios'][1] == 'Destapaciones y arreglos de cañerías urgentes', f"Descripción no actualizada: {{updated_content}}"
print("SUBPROCESO PASO 3: Web actualizada exitosamente con los datos preservados a través de múltiples reinicios.")
"""
    res3 = subprocess.run([sys.executable, "-c", code_step3], capture_output=True, text=True)
    print(res3.stdout.strip())
    assert res3.returncode == 0, f"Error en paso 3: {res3.stderr}"
    print("✅ Flujo multi-paso con reinicios completado satisfactoriamente.")


if __name__ == "__main__":
    try:
        cleanup()
        test_schema()
        test_helpers_and_persistence()
        test_simulation_restarts()
        test_escape_words()
        test_multiturn_flow_with_restarts()
        print("\n==============================================")
        print("🎉 TODOS LOS TESTS LOCALES PASARON CON ÉXITO")
        print("==============================================")
    finally:
        cleanup()
