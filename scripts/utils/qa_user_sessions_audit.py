import os
import sys
import json
import sqlite3
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import bot_engine

PYTHON_BIN = sys.executable

def banner(title):
    print(f"\n{'='*70}\n🔍 QA AUDIT TEST: {title}\n{'='*70}")

def cleanup_test_phones(phones):
    db_path = bot_engine.get_db_path()
    try:
        with sqlite3.connect(db_path, timeout=5) as conn:
            c = conn.cursor()
            placeholders = ",".join("?" for _ in phones)
            c.execute(f"DELETE FROM user_sessions WHERE phone IN ({placeholders})", phones)
            conn.commit()
    except Exception as e:
        print(f"Error en cleanup_test_phones: {e}")
    for p in phones:
        bot_engine.user_states.pop(p, None)

def test_sql_injection():
    banner("1. Vulnerabilidad e Inyección SQL")
    malicious_phones = [
        "54911'; DROP TABLE user_sessions; --",
        "54911' OR '1'='1",
        "54911\" OR 1=1 --",
        "54911 UNION SELECT 1,2,3,4 --"
    ]
    malicious_states = [
        "WAITING_FOR_TITLE'; DROP TABLE user_sessions; --",
        "' OR '1'='1"
    ]
    malicious_data = {
        "key'; DROP TABLE user_sessions; --": "val'; DROP TABLE user_sessions; --",
        "payload": "'); DELETE FROM user_sessions; --"
    }

    try:
        for idx, phone in enumerate(malicious_phones):
            state = malicious_states[idx % len(malicious_states)]
            bot_engine.set_user_state(phone, state, malicious_data)
            retrieved = bot_engine.get_user_state(phone)
            assert retrieved["estado"] == state, f"Estado corrupto para {phone}"
            assert retrieved["temp_data"] == malicious_data, f"Temp data corrupto para {phone}"

        # Comprobar que user_sessions sigue viva y no fue destruida
        db_path = bot_engine.get_db_path()
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT count(*) FROM user_sessions")
            count = c.fetchone()[0]
            assert count >= len(malicious_phones), "Inyección SQL afectó las filas"

        # Probar clear_user_state con phone malicioso
        for phone in malicious_phones:
            bot_engine.clear_user_state(phone)
            res = bot_engine.get_user_state(phone)
            assert res["estado"] == bot_engine.IDLE

        # Comprobar que los estados estén declarados como constantes según AGENTS.md
        required_constants = [
            "IDLE", "MAIN_MENU", "EDIT_MENU", "EDIT_MENU_SERVICIOS",
            "WAITING_FOR_TITLE", "WAITING_FOR_SUBTITLE", "WAITING_FOR_SERVICE_TITLE",
            "WAITING_FOR_SERVICE_DESC", "WAITING_FOR_LOCATION", "WAITING_FOR_SCHEDULE",
            "WAITING_FOR_IMAGE_ROLE", "WAITING_FOR_RECEIPT", "WAITING_FOR_DOMAIN_NAME",
            "WAITING_FOR_ADMIN_MESSAGE", "WAITING_FOR_WHATSAPP", "WAITING_FOR_EMAIL",
            "WAITING_FOR_INSTAGRAM", "WAITING_FOR_TRANSFER_PHONE"
        ]
        missing_constants = [c for c in required_constants if not hasattr(bot_engine, c)]
        assert not missing_constants, f"Faltan constantes de estado en bot_engine: {missing_constants}"
        print("✅ PASADO: Todas las constantes de estado están formalmente declaradas en bot_engine.")

        print("✅ PASADO: Todas las queries SQL están correctamente parametrizadas. Inmune a SQL Injection.")
        return True, []
    except Exception as e:
        print(f"❌ FALLO en test_sql_injection: {e}")
        return False, [f"SQL Injection vulnerability: {e}"]
    finally:
        cleanup_test_phones(malicious_phones)

