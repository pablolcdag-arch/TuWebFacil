#!/usr/bin/env python3
"""
safe_deploy.py — Despliegue seguro y selectivo para TuWebLista en VPS Donweb.

REGLAS CRÍTICAS:
1. NUNCA sube .env, messages.db, receipts/ ni logs (protege datos de producción).
2. NUNCA ejecuta 'supervisorctl restart all' (protege Disgraf Hub y otros servicios).
3. Solo reinicia 'tuwebfacil_app', 'tuwebfacil_receiver' y 'tuwebfacil_scheduler'.
"""

import os
import sys
import paramiko
from dotenv import dotenv_values

# Cargar credenciales desde .env.deploy
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_ENV_PATH = os.path.join(BASE_DIR, ".env.deploy")

if not os.path.exists(DEPLOY_ENV_PATH):
    print(f"❌ Error: No se encontró el archivo de credenciales {DEPLOY_ENV_PATH}")
    print("Asegurate de que exista .env.deploy con VPS_HOST, VPS_PORT, VPS_USER, VPS_PASS, VPS_DIR.")
    sys.exit(1)

config = dotenv_values(DEPLOY_ENV_PATH)
HOST = config.get("VPS_HOST", "149.50.151.121")
PORT = int(config.get("VPS_PORT", 5023))
USER = config.get("VPS_USER", "root")
PASS = config.get("VPS_PASS")
REMOTE_DIR = config.get("VPS_DIR", "/var/www/tuwebfacil")

if not PASS:
    print("❌ Error: VPS_PASS no está configurado en .env.deploy")
    sys.exit(1)

# Archivos y carpetas permitidos para sincronizar (WHITELIST ESTRICTA)
ALLOWED_FILES = [
    "app.py",
    "bot_engine.py",
    "receiver.py",
    "sender.py",
    "instagram_auto_poster.py",
    "daily_billing_cron.py",
    "requirements.txt",
    "index.html",
]

ALLOWED_DIRS = [
    ("templates", "templates"),
    ("static/img", "static/img"),
    ("scripts/ops", "scripts/ops"),
    ("scripts/onboarding_cron.py", "scripts/onboarding_cron.py"),
]

# Archivos PROHIBIDOS explícitos
FORBIDDEN = [
    ".env",
    ".env.deploy",
    "messages.db",
    "receipts",
    "resumenes_banco",
    "deploy.tar.gz",
    "venv",
    "app.log",
]

def ensure_remote_dir(sftp, remote_path):
    dirs = []
    head, tail = os.path.split(remote_path)
    while head and head != "/":
        dirs.append(head)
        head, tail = os.path.split(head)
    for d in reversed(dirs):
        try:
            sftp.stat(d)
        except IOError:
            try:
                sftp.mkdir(d)
            except IOError:
                pass

def deploy():
    print("=" * 60)
    print("🚀 Iniciando despliegue SEGURO de TuWebLista...")
    print(f"📡 Conectando a {HOST}:{PORT} como {USER}...")
    print("=" * 60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
    except Exception as e:
        print(f"❌ Error de conexión SSH: {e}")
        sys.exit(1)

    sftp = ssh.open_sftp()

    # 1. Sincronizar archivos raíz permitidos
    print("\n📦 Sincronizando archivos principales...")
    for filename in ALLOWED_FILES:
        local_path = os.path.join(BASE_DIR, filename)
        if os.path.exists(local_path):
            remote_path = f"{REMOTE_DIR}/{filename}"
            print(f"  ⬆️  {filename} -> {remote_path}")
            sftp.put(local_path, remote_path)
        else:
            print(f"  ⚠️  Archivo local no encontrado, salteando: {filename}")

    # 2. Sincronizar carpetas permitidas
    print("\n📁 Sincronizando directorios permitidos...")
    for local_rel, remote_rel in ALLOWED_DIRS:
        local_abs = os.path.join(BASE_DIR, local_rel)
        if not os.path.exists(local_abs):
            continue

        if os.path.isfile(local_abs):
            remote_path = f"{REMOTE_DIR}/{remote_rel}"
            ensure_remote_dir(sftp, remote_path)
            print(f"  ⬆️  {local_rel} -> {remote_path}")
            sftp.put(local_abs, remote_path)
        elif os.path.isdir(local_abs):
            for root, _, files in os.walk(local_abs):
                for f in files:
                    if f.startswith(".") or f.endswith(".pyc") or f == "__pycache__":
                        continue
                    full_local = os.path.join(root, f)
                    rel_sub = os.path.relpath(full_local, BASE_DIR)
                    
                    # Chequear si está prohibido
                    if any(forbid in rel_sub for forbid in FORBIDDEN):
                        continue
                        
                    full_remote = f"{REMOTE_DIR}/{rel_sub}"
                    ensure_remote_dir(sftp, full_remote)
                    print(f"  ⬆️  {rel_sub} -> {full_remote}")
                    sftp.put(full_local, full_remote)

    sftp.close()

    # 3. Reiniciar de forma QUIRÚRGICA solo TuWebLista (NUNCA RESTART ALL)
    print("\n🔄 Reiniciando procesos de TuWebLista en Supervisor...")
    cmd_restart = "supervisorctl restart tuwebfacil_app tuwebfacil_receiver tuwebfacil_scheduler"
    stdin, stdout, stderr = ssh.exec_command(cmd_restart)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    
    if out:
        print(f"  {out}")
    if err:
        print(f"  ⚠️ Stderr: {err}")

    # 4. Verificar estado
    print("\n🔍 Verificando estado de los servicios...")
    cmd_status = "supervisorctl status tuwebfacil_app tuwebfacil_receiver tuwebfacil_scheduler"
    stdin, stdout, stderr = ssh.exec_command(cmd_status)
    status_out = stdout.read().decode().strip()
    print(status_out)

    ssh.close()
    print("\n" + "=" * 60)
    print("✅ ¡Despliegue completado con éxito! (Disgraf Hub intacto).")
    print("=" * 60)

if __name__ == "__main__":
    deploy()
