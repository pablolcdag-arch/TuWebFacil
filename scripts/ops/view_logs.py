#!/usr/bin/env python3
"""
view_logs.py — Consulta remota y segura de logs de TuWebLista.

Uso:
  python scripts/ops/view_logs.py               # Muestra los últimos 30 logs de la app
  python scripts/ops/view_logs.py app 50        # Muestra los últimos 50 logs de tuwebfacil_app
  python scripts/ops/view_logs.py receiver 30   # Muestra logs del webhook de WhatsApp
  python scripts/ops/view_logs.py scheduler 30  # Muestra logs del scheduler de Instagram
"""

import os
import sys
import paramiko
from dotenv import dotenv_values

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_ENV_PATH = os.path.join(BASE_DIR, ".env.deploy")

if not os.path.exists(DEPLOY_ENV_PATH):
    print(f"❌ Error: No se encontró el archivo de credenciales {DEPLOY_ENV_PATH}")
    sys.exit(1)

config = dotenv_values(DEPLOY_ENV_PATH)
HOST = config.get("VPS_HOST", "149.50.151.121")
PORT = int(config.get("VPS_PORT", 5023))
USER = config.get("VPS_USER", "root")
PASS = config.get("VPS_PASS")

service = sys.argv[1] if len(sys.argv) > 1 else "app"
lines = int(sys.argv[2]) if len(sys.argv) > 2 else 30

valid_services = {
    "app": ("/var/log/tuwebfacil_app.out.log", "/var/log/tuwebfacil_app.err.log"),
    "receiver": ("/var/log/tuwebfacil_receiver.out.log", "/var/log/tuwebfacil_receiver.err.log"),
    "scheduler": ("/var/log/tuwebfacil_scheduler.out.log", "/var/log/tuwebfacil_scheduler.err.log"),
}

if service not in valid_services:
    print(f"❌ Servicio inválido '{service}'. Opciones: {list(valid_services.keys())}")
    sys.exit(1)

out_log, err_log = valid_services[service]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
except Exception as e:
    print(f"❌ Error de conexión SSH: {e}")
    sys.exit(1)

print("=" * 60)
print(f"📄 Logs de 'tuwebfacil_{service}' (Últimas {lines} líneas)")
print("=" * 60)

cmd = f"tail -n {lines} {err_log} 2>/dev/null; echo '--- STDOUT ---'; tail -n {lines} {out_log} 2>/dev/null"
stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode())

ssh.close()