def test_connection_handling():
    banner("2. Inspección de Cierre de Conexiones SQLite")
    db_path = bot_engine.get_db_path()
    test_phone = "5491199990001"
    bugs = []

    # Verificar que bot_engine no use 'with sqlite3.connect' y que cierre explícitamente sus conexiones con try...finally: conn.close()
    import inspect
    session_funcs = [bot_engine.init_sessions_db, bot_engine.get_user_state, bot_engine.set_user_state, bot_engine.clear_user_state]
    unclosed_funcs = []
    for f in session_funcs:
        src = inspect.getsource(f)
        if "with sqlite3.connect" in src or "conn.close()" not in src:
            unclosed_funcs.append(f.__name__)

    if unclosed_funcs:
        msg = (f"ADVERTENCIA CRÍTICA: En Python, 'with sqlite3.connect(...) as conn:' solo administra "
               f"la transacción (commit/rollback), pero NO CIERRA la conexión (conn.close() nunca es llamado). "
               f"Las siguientes funciones no cierran explícitamente sus conexiones: {', '.join(unclosed_funcs)}.")
        print(f"⚠️  {msg}")
        bugs.append(msg)
    else:
        print("✅ Las conexiones en bot_engine se cierran explícitamente con try...finally: conn.close() sin usar 'with sqlite3.connect'.")

    # Verificar modo WAL
    with sqlite3.connect(db_path) as check_conn:
        mode = check_conn.execute("PRAGMA journal_mode;").fetchone()[0]
        if mode.lower() != "wal":
            bugs.append(f"Modo WAL no está activo en SQLite (actual: {mode})")
        else:
            print("✅ Modo WAL activo en SQLite (lecturas y escrituras simultáneas permitidas).")

    # Prueba de estrés con 500 operaciones rápidas para detectar si hay locking o leak de fds
    try:
        for i in range(500):
            bot_engine.set_user_state(test_phone, bot_engine.WAITING_FOR_TITLE, {"iter": i})
            st = bot_engine.get_user_state(test_phone)
            assert st["temp_data"]["iter"] == i
        bot_engine.clear_user_state(test_phone)
        print("✅ 500 operaciones secuenciales completadas sin error 'database is locked'.")
    except Exception as e:
        print(f"❌ FALLO durante operaciones repetidas de SQLite: {e}")
        bugs.append(f"Fallo de conexión bajo estrés: {e}")

    cleanup_test_phones([test_phone])
    return (len(bugs) == 0, bugs)

def test_graceful_degradation():
    banner("3. Resiliencia y Degradación Elegante ante Fallos de SQLite")
    test_phone = "5491188880001"
    bugs = []

    # Mock de sqlite3.connect para simular fallo absoluto de base de datos
    original_connect = sqlite3.connect

    def broken_connect(*args, **kwargs):
        raise sqlite3.OperationalError("Simulated DB Disk Failure / Locked")

    try:
        # 1. Fallo en get_user_state
        sqlite3.connect = broken_connect
        bot_engine.user_states.clear() # Limpiar RAM para forzar lectura a BD
        state = bot_engine.get_user_state(test_phone)
        assert state["estado"] == bot_engine.IDLE, "No devolvió IDLE ante fallo de BD"
        assert state["temp_data"] == {}, "No devolvió temp_data vacía ante fallo de BD"
        print("✅ get_user_state degrada elegantemente a IDLE si la BD no responde.")

        # 2. Fallo en set_user_state
        res = bot_engine.set_user_state(test_phone, bot_engine.WAITING_FOR_TITLE, {"offline": True})
        assert res["estado"] == bot_engine.WAITING_FOR_TITLE, "No actualizó memoria ante fallo de BD"
        assert bot_engine.user_states[test_phone]["temp_data"]["offline"] is True
        print("✅ set_user_state degrada elegantemente actualizando la memoria RAM si SQLite falla.")

        # 3. Fallo en clear_user_state
        bot_engine.clear_user_state(test_phone)
        assert bot_engine.user_states[test_phone]["estado"] == bot_engine.IDLE
        print("✅ clear_user_state degrada elegantemente reseteando memoria si SQLite falla.")

        # 4. Fallo con JSON corrupto en SQLite
        sqlite3.connect = original_connect # Restaurar conexión real
        db_path = bot_engine.get_db_path()
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO user_sessions (phone, estado, temp_data) VALUES (?, ?, ?)",
                      (test_phone, "WAITING_FOR_TITLE", "{JSON TOTALMENTE CORRUPTO Y ROTO"))
            conn.commit()

        bot_engine.user_states.clear()
        recovered = bot_engine.get_user_state(test_phone)
        assert recovered["estado"] == "WAITING_FOR_TITLE"
        assert recovered["temp_data"] == {}, f"Esperaba fallback a dict vacio ante JSON corrupto, obtuve {recovered['temp_data']}"
        print("✅ get_user_state tolera JSON corrupto en SQLite sin crashear.")

    except Exception as e:
        print(f"❌ FALLO en degradación elegante: {e}")
        bugs.append(f"Fallo en degradación elegante: {e}")
    finally:
        sqlite3.connect = original_connect
        cleanup_test_phones([test_phone])

    return (len(bugs) == 0, bugs)

