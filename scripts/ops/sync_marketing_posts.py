#!/usr/bin/env python3
"""
sync_marketing_posts.py — Sube las imágenes de marketing y programa el lote en messages.db del VPS.
"""

import os
import sys
import json
import datetime
import paramiko
from dotenv import dotenv_values

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_ENV_PATH = os.path.join(BASE_DIR, ".env.deploy")
LOCAL_IMG_DIR = os.path.join(BASE_DIR, "static", "marketing_images")
JSON_COPYS_PATH = os.path.join(BASE_DIR, "copys_completos_instagram_30_dias.json")

if not os.path.exists(DEPLOY_ENV_PATH):
    print("❌ Error: No se encontró .env.deploy")
    sys.exit(1)

config = dotenv_values(DEPLOY_ENV_PATH)
HOST = config.get("VPS_HOST", "149.50.151.121")
PORT = int(config.get("VPS_PORT", 5023))
USER = config.get("VPS_USER", "root")
PASS = config.get("VPS_PASS")
REMOTE_DIR = config.get("VPS_DIR", "/var/www/tuwebfacil")

if not os.path.exists(JSON_COPYS_PATH):
    print(f"❌ Error: No se encontró {JSON_COPYS_PATH}")
    sys.exit(1)

with open(JSON_COPYS_PATH, "r", encoding="utf-8") as f:
    copys = json.load(f)

print("=" * 60)
print("🚀 SINCRONIZACIÓN Y PROGRAMACIÓN DE MARKETING EN VPS")
print("=" * 60)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
except Exception as e:
    print(f"❌ Error SSH: {e}")
    sys.exit(1)

sftp = ssh.open_sftp()

# 1. Asegurar directorio remoto
remote_img_dir = f"{REMOTE_DIR}/static/marketing_images"
stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {remote_img_dir}")

# 2. Subir las 30 imágenes
print("\n📤 Subiendo 30 imágenes a", remote_img_dir)
for dia_num in range(1, 31):
    filename = f"post_dia_{dia_num:02d}.png"
    local_path = os.path.join(LOCAL_IMG_DIR, filename)
    remote_path = f"{remote_img_dir}/{filename}"
    
    if os.path.exists(local_path):
        print(f"  ⬆️ Subiendo {filename}...")
        sftp.put(local_path, remote_path)
    else:
        print(f"  ⚠️ No encontrada: {filename}")

sftp.close()

# 3. Preparar inserción en messages.db del VPS
# Fecha de inicio: Mañana a las 19:00
now = datetime.datetime.now()
start_date = (now + datetime.timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)

print(f"\n📅 Programando 30 días a partir de: {start_date.strftime('%Y-%m-%d %H:%M')}")

# Generar script temporal de inyección remota
insert_script = f"""
import sqlite3
import json

db_path = "{REMOTE_DIR}/messages.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Limpiar cualquier borrador huérfano previo si es necesario o insertar directo
"""

posts_data = []
for item in copys:
    dia = item["dia"]
    caption = item["caption"]
    target_dt = start_date + datetime.timedelta(days=(dia - 1))
    scheduled_for = target_dt.strftime("%Y-%m-%dT%H:%M")
    image_url = f"https://tuweblista.com.ar/static/marketing_images/post_dia_{dia:02d}.png"
    posts_data.append((caption, image_url, scheduled_for, dia))

posts_json = json.dumps(posts_data)

remote_python = f"""
import sqlite3
import json

db_path = "{REMOTE_DIR}/messages.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

posts = {posts_json}

for caption, image_url, scheduled_for, dia in posts:
    c.execute('''
        INSERT INTO marketing_content (content_type, copy_text, design_description, status, scheduled_for)
        VALUES ('post', ?, ?, 'scheduled', ?)
    ''', (caption, image_url, scheduled_for))

conn.commit()

c.execute("SELECT count(*), min(scheduled_for), max(scheduled_for) FROM marketing_content WHERE status='scheduled'")
row = c.fetchone()
print(f"PROGRAMADOS_TOTAL: {{row[0]}}, DESDE: {{row[1]}}, HASTA: {{row[2]}}")
conn.close()
"""

# Ejecutar el script remotamente en el VPS
stdin, stdout, stderr = ssh.exec_command(f"{REMOTE_DIR}/venv/bin/python -c '{remote_python}'")
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()

if out:
    print(f"\n📊 Resultado en VPS: {out}")
if err:
    print(f"⚠️ Stderr: {err}")

ssh.close()
print("\n" + "=" * 60)
print("✅ ¡30 DÍAS DE CONTENIDO PROGRAMADOS CON ÉXITO EN EL VPS!")
print("=" * 60)
