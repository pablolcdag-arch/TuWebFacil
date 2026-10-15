#!/usr/bin/env python3
"""
update_scheduled_copys.py — Inyecta la firma canónica completa de transparencia
(NIC.ar $8.500 al año, $0 configuración técnica, $2.000 abono y Cero Tarjetas)
en los 30 copys locales y en la base de datos de producción (messages.db) del VPS.
"""

import os
import json
import sqlite3
import paramiko
from dotenv import dotenv_values

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_ENV_PATH = os.path.join(BASE_DIR, ".env.deploy")
JSON_PATH = os.path.join(BASE_DIR, "copys_completos_instagram_30_dias.json")

CANONICAL_SIGNATURE = (
    "💡 ¿Cuánto cuesta tener tu web?\n"
    "• Con subdominio: Solo $2.000 al mes (menos que un alfajor 🍫).\n"
    "• Con dominio propio .com.ar: $8.500 al año (costo oficial de NIC Argentina).\n"
    "🎁 Toda la configuración técnica del dominio y servidor te la hacemos 100% GRATIS (otras agencias te cobran más de $80.000 por esto).\n"
    "🔒 Cero tarjetas ni ataduras: pagás mes a mes por transferencia solo si querés seguir."
)

OLD_HOOK_PREFIX = "💡 ¿Cuánto cuesta"

def update_local_json():
    print("📖 Leyendo copys_completos_instagram_30_dias.json...")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)

    updated_posts = []
    for p in posts:
        caption = p["caption"]
        
        # Si ya tiene un bloque de "¿Cuánto cuesta", lo reemplazamos
        if OLD_HOOK_PREFIX in caption:
            partes = caption.split("\n\n")
            new_partes = []
            skip = False
            for part in partes:
                if part.startswith(OLD_HOOK_PREFIX):
                    new_partes.append(CANONICAL_SIGNATURE)
                else:
                    new_partes.append(part)
            p["caption"] = "\n\n".join(new_partes)
        else:
            # Si no lo tiene, insertar antes de www.tuweblista.com.ar o hashtags
            partes = caption.split("\n\n")
            new_partes = []
            inserted = False
            for part in partes:
                if ("www.tuweblista.com.ar" in part or "#" in part) and not inserted:
                    new_partes.append(CANONICAL_SIGNATURE)
                    inserted = True
                new_partes.append(part)
            if not inserted:
                new_partes.append(CANONICAL_SIGNATURE)
            p["caption"] = "\n\n".join(new_partes)

        updated_posts.append(p)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(updated_posts, f, ensure_ascii=False, indent=2)

    print("✅ Archivo JSON local actualizado con la firma canónica completa.")
    return updated_posts

def update_vps_database(updated_posts):
    if not os.path.exists(DEPLOY_ENV_PATH):
        print("❌ No se encontró .env.deploy para conectar al VPS.")
        return

    config = dotenv_values(DEPLOY_ENV_PATH)
    HOST = config.get("VPS_HOST", "149.50.151.121")
    PORT = int(config.get("VPS_PORT", 5023))
    USER = config.get("VPS_USER", "root")
    PASS = config.get("VPS_PASS")
    REMOTE_DIR = config.get("VPS_DIR", "/var/www/tuwebfacil")

    print(f"📡 Conectando a VPS {HOST}:{PORT} para actualizar copys en messages.db...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

    # Subir el JSON actualizado al VPS primero
    sftp = ssh.open_sftp()
    remote_json_path = f"{REMOTE_DIR}/copys_completos_instagram_30_dias.json"
    sftp.put(JSON_PATH, remote_json_path)
    sftp.close()
    print("⬆️ JSON sincronizado en el VPS.")

    # Ejecutar script remoto en python para actualizar messages.db
    remote_py_script = f"""
import sqlite3
import json

db_path = '{REMOTE_DIR}/messages.db'
json_path = '{remote_json_path}'

with open(json_path, 'r', encoding='utf-8') as f:
    posts = json.load(f)

conn = sqlite3.connect(db_path)
c = conn.cursor()

updated_count = 0
for p in posts:
    dia = p['dia']
    day_str = f'{{dia:02d}}'
    filename = f'post_dia_{{day_str}}.png'
    media_url = f'https://tuweblista.com.ar/static/marketing_images/{{filename}}'
    new_caption = p['caption']
    
    c.execute('''
        UPDATE marketing_content 
        SET copy_text = ? 
        WHERE design_description = ? AND status = 'scheduled'
    ''', (new_caption, media_url))
    if c.rowcount > 0:
        updated_count += c.rowcount

conn.commit()
conn.close()
print(f'TOTAL_ACTUALIZADOS: {{updated_count}}')
"""
    stdin, stdout, stderr = ssh.exec_command(f"python3 -c \"{remote_py_script}\"")
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print("Respuesta remota:", out)
    if err:
        print("Stderr remoto:", err)

    ssh.close()
    print("✅ Actualización en base de datos del VPS completada.")

if __name__ == "__main__":
    posts = update_local_json()
    update_vps_database(posts)