def test_real_process_restart():
    banner("4. Persistencia Real con Reinicio Total de Proceso (WAITING_FOR_TITLE y WAITING_FOR_DOMAIN_NAME)")
    phone_title = "5491177770001"
    phone_domain = "5491177770002"
    phone_receipt = "5491177770003"
    bugs = []

    try:
        # Paso 1: Configurar estados en proceso actual
        bot_engine.set_user_state(phone_title, bot_engine.WAITING_FOR_TITLE, {"init": 1})
        bot_engine.set_user_state(phone_domain, bot_engine.WAITING_FOR_DOMAIN_NAME, {"init": 2})
        bot_engine.set_user_state(phone_receipt, bot_engine.WAITING_FOR_RECEIPT, {"dominio": "panaderiatest.com.ar"})

        # Paso 2: Crear un subproceso de Python fresco que simula que el servidor se reinició por completo
        subproc_code = f"""
import sys, os
sys.path.insert(0, '{BASE_DIR}')
import bot_engine

# Verificar que user_states está vacío inicialmente en este proceso nuevo
assert len(bot_engine.user_states) == 0, "user_states no estaba limpio en el nuevo proceso"

# Mock de WhatsApp y Supabase para probar recepción de mensajes
bot_engine.send_whatsapp_message = lambda *args, **kwargs: None
bot_engine.send_whatsapp_list = lambda *args, **kwargs: None
bot_engine.send_whatsapp_buttons = lambda *args, **kwargs: None

# 1. Verificar WAITING_FOR_TITLE
s1 = bot_engine.get_user_state('{phone_title}')
assert s1['estado'] == bot_engine.WAITING_FOR_TITLE, f"Estado incorrecto s1: {{s1}}"
assert s1['temp_data']['init'] == 1, f"temp_data perdido s1: {{s1}}"

# Simular que el usuario envía su nuevo título
bot_engine.obtener_web_del_cliente = lambda p: {{'version_id': 'v1', 'slug': 'demo', 'content': {{}}}}
bot_engine.actualizar_web_content = lambda vid, cnt: True

bot_engine.procesar_mensaje('{phone_title}', 'Estudio Jurídico Pérez & Asoc.', 'Carlos')
s1_post = bot_engine.get_user_state('{phone_title}')
# Tras editar título, la FSM lo redirige al menú de edición (EDIT_MENU) mediante llamada interna a procesar_mensaje('2')
assert s1_post['estado'] == bot_engine.EDIT_MENU, f"Estado post-titulo deberia ser EDIT_MENU, obtuve: {{s1_post}}"

# 2. Verificar WAITING_FOR_DOMAIN_NAME
s2 = bot_engine.get_user_state('{phone_domain}')
assert s2['estado'] == bot_engine.WAITING_FOR_DOMAIN_NAME, f"Estado incorrecto s2: {{s2}}"

# 3. Verificar WAITING_FOR_RECEIPT y preservación de temp_data (dominio)
s3 = bot_engine.get_user_state('{phone_receipt}')
assert s3['estado'] == bot_engine.WAITING_FOR_RECEIPT, f"Estado incorrecto s3: {{s3}}"
assert s3['temp_data'].get('dominio') == 'panaderiatest.com.ar', f"Dominio perdido en temp_data: {{s3}}"

print("SUBPROCESO_EXITOSO")
"""
        res = subprocess.run([PYTHON_BIN, "-c", subproc_code], capture_output=True, text=True)
        if res.returncode != 0 or "SUBPROCESO_EXITOSO" not in res.stdout:
            print("STDERR subproceso:", res.stderr)
            bugs.append(f"Fallo en subproceso de reinicio: {res.stderr}")
        else:
            print("✅ Subproceso recuperó estados y temp_data correctamente desde SQLite.")
            print("✅ El flujo de mensajes funcionó correctamente en proceso fresco tras reinicio.")

    except Exception as e:
        print(f"❌ FALLO en test_real_process_restart: {e}")
        bugs.append(f"Error en reinicio de proceso: {e}")
    finally:
        cleanup_test_phones([phone_title, phone_domain, phone_receipt])

    return (len(bugs) == 0, bugs)

