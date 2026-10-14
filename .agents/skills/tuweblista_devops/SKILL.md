---
name: tuweblista_devops
description: Guía y procedimientos para automatizar el despliegue, chequeo de salud y monitoreo del VPS para TuWebLista.
---
# Skill: TuWebLista DevOps

> [!IMPORTANT]
> Esta skill está **subordinada a [`.agents/AGENTS.md`](../../AGENTS.md)** (secciones *Infraestructura*, *Prohibiciones Absolutas*, *Deploy* y *Hallazgos de Auditoría*). Si algo de acá contradice a `AGENTS.md`, **manda `AGENTS.md`**. Leelo antes de usar esta skill.

## 0. Reglas de oro (resumen de AGENTS.md)
- **Nada se ejecuta en el VPS sin autorización explícita del usuario en ese mismo turno** (deploys, reinicios, cambios de Nginx/Supervisor/cron, escrituras en disco).
- Los chequeos de **solo lectura** (leer logs, `supervisorctl status`, `cat` de configs) también requieren que el usuario haya pedido el diagnóstico.
- El VPS **podría ser compartido** con otros proyectos: tocar **únicamente** los procesos `tuwebfacil_app`, `tuwebfacil_receiver`, `tuwebfacil_scheduler` y los vhosts de TuWebLista. **PROHIBIDO `supervisorctl restart all`.**
- **PROHIBIDO** sobrescribir configs de Nginx que tengan bloques SSL de Certbot. Emergencias SSL → `scripts/fixes/fix_ssl.py` (con autorización).
- El sitio está detrás de **Cloudflare** (proxy). Considerarlo al diagnosticar errores 5xx, caché o IPs reales.

## 1. Despliegue (Deploy) al VPS

> [!CAUTION]
> **`scripts/ops/deploy_vps.py` está BLOQUEADO hasta que se corrija** (ver *Hallazgos P0* en AGENTS.md). Hoy:
> - empaqueta `.env`, `messages.db`, `receipts/`, `resumenes_banco/` y scripts con credenciales,
> - **pisa `messages.db` de producción** con la copia local,
> - deja `deploy.tar.gz` dentro de `/var/www/tuwebfacil` (directorio servido públicamente),
> - ejecuta `supervisorctl restart all` y `apt-get update/install`,
> - tiene la contraseña root en texto plano.

Requisitos que debe cumplir el deploy corregido (a implementar en un ciclo SDD aprobado):
1. **Credenciales** desde `.env.deploy` (gitignored) o llave SSH. Nunca en el código.
2. **Whitelist de archivos** de código (`*.py` del core, `templates/`, `static/img/`, `index.html`, `requirements.txt`, `scripts/`). Jamás: `.env`, `messages.db`, `receipts/`, `resumenes_banco/`, `static/uploads/`, `static/marketing_images/`, `*.log`, `deploy.tar.gz`, `venv/`, `Marketing_Reels/`.
3. **Backup previo** en el VPS de `messages.db` y del código actual (para rollback).
4. El tarball se sube y se descomprime **fuera** del directorio servido, y se borra al terminar.
5. Reinicio **solo** de `tuwebfacil_app`, `tuwebfacil_receiver`, `tuwebfacil_scheduler`.
6. No ejecutar `apt-get` en cada deploy.
7. Solo lo ejecuta el **Agente Coordinador**, con autorización explícita y después de verificar los criterios de aceptación de AGENTS.md.

## 2. Verificación Post-Despliegue
- `supervisorctl status tuwebfacil_app tuwebfacil_receiver tuwebfacil_scheduler` → todos `RUNNING`.
- Últimas líneas de `/var/log/tuwebfacil_{app,receiver,scheduler}.err.log` sin tracebacks nuevos.
- `https://tuweblista.com.ar/` responde 200; una web de cliente por subdominio renderiza; `/admin/login` carga.
- Archivos sensibles **NO** accesibles públicamente (deben devolver 403/404): `/.env`, `/messages.db`, `/app.py`, `/deploy.tar.gz`. Usar `curl -I` (solo headers, sin descargar contenido).

## 3. Diagnóstico de Salud (Healthcheck)
Cuando el usuario pida un reporte de estado:
- Estado de los 3 procesos `tuwebfacil_*` (no de todo Supervisor).
- Errores recientes en los logs de cada proceso (resumir, no volcar secretos ni datos personales).
- Conectividad del webhook de WhatsApp (`/webhook` responde al GET).
- Conexión a Supabase en **solo lectura** (`scripts/db/`).
- Cron de upsell presente (`crontab -l | grep upsell_cron`) y si billing/onboarding/watchdog están agendados (hoy **sin confirmar**).
- Entregar un informe breve: OK / Alertas / Acciones sugeridas (sin ejecutarlas).

## 4. Gestión de Pagos (Contexto)
El sistema **no usa pasarelas automáticas** (Mercado Pago descartado). Flujo:
- El cliente envía la foto del comprobante por WhatsApp → se guarda en `receipts/` y se crea un registro en `payments` con `status='uploaded'` (`payment_method` = ruta del comprobante, `invoice_number` = dominio solicitado).
- El admin aprueba/rechaza desde `/admin`.
Los chequeos de pagos se enfocan en la recepción/almacenamiento del comprobante y el estado en la BD, no en APIs de pago. Los comprobantes son **datos sensibles**: nunca copiarlos, listarlos públicamente ni incluirlos en deploys.