def test_escape_words():
    banner("5. Prueba Exhaustiva de Palabras de Escape")
    test_phone = "5491166660001"
    escape_words = ["menu", "menú", "volver", "inicio", "cancelar", " MENU ", "  volver\n", "CANCELAR"]
    bugs = []

    try:
        # Mock de envíos
        bot_engine.send_whatsapp_message = lambda *args, **kwargs: None
        bot_engine.send_whatsapp_list = lambda *args, **kwargs: None
        bot_engine.send_whatsapp_buttons = lambda *args, **kwargs: None

        for word in escape_words:
            # Ponemos al usuario en un estado previo con temp_data residual
            bot_engine.set_user_state(test_phone, "WAITING_FOR_SERVICE_DESC", {
                "servicio_idx": 2,
                "nuevo_titulo_srv": "Algo"
            })
            
            # El usuario escribe la palabra de escape
            bot_engine.procesar_mensaje(test_phone, word, "Usuario Test")

            # 1. Comprobar en memoria
            state_mem = bot_engine.user_states.get(test_phone, {})
            if state_mem.get("estado") != bot_engine.MAIN_MENU:
                bugs.append(f"Palabra '{word}' no dejó estado en MAIN_MENU en memoria: {state_mem}")
            if state_mem.get("temp_data") != {}:
                bugs.append(f"Palabra '{word}' no reseteó temp_data en memoria: {state_mem}")

            # 2. Comprobar en SQLite
            db_path = bot_engine.get_db_path()
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                row = c.execute("SELECT estado, temp_data FROM user_sessions WHERE phone = ?", (test_phone,)).fetchone()
                if not row:
                    bugs.append(f"Palabra '{word}' no dejó registro en SQLite")
                else:
                    db_st, db_temp = row
                    if db_st != bot_engine.MAIN_MENU:
                        bugs.append(f"Palabra '{word}' dejó estado {db_st} en SQLite, esperaba MAIN_MENU")
                    parsed_temp = json.loads(db_temp) if db_temp else {}
                    if parsed_temp != {}:
                        bugs.append(f"Palabra '{word}' dejó temp_data residual en SQLite: {parsed_temp}")

        if not bugs:
            print("✅ Todas las palabras de escape ('menu', 'menú', 'volver', 'inicio', 'cancelar' con mayúsculas y espacios) resetean la sesión a MAIN_MENU con temp_data vacía tanto en RAM como en SQLite.")
        else:
            for b in bugs:
                print(f"❌ {b}")

    except Exception as e:
        bugs.append(f"Excepción en test_escape_words: {e}")
    finally:
        cleanup_test_phones([test_phone])

    return (len(bugs) == 0, bugs)

def test_concurrency_and_isolation():
    banner("6. Prueba de Concurrencia y Aislamiento entre Múltiples Usuarios")
    NUM_USERS = 12
    phones = [f"549115555{i:04d}" for i in range(NUM_USERS)]
    bugs = []

    # Mock WhatsApp
    bot_engine.send_whatsapp_message = lambda *args, **kwargs: None
    bot_engine.send_whatsapp_list = lambda *args, **kwargs: None
    bot_engine.send_whatsapp_buttons = lambda *args, **kwargs: None

    def worker_task(idx, phone):
        try:
            # Cada usuario realiza operaciones en paralelo
            # Usuario par edita servicio 0, usuario impar edita servicio 1
            srv_idx = idx % 3
            titulo = f"Servicio Especial {idx}"
            
            # Paso A: set_user_state WAITING_FOR_SERVICE_TITLE
            bot_engine.set_user_state(phone, "WAITING_FOR_SERVICE_TITLE", {"servicio_idx": srv_idx})
            time.sleep(0.01)

            # Paso B: procesar mensaje con título
            bot_engine.procesar_mensaje(phone, titulo, f"User {idx}")
            time.sleep(0.01)

            # Paso C: verificar estado en SQLite
            db_path = bot_engine.get_db_path()
            with sqlite3.connect(db_path, timeout=10) as conn:
                c = conn.cursor()
                row = c.execute("SELECT estado, temp_data FROM user_sessions WHERE phone = ?", (phone,)).fetchone()
                if not row:
                    return f"Fila no encontrada para {phone}"
                estado, temp_raw = row
                temp = json.loads(temp_raw)
                if estado != "WAITING_FOR_SERVICE_DESC":
                    return f"{phone}: esperaba WAITING_FOR_SERVICE_DESC, obtuve {estado}"
                if temp.get("servicio_idx") != srv_idx:
                    return f"{phone}: servicio_idx cruzado! Esperaba {srv_idx}, obtuve {temp.get('servicio_idx')}"
                if temp.get("nuevo_titulo_srv") != titulo:
                    return f"{phone}: título cruzado! Esperaba '{titulo}', obtuve '{temp.get('nuevo_titulo_srv')}'"

            return None
        except Exception as e:
            return f"Excepción en worker {phone}: {e}"

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_task, i, phones[i]) for i in range(NUM_USERS)]
            results = [f.result() for f in futures]

        errors = [r for r in results if r is not None]
        if errors:
            for err in errors:
                print(f"❌ {err}")
                bugs.append(err)
        else:
            print(f"✅ {NUM_USERS} usuarios concurrentes ejecutados en hilos paralelos sin cruce de datos ni colisiones en SQLite.")

    except Exception as e:
        bugs.append(f"Excepción en test_concurrency_and_isolation: {e}")
    finally:
        cleanup_test_phones(phones)

    return (len(bugs) == 0, bugs)

def run_all_qa():
    print("\n" + "🚀"*35)
    print(" INICIANDO BATERÍA DE AUDITORÍA DE QA - TUWEBLISTA")
    print(" Módulo: bot_engine.py (Migración de Sesiones RAM -> SQLite)")
    print("🚀"*35)

    all_passed = True
    all_bugs = []

    tests = [
        ("Inyección SQL", test_sql_injection),
        ("Cierre de Conexiones", test_connection_handling),
        ("Degradación Elegante", test_graceful_degradation),
        ("Persistencia y Reinicio de Proceso", test_real_process_restart),
        ("Palabras de Escape", test_escape_words),
        ("Concurrencia y Aislamiento", test_concurrency_and_isolation)
    ]

    for name, test_func in tests:
        passed, bugs = test_func()
        if not passed:
            all_passed = False
            all_bugs.extend(bugs)

    print("\n" + "="*70)
    print("📊 RESUMEN DE AUDITORÍA QA:")
    if all_passed:
        print("✅ ESTADO GENERAL: APROBADO")
    else:
        print("⚠️ ESTADO GENERAL: OBSERVADO / RECHAZADO CON HALLAZGOS")
        for b in all_bugs:
            print(f"  - {b}")
    print("="*70 + "\n")
    return all_passed, all_bugs

if __name__ == "__main__":
    run_all_qa()
