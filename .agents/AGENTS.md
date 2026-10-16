# AGENTS.md — TuWebLista
> **Documento Maestro de Contexto para Agentes de IA**
> Versión: 1.0 | Última actualización: 06/10/2026
> **Este archivo es la fuente única de verdad para cualquier agente que trabaje en este proyecto.**
> Antes de escribir una sola línea de código, leer este archivo completo.

---

## 📌 REGLA NÚMERO UNO

> **LEE TODO ESTE ARCHIVO ANTES DE HACER CUALQUIER COSA.**
> Si una directiva aquí contradice algo que el usuario dice en el chat, **este archivo tiene prioridad** y debes señalarlo antes de proceder.

> [!IMPORTANT]
> **El sistema está EN PRODUCCIÓN y con clientes reales.** El objetivo es mejorarlo **sin romper nada**. Ante la duda, **preguntar al usuario** antes de actuar. Cambios chicos, verificables y reversibles.

---

## 🏢 Contexto del Negocio

**Producto:** TuWebLista (antes "TuWebFacil" — renombrado el 05/09/2026)
**Dominio principal:** `tuweblista.com.ar` (landing + subdominios `*.tuweblista.com.ar` para las webs de clientes)
**País / Idioma:** Argentina — todo el contenido de cara al cliente en español rioplatense (voseo).
**Rubro:** SaaS de creación automática de páginas web para comerciantes, artesanos y profesionales independientes que hoy venden solo por redes y no tienen web.
**Propuesta de valor:** Web lista en minutos, generada con IA, y **administrada 100% por WhatsApp** (sin paneles ni logins para el cliente).

**Modelo comercial (valores hardcodeados hoy en [`bot_engine.py`](../bot_engine.py)):**
| Plan | Qué incluye | Precio |
|---|---|---|
| **Gratis** | Web publicada en `https://{slug}.tuweblista.com.ar` | $0 de por vida (sin tarjeta) |
| **Profesional / Premium** | Dominio `.com.ar` propio registrado en NIC Argentina + web publicada | $10.500 inicial ($8.500 dominio anual + $2.000 abono 1er mes). Luego $2.000/mes. |

**Cobro:** **Transferencia bancaria al alias `tuweblista`** → el cliente manda la foto del comprobante por WhatsApp → el administrador **aprueba manualmente** desde `/admin`. **NO se usa Mercado Pago ni ninguna pasarela automática. CERO tarjetas ni débitos automáticos.** (decisión estratégica clave para eliminar fricción).

**Límite operativo:** máximo **3 webs por número de teléfono** (validado en `/process_form`).

---

## 🎯 Visión del Producto

TuWebLista centraliza:
1. **Landing + generador de demos** (`index.html` → `POST /process_form`) — el visitante completa un formulario y la IA genera su web demo al instante.
2. **Webs de clientes** (`templates/client_template.html`) — servidas por subdominio (`{slug}.tuweblista.com.ar`) o por dominio propio (`custom_domain`).
3. **Bot de WhatsApp (panel de control del cliente)** — edición de textos, servicios, imágenes, ubicación, horarios, contacto; búsqueda de dominio; transferencia de titularidad; contacto con soporte; publicación/planes.
4. **Panel de administración** (`/admin`) — aprobación de pagos, publicación con dominio + Nginx + SSL, demos abandonadas y retargeting, mensajes de soporte, difusión masiva, prospección vía Google Maps, marketing.
5. **Marketing automatizado de la propia marca** — borradores de posteos para Instagram con Gemini, programación y publicación vía Instagram Graph API.
6. **Procesos en segundo plano** — scheduler de Instagram, cron de upsell diario, (y scripts de billing/onboarding/watchdog cuyo agendamiento en el VPS **no está confirmado**).

**Ideas futuras documentadas en docs históricos (NO implementadas):** análisis de competidores, "Undo"/historial de versiones, cuota de ediciones mensuales (hoy es un stub que siempre devuelve `True, 999`).

---

## 💻 Stack Tecnológico

### Backend
- **Lenguaje:** Python 3 (venv local en **Python 3.14**; versión del VPS **sin confirmar**)
- **Framework:** Flask `3.0.2` + `flask-cors`
- **Servidor de producción:** Gunicorn (`-w 2 --timeout 120`, puerto 5000) para `app.py`; `receiver.py` corre con el servidor de desarrollo de Flask (puerto 5002)
- **Templating:** Jinja2 (server-side)
- **Gestor de procesos (VPS):** Supervisor

### Frontend
- **HTML + Tailwind CSS vía CDN** (`cdn.tailwindcss.com`) + JavaScript vanilla
- **Íconos/Fuentes:** Font Awesome (CDN, versiones 6.0.0 y 6.5.1 mezcladas), Lucide (`unpkg`, `@latest`), Google Fonts (Inter, Plus Jakarta Sans)
- **Sin frameworks SPA** (no React/Vue). Toda la UI se renderiza con Jinja2.

### Base de Datos
- **Core:** **Supabase (PostgreSQL)** vía SDK `supabase` (Python) — clientes, webs, contenido, suscripciones, pagos.
- **Soporte local:** **SQLite** `messages.db` (en la raíz del proyecto / `os.getcwd()`) — mensajes de soporte, marketing, transferencias, logs de upsell.
- **ORM:** Ninguno. Queries directas con el SDK de Supabase y `sqlite3`.
- Ver detalle en la sección **🗄️ Modelo de Datos**.

### Dependencias declaradas (`requirements.txt`)
```
flask==3.0.2
requests==2.31.0
python-dotenv==1.0.1
supabase>=2.3.0
google-generativeai>=0.8.0   # SDK DEPRECADO por Google — ver sección IA
pandas==2.2.1                # solo usado por código legacy
matplotlib==3.8.3            # solo usado por código legacy
mercadopago==2.2.0           # LEGACY — Mercado Pago NO se usa
Pillow
python-dateutil==2.8.2
pytz==2023.3
flask-cors
gunicorn
```
**No declaradas pero usadas:** `paramiko` (scripts de ops locales), `google-genai` (solo `test_image.py`).

### Inteligencia Artificial
- **Proveedor:** Google Gemini.
- **SDK actual:** `google-generativeai` (**deprecado**). Solo `test_image.py` usa el SDK nuevo `google-genai`.
- **Estado de modelos (Estandarizado el 14/10/2026):**

| Archivo | Uso | Modelo Canónico |
|---|---|---|
| `app.py` → `generar_plantilla_dinamica()` | Generación de la web demo (core del negocio) | `gemini-flash-lite-latest` |
| `app.py` → `generate_promo_ai()` | Borradores de marketing del admin | `gemini-flash-lite-latest` |
| `instagram_auto_poster.py` | Captions de Instagram | `gemini-flash-lite-latest` |
| `scripts/utils/verificar_pagos.py` | Utilidad | `gemini-flash-lite-latest` |
| `test_image.py` | Prueba de Imagen | `imagen-3.0-generate-001` |

- **Investigación completada (14/10/2026):** `gemini-1.5-flash` y `gemini-2.0-flash` fueron retirados por Google (404); `gemini-3.6-flash` y `gemini-3.8-flash` presentan alta saturación (503). El modelo oficial y estable confirmado para producción es `gemini-flash-lite-latest`.
- **Groq:** `GROQ_API_KEY` y `GROQ_URL` se cargan en `app.py` pero **no se usan** (resto histórico).

### Servicios Externos
| Servicio | Uso | Dónde |
|---|---|---|
| **WhatsApp Cloud API** (Graph `v19.0`) | Envío/recepción de mensajes, botones, listas, descarga de media | `sender.py`, `receiver.py` |
| **Instagram Graph API** (`v19.0`) | Publicación de posteos de la marca | `instagram_auto_poster.py` |
| **Unsplash API** | Fotos de la web demo | `app.py` → `buscar_foto_unsplash()` |
| **Nominatim (OpenStreetMap)** | Geocodificación para el mapa | `app.py` y `bot_engine.py` → `obtener_coordenadas()` (duplicada) |
| **Google Places API** | Prospección de leads (CSV) | `app.py` → `/admin/maps_scraper` |
| **`whois` (CLI) / NIC Argentina** | Disponibilidad de dominios `.com.ar` | `bot_engine.py` (`WAITING_FOR_DOMAIN_NAME`) |
| **Certbot** | SSL para dominios de clientes | `app.py` → `/admin/generate_ssl` |
| **Nginx** | Reverse proxy + vhosts por dominio de cliente | VPS + `app.py` (escribe en `/etc/nginx/`) |

### Infraestructura
- **Servidor de producción:** VPS en **Donweb**, acceso SSH por puerto no estándar (datos en scripts de ops — **ver deuda de seguridad**).
- **CDN / Proxy:** **Cloudflare** delante de `tuweblista.com.ar` (detectado en headers `server: cloudflare`, 07/10/2026). Permite reglas WAF para bloquear rutas sin tocar el VPS. Configuración de DNS/SSL de Cloudflare y de los dominios de clientes **sin relevar**.
- **Directorio remoto:** `/var/www/tuwebfacil`
- **Procesos Supervisor** (`/etc/supervisor/conf.d/tuwebfacil.conf`):
  - `tuwebfacil_app` → `gunicorn -w 2 --timeout 120 -b 0.0.0.0:5000 app:app`
  - `tuwebfacil_receiver` → `python receiver.py` (puerto 5002)
  - `tuwebfacil_scheduler` → `python scripts/ops/instagram_scheduler.py` (loop cada 60 s)
- **Nginx** (`/etc/nginx/sites-available/tuwebfacil`): `/` → `127.0.0.1:5000`, `/webhook` → `127.0.0.1:5002`. SSL inyectado por Certbot.
- **Cron:** `0 11 * * *` → `scripts/ops/upsell_cron.py` (log en `upsell_cron.log`).
- **Logs:** `/var/log/tuwebfacil_{app,receiver,scheduler}.{out,err}.log`, más `app.log` y `scheduler.log` en el directorio del proyecto.
- **Logs:** `/var/log/tuwebfacil_{app,receiver,scheduler}.{out,err}.log`, más `app.log` y `scheduler.log` en el directorio del proyecto.
- **VPS Compartido (CONFIRMADO):** El VPS se comparte con **Disgraf Hub** (FastAPI en puerto 8000). **REGLA ABSOLUTA:** NUNCA ejecutar `supervisorctl restart all`. Solo reiniciar quirúrgicamente `tuwebfacil_app`, `tuwebfacil_receiver` y `tuwebfacil_scheduler`.

---

## 📁 Estructura del Proyecto

```
TuWebLista/
├── .agents/
│   ├── AGENTS.md                    ← ESTE ARCHIVO (fuente única de verdad)
│   ├── rules/arquitectura_tuweblista.md ← Puntero a este archivo
│   └── skills/tuweblista_devops/SKILL.md ← Skill de deploy/healthcheck (subordinada a este archivo)
├── .env                             ← Variables de entorno (NO commitear)
├── .env.deploy                      ← Credenciales SSH del VPS para deploy/logs (NO commitear)
├── .gitignore                       ← Ignora .env, .env.*, messages.db, receipts/, *.log, backups, etc.
├── decisions_log.md                 ← Bitácora de decisiones estratégicas
├── requirements.txt                 ← Dependencias Python (incluye paramiko)
│
│ ── CORE (producción) ──────────────────────────────────────────────
├── app.py                           ← App Flask principal (~1200 líneas): landing, demos, webs de clientes,
│                                      ruteo por subdominio/dominio propio, panel /admin completo, marketing
├── receiver.py                      ← Webhook de WhatsApp (Flask, :5002). Despacha a bot_engine en un thread
├── bot_engine.py                    ← Máquina de estados (FSM) del bot de WhatsApp (~775 líneas)
├── sender.py                        ← Cliente WhatsApp Cloud API (texto, imagen, botones, listas, media)
├── instagram_auto_poster.py         ← Generación de captions + publicación en Instagram (importado por app.py y scheduler)
├── index.html                       ← Landing pública + formulario de creación de demo
├── templates/
│   ├── client_template.html         ← Plantilla de la web de cada cliente (contrato JSON: ver Modelo de Datos)
│   ├── admin_dashboard.html         ← Panel de administración (~660 líneas)
│   ├── admin_login.html             ← Login del admin
│   ├── privacidad.html              ← Política de privacidad (requerida por Meta)
│   └── paused.html                  ← Plantilla de sitio pausado (hoy NO referenciada por el código)
├── static/
│   ├── img/                         ← Imágenes de la landing (demos, logo)
│   ├── uploads/                     ← (runtime) Imágenes subidas por clientes vía WhatsApp
│   └── marketing_images/            ← (runtime) Diseños de marketing subidos desde /admin
├── receipts/                        ← (runtime) Comprobantes de pago de clientes — DATOS SENSIBLES
├── messages.db                      ← SQLite de soporte (runtime) — NO commitear, NO deployar
│
│ ── SCRIPTS ───────────────────────────────────────────────────────
├── scripts/
│   ├── db/                          ← Mantenimiento/inspección de BD (check_*, create_table, list_tables)
│   ├── ops/                         ← Operaciones VPS: safe_deploy.py (whitelist estricta), view_logs.py,
│   │                                  instagram_scheduler.py, watchdog.py, upsell_cron.py ...
│   ├── utils/                       ← QA y simulaciones (qa_suite.py, qa_admin_suite.py, simulate_user.py ...)
│   └── onboarding_cron.py           ← Mensajes de onboarding día 3 / día 10 (agendamiento no confirmado)
├── daily_billing_cron.py            ← Suspende webs con pago fallido > 72 hs (en raíz; agendamiento no confirmado)
├── start.command                    ← Arranque local: app :5000 + receiver :5002 + ngrok
├── test_gemini.py / test_image.py   ← Pruebas manuales sueltas de Gemini / Imagen
│
│ ── LEGACY / NO USADO POR EL CORE (no borrar sin aprobación) ──────
├── utils.py                         ← 131 KB, no importado por ningún módulo
├── marketing_bot.py                 ← Bot de marketing original (Supabase + Gemini)
├── competitor_analysis.py           ← Análisis de competidores (depende de marketing_bot)
├── mercadopago_integration.py       ← Integración MP (DESCARTADA como modelo de negocio)
│
│ ── DOCUMENTACIÓN HISTÓRICA (desactualizada — NO usar como fuente de verdad) ──
├── README.md                        ← Menciona Mercado Pago, Python 3.8, repo tuwebfacil
├── SUMMARY.md                       ← Titulado "TuWebFacil"
├── ESTRUCTURA_Y_LOGICA_DEL_PROYECTO.md ← Describe Groq y MP (ya no aplica)
├── database_schema.md               ← Esquema ASPIRACIONAL (no coincide 1:1 con el real)
├── whatsapp_ux.md                   ← Diseño UX original del bot
├── docs/META_API_SETUP.md           ← Guía de configuración de Meta (vigente y útil)
├── instrucciones.txt                ← Hoja de ruta vieja (puerto 5001, ngrok)
├── AGENTS_plantilla_visible.md      ← Plantilla de Disgraf Hub (ignorado en .gitignore)
│
│ ── ARTEFACTOS PROTEGIDOS EN .gitignore ───────────────────────────
├── deploy.tar.gz                    ← Contiene credenciales y estado antiguo — IGNORADO
├── resumenes_banco/                 ← Datos bancarios — IGNORADO
├── app.log, ngrok.log, upsell_cron.log ← IGNORADOS
├── Marketing_Reels/                 ← Assets de marketing (imágenes, prompts) — IGNORADO
└── venv/                            ← Entorno virtual — IGNORADO
```

---

## 🗄️ Modelo de Datos

> [!WARNING]
> `database_schema.md` es un diseño **aspiracional**. El esquema **real** es el que usa el código y se describe abajo. Ante dudas, inspeccionar Supabase en modo **solo lectura** con `scripts/db/` antes de asumir columnas.

### Supabase (PostgreSQL) — tablas efectivamente usadas
| Tabla | Columnas usadas por el código | Notas |
|---|---|---|
| `clients` | `id`, `created_at`, `phone`, `name`, `business_type`, `status` | `phone` único (upsert `on_conflict="phone"`). El bot busca por `ilike '%{últimos 10 dígitos}'`. |
| `websites` | `id`, `created_at`, `client_id`, `subdomain`, `custom_domain`, `seo_title`, `status` | `status`: `demo` → `published` → `maintenance` (suspendida). `subdomain` = slug. El bot administra **la web más reciente** del cliente. |
| `website_content` | `id`, `website_id`, `content`, `is_current`, `version` | **El bot actualiza la fila en el lugar** (no crea versiones nuevas) e incrementa `version`. `version > 1` ⇒ `has_edits=True`. `content` llega como string JSON (app) o dict (bot): siempre parsear con tolerancia a ambos. |
| `subscriptions` | `id`, `client_id`, `plan_type`, `status`, `created_at` | `plan_type`: `premium` / `gratis`. `status`: `active` / `payment_failed`. |
| `payments` | `id`, `client_id`, `subscription_id`, `status`, `payment_method`, `invoice_number`, `created_at` | `status`: `uploaded` → `approved` / `rejected`. ⚠️ **Columnas reutilizadas:** `payment_method` guarda la **ruta local del comprobante** y `invoice_number` guarda el **dominio solicitado**. No "corregir" sin plan de migración. |

### SQLite `messages.db` (soporte local)
| Tabla | Creada por | Uso |
|---|---|---|
| `admin_messages` | `app.initialize_db()` / bot | Mensajes de clientes al soporte y respuestas del admin |
| `marketing_content` | `app.initialize_db()` | Borradores/posteos de Instagram (`draft`, `scheduled`, `published`, `rejected`, `error_publish`) |
| `marketing_settings` | `app.initialize_db()` | Prompt, hashtags y lineamientos visuales (fila `id=1`) |
| `transfers` | `bot_engine` (lazy) | Códigos `mudanza-XXXX` para transferir la titularidad de una web |
| `upsell_logs` | `upsell_cron.py` | Webs a las que ya se envió el mensaje de upsell |

La ruta es `os.path.join(os.getcwd(), "messages.db")` → **depende del working directory** (en el VPS, `directory=/var/www/tuwebfacil` de Supervisor).

### Contrato JSON de `website_content.content`
Claves consumidas por `client_template.html` y/o escritas por el bot. **Cambiar o renombrar una clave rompe webs publicadas.**
```
titulo_web, subtitulo, paleta_colores{primario, secundario},
servicios_sugeridos[3], descripciones_servicios[3], fotos_queries[3], fotos_servicios[3],
foto_hero_query, foto_hero, logo_url, galeria[],
horario            ("ocultar" = no mostrar)
ubicacion_detectada, mapa{lat, lon, zoom}, google_maps,
whatsapp_contacto, email_contacto ("ocultar" = no mostrar), instagram ("" = no mostrar),
plan_type,
lista_precios{titulo, columnas_pago[], items[{servicio, precios{efectivo, transferencia, tarjeta...}}]}
```

### Máquina de Estados del Bot (Persistencia en SQLite `user_sessions` + Caché en RAM)
`IDLE`, `MAIN_MENU`, `EDIT_MENU`, `EDIT_MENU_SERVICIOS`, `WAITING_FOR_TITLE`, `WAITING_FOR_SUBTITLE`, `WAITING_FOR_SERVICE_TITLE`, `WAITING_FOR_SERVICE_DESC`, `WAITING_FOR_LOCATION`, `WAITING_FOR_SCHEDULE`, `WAITING_FOR_IMAGE_ROLE`, `WAITING_FOR_WHATSAPP`, `WAITING_FOR_EMAIL`, `WAITING_FOR_INSTAGRAM`, `WAITING_FOR_DOMAIN_NAME`, `WAITING_FOR_RECEIPT`, `WAITING_FOR_TRANSFER_PHONE`, `WAITING_FOR_ADMIN_MESSAGE`, `WAITING_FOR_PRICE_LIST`, `CONFIRM_PRICE_LIST_DRAFT` (`WAITING_FOR_PLAN_SELECTION` está declarado pero no se usa).
- **Persistencia:** Tabla `user_sessions` en `messages.db` (`phone`, `estado`, `temp_data`, `updated_at`). Helpers `get_user_state()`, `set_user_state()`, `clear_user_state()`. Mantiene caché en memoria en `user_states`.
- **Palabras de escape universales:** `menu`, `menú`, `volver`, `inicio`, `cancelar`.
- **Disparador del panel:** cualquier texto que contenga `confirmar mi web` (los links de la web demo envían "Quiero confirmar mi web").
- **IDs de opciones** (`MAIN_*`, `EDIT_*`, `FOTO_*`, `DOMINIO_*`) se comparan en minúsculas: son contrato con WhatsApp.
- **Comandos de eliminación en WAITING_FOR_PRICE_LIST:** `quitar`, `borrar`, `eliminar`, `ocultar` (remueven `lista_precios` de `website_content` y confirman al usuario).
- El estado **persiste ante reinicios** de `tuwebfacil_receiver`.

---

## 🔑 Variables de Entorno

Todas las variables sensibles van en `.env`. **NUNCA hardcodear credenciales en el código.**

```bash
# Base de datos
SUPABASE_URL=              # URL del proyecto Supabase
SUPABASE_KEY=              # API key de Supabase

# IA
GEMINI_API_KEY=            # Google Gemini

# WhatsApp Cloud API (Meta)
WHATSAPP_TOKEN=            # Token de acceso
PHONE_NUMBER_ID=           # ID del número emisor
BOT_PHONE_NUMBER=          # Número público del bot (links wa.me de las webs demo). daily_billing_cron lo usa como "admin" (revisar)

# Instagram Graph API
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ID=

# APIs de contenido
UNSPLASH_ACCESS_KEY=       # Fotos para webs demo
GOOGLE_MAPS_API_KEY=       # Prospección (/admin/maps_scraper)

# Flask
SECRET_KEY=                # ⚠️ HOY NO ESTÁ en .env → se usa un fallback hardcodeado en app.py

# Sin uso en el código actual (históricas)
GROQ_API_KEY=
TELEGRAM_TOKEN=

# QA (opcional)
QA_TARGET_URL=             # Destino de qa_admin_suite.py (default: producción)
```

**Pendiente de migrar a `.env`** (hoy hardcodeado): contraseña del admin (`ADMIN_PASS` en `app.py` y `qa_admin_suite.py`), teléfono del administrador (`5491134710787` en `bot_engine.py`, `watchdog.py`, `instagram_auto_poster.py`), credenciales SSH del VPS (scripts de `scripts/ops/`, `scripts/fixes/`, `check_logs.py`), email de Certbot.

---

## 🏗️ Convenciones de Código

### Python General
- **Estilo:** PEP 8, indentación de 4 espacios.
- **Strings:** f-strings para interpolación. Textos de cara al cliente en español rioplatense (voseo), con el tono y emojis existentes del bot.
- **Imports:** al tope del archivo, agrupados stdlib → third-party → local. **Código nuevo: NUNCA imports dentro de funciones** (antipatrón muy presente en `app.py` y `bot_engine.py`; limpiar solo cuando se toque esa función y con verificación).
- **Errores:** `except Exception as e:` + `logging.error(...)`. **NUNCA** `bare except:`. Usar `logging` en lugar de `print` en código nuevo.
- **Supabase:** siempre contemplar `supabase is None` (el código degrada si no hay conexión) y fallos de red (ver patrón en `check_custom_domain()`).
- **SQLite:** siempre queries parametrizadas (`?`). Cerrar conexiones.

### Funciones y Módulos
- Una función = una responsabilidad.
- Duplicaciones conocidas a unificar (cuando se planifique): `obtener_coordenadas()` (app + bot), normalización de teléfono (`[-10:]`), helpers de conexión SQLite, cliente Supabase instanciado en cada módulo.
- **No crear un `utils.py` nuevo**: ya existe un `utils.py` legacy de 131 KB. Usar un nombre distinto (p. ej. `core/helpers.py`) cuando se planifique el refactor.

### Rutas Flask
- Rutas de administración bajo `/admin/...` y **siempre** chequear `session.get('admin_logged_in')` al inicio.
- Rutas HTML sin sesión → `redirect(url_for('admin_login'))`. Rutas JSON sin sesión → `jsonify(...)`, 403.
- `app.config['SERVER_NAME'] = 'tuweblista.com.ar'` y la ruta `subdomain="<client_slug>"` dependen del Host. **Cualquier cambio de ruteo debe considerar subdominios y `custom_domain`** (`check_custom_domain()` en `before_request`).

### Bot de WhatsApp (FSM)
- Todo estado nuevo debe: declararse como constante, documentarse en este archivo, y tener salida con las palabras de escape.
- Respetar los límites de WhatsApp: máx. 3 botones (título ≤ 20 chars), listas con título de fila ≤ 24 y descripción ≤ 72 (ya truncado en `sender.py`).
- Trabajo pesado del webhook va en thread (patrón actual de `receiver.py`); el webhook debe responder 200 rápido.

### Templates Jinja2 / Frontend
- Tailwind (CDN) con clases utilitarias; evitar CSS inline salvo necesidad.
- Lógica mínima en templates. Mostrar/ocultar banners de demo según variables del backend (`web_status`, `has_edits`).
- Variables de contexto en `snake_case`.

### Naming
- Variables y funciones: `snake_case` (el código mezcla español e inglés; en código nuevo **seguir el idioma del módulo que se toca**).
- Constantes: `UPPER_SNAKE_CASE`. Estados del bot: `UPPER_SNAKE_CASE` en inglés (`WAITING_FOR_*`).
- Archivos: `snake_case.py` / `snake_case.html`.

### Scripts
- Mantenimiento de BD → `scripts/db/` · Operaciones/Deploy → `scripts/ops/` · QA/Simulación → `scripts/utils/` · Parches → `scripts/fixes/`.
- **Nunca** dejar scripts nuevos sueltos en la raíz.

---

## 🔄 Flujo de Trabajo

### Ciclo de Desarrollo Standard
```
1. LEER este AGENTS.md
2. LEER decisions_log.md (entender qué fue decidido/descartado y por qué)
3. INSPECCIONAR el código real involucrado (el código es la verdad; los docs históricos no)
4. ESPECIFICAR la tarea (qué queremos, criterios de aceptación)
5. PLANIFICAR la implementación (qué archivos tocar, riesgos, cómo revertir)
6. IMPLEMENTAR (cambio mínimo necesario)
7. VERIFICAR (local; nunca contra producción sin autorización)
8. ACTUALIZAR este archivo si hubo cambio arquitectónico
9. REGISTRAR en decisions_log.md si hubo decisión estratégica
10. DEPLOY (solo Coordinador, con autorización explícita del usuario)
```

### Separación de Conversaciones
Para evitar overflow de contexto, cada conversación tiene un foco:
- **Conversación Backend/Bot:** `app.py`, `bot_engine.py`, `receiver.py`, `sender.py`, Supabase, SQLite, crons.
- **Conversación Frontend/Templates:** `index.html`, `client_template.html`, `admin_dashboard.html`, UX.
- **Conversación Marketing IA:** prompts de Gemini, Instagram, `instagram_auto_poster.py`, scheduler.
- **Conversación DevOps:** VPS, Supervisor, Nginx, SSL, deploy (usar la skill `tuweblista_devops`, subordinada a este archivo).

Todas comparten este `AGENTS.md` como contexto unificado.

---

## 🚫 PROHIBICIONES ABSOLUTAS

> [!CAUTION]
> Violar estas reglas puede romper producción, exponer datos de clientes o afectar a otros servicios del servidor.

1. **PROHIBIDO** hardcodear credenciales, API keys, contraseñas, IPs/puertos SSH o teléfonos personales en el código. Todo va en `.env`.
2. **PROHIBIDO** ejecutar `scripts/ops/deploy_vps.py` (o cualquier deploy) **sin autorización explícita del usuario en ese mismo turno**. El script actual empaqueta `.env`, `messages.db`, `receipts/` y credenciales y **pisa la base SQLite de producción** — debe corregirse antes del próximo uso (ver Hallazgos P0).
3. **PROHIBIDO** usar `supervisorctl restart all` o tocar procesos/vhosts que no sean `tuwebfacil_*` / dominios de TuWebLista. El VPS **podría ser compartido** con otros proyectos.
4. **PROHIBIDO** sobrescribir `/etc/nginx/sites-available/tuwebfacil` u otras configs con SSL de Certbot (rompe certificados → `NET::ERR_CERT_COMMON_NAME_INVALID`). Para emergencias SSL existe `scripts/fixes/fix_ssl.py`.
5. **PROHIBIDO** correr `scripts/utils/qa_suite.py` o `qa_admin_suite.py` **sin autorización explícita**: apuntan a **producción** (`tuweblista.com.ar` + Supabase real) y crean/borran datos.
6. **PROHIBIDO** escribir/borrar datos en Supabase de producción desde scripts ad-hoc sin autorización. Inspección = solo lectura.
7. **PROHIBIDO** reintroducir Mercado Pago u otra pasarela de pago automática. El cobro es por **transferencia + aprobación manual**.
8. **PROHIBIDO** cambiar el modelo de Gemini o el SDK de un módulo que funciona hasta que se apruebe la propuesta del ciclo de investigación de IA (ver sección IA).
9. **PROHIBIDO** renombrar/eliminar claves del contrato JSON de `website_content.content`, columnas de Supabase, o "corregir" el uso de `payments.payment_method` / `payments.invoice_number` sin plan de migración aprobado.
10. **PROHIBIDO** cambiar los IDs de opciones del bot (`MAIN_*`, `EDIT_*`, `FOTO_*`, `DOMINIO_*`), las palabras de escape o el disparador `confirmar mi web` sin actualizar todos los puntos que dependen de ellos (incluidos los links de `client_template.html`).
11. **PROHIBIDO** agregar estados a la FSM sin salida por palabras de escape.
12. **PROHIBIDO** borrar archivos legacy (`utils.py`, `marketing_bot.py`, `competitor_analysis.py`, `mercadopago_integration.py`, scripts viejos) sin aprobación del usuario.
13. **PROHIBIDO** commitear o deployar: `.env`, `messages.db`, `receipts/`, `resumenes_banco/`, `deploy.tar.gz`, `*.log`, `venv/`, `static/uploads/`.
14. **PROHIBIDO** hacer el primer commit de "baseline" o un `git push` mientras existan credenciales hardcodeadas en archivos a commitear (el remoto es GitHub).
15. **PROHIBIDO** `bare except:` y nuevos `import` dentro de funciones.
16. **PROHIBIDO** modificar el directorio `venv/`.
17. **PROHIBIDO** crear archivos de reglas duplicados → solo este `AGENTS.md` y `decisions_log.md`.
18. **PROHIBIDO** dejar scripts nuevos sueltos en la raíz del proyecto.

---

## 🧪 Testing

### Estado actual
- **No existe una suite automatizada local** (no hay `pytest`, no hay `tests/`).
- Existen suites **E2E contra producción**: `scripts/utils/qa_suite.py` (webhook + creación/edición de sitio) y `scripts/utils/qa_admin_suite.py` (login admin, pagos, mensajes). Imprimen `🎉 TODOS LOS TESTS PASARON EXITOSAMENTE 🎉` al pasar. **Requieren autorización explícita (Prohibición 5).**
- Scripts manuales de simulación: `scripts/utils/simulate_user.py`, `test_bot_direct.py`, `sim_img.py`, `test_wh_local.py`, `test_gemini.py`, `test_image.py`.

### Estrategia de Testing (a implementar — ciclo futuro)
```
tests/
├── conftest.py            ← Flask test client + mocks de Supabase, WhatsApp (sender), Gemini, Unsplash, Nominatim
├── test_process_form.py   ← Creación de demo, límite de 3 webs, fallback sin Gemini
├── test_client_routing.py ← Subdominio, custom_domain, maintenance (402), demo en memoria
├── test_bot_engine.py     ← Transiciones de la FSM, palabras de escape, edición de contenido
├── test_admin.py          ← Auth de /admin, aprobar/rechazar pago (sin tocar Nginx real)
└── test_sender.py         ← Payloads de WhatsApp (truncados, formatos)
```

### Verificación mínima local (hasta tener suite)
```bash
source venv/bin/activate
python -c "import app; import receiver; import bot_engine; print('OK imports')"
# Arranque completo local (app :5000, receiver :5002, ngrok):
./start.command
```
> [!NOTE]
> Con `SERVER_NAME='tuweblista.com.ar'` fijo, el ruteo de Flask en `localhost` puede no resolver rutas. Verificar antes de asumir que la UI local funciona; no "arreglarlo" sin plan (afecta subdominios en producción).

### Criterios de aceptación para deploy
- [ ] `app.py`, `receiver.py` y `bot_engine.py` importan sin errores.
- [ ] Landing (`/`) responde y el formulario crea una demo.
- [ ] Una web de cliente existente (subdominio) renderiza igual que antes.
- [ ] `/admin/login` funciona y el dashboard carga.
- [ ] El bot responde a `menu` y muestra el Panel de Control.
- [ ] (Con autorización) QA E2E en verde.

---

## 🚀 Deploy

### Estado actual (manual, por tarball)
1. `python scripts/ops/deploy_vps.py` (desde la Mac):
   - Empaqueta toda la raíz excepto `venv`, `__pycache__`, `.git`, `.DS_Store`, `deploy.tar.gz`, `app.log`.
   - Sube por SFTP a `/var/www/tuwebfacil`, descomprime, recrea venv, `pip install -r requirements.txt`.
   - Reescribe la config de Supervisor y ejecuta `supervisorctl restart all`.
   - Escribe la config Nginx **solo si no tiene SSL**, reinicia Nginx, registra el cron de upsell.
2. Verificación post-deploy: logs en `/var/log/tuwebfacil_*.err.log` (scripts `scripts/ops/get_logs*.py`, `check_logs.py`).

> [!WARNING]
> El flujo actual tiene defectos graves (empaqueta secretos y datos, pisa `messages.db` de producción, reinicia todos los procesos de Supervisor, credenciales root en texto plano). **No usar hasta corregir** (ver Hallazgos P0). No hay CI/CD.

### Objetivo (a planificar)
- Credenciales SSH desde `.env.deploy` (gitignored) o llave SSH, nunca en el código.
- Lista de exclusiones estricta (whitelist de archivos de código), sin `.env` ni datos runtime.
- Reinicio solo de `tuwebfacil_app`, `tuwebfacil_receiver`, `tuwebfacil_scheduler`.
- Backup previo de `messages.db` y del directorio remoto.
- A futuro: CI/CD con GitHub Actions (tests → deploy), cuando exista suite local.

### ⚠️ Regla de deploy general
Nunca deployar sin haber verificado localmente los criterios de aceptación.

**REGLA ESTRICTA DE ROLES (DEPLOY Y DOCUMENTACIÓN):** 
1. **SOLO EL AGENTE COORDINADOR, CON AUTORIZACIÓN EXPLÍCITA DEL USUARIO, PUEDE EJECUTAR DEPLOYS, `git commit` O `git push`.** Los Agentes Implementadores y Verificadores tienen PROHIBIDO hacer commits, push o deploys. Su trabajo finaliza entregando el código verificado.
2. **SOLO EL AGENTE COORDINADOR PUEDE EDITAR `decisions_log.md`, `.agents/AGENTS.md` O CUALQUIER ARCHIVO DE DOCUMENTACIÓN ESTRATÉGICA.** Los Agentes Implementadores y Verificadores tienen terminantemente PROHIBIDO tocar estos archivos. El Coordinador es la única fuente de verdad y el único responsable de registrar decisiones arquitectónicas al momento de auditar y autorizar el deploy.

---

## 🤖 Patrones Agénticos

### Modelo de Razonamiento
- Se usa el modelo que el usuario tenga configurado en Antigravity. No iniciar tareas que no puedan completarse en el turno actual.

### Bucle SDD (Especificar → Plan → Tareas → Implementar → Verificar)
Todo desarrollo significativo sigue este bucle:
```
1. ESPECIFICAR  → spec_[feature].md con criterios de aceptación
2. PLAN         → implementation_plan.md con decisiones técnicas, riesgos y rollback
3. TAREAS       → task.md con checklist atómico
4. IMPLEMENTAR  → Ejecución (puede usar subagentes)
5. VERIFICAR    → Verificación local + revisión de criterios
   └── ¿Pasa? → SÍ: actualizar AGENTS.md + decisions_log, deploy autorizado
              → NO: volver a ESPECIFICAR con el diagnóstico del fallo
```

### Flujo Multiagente
| Agente | Rol | Puede escribir código |
|---|---|---|
| **Coordinador** | Único. Planifica (`implementation_plan.md`), asigna tareas, redacta prompts para otros agentes, mantiene este archivo y `decisions_log.md`, hace commits/DEPLOY con autorización. | ❌ NUNCA (solo archivos `.md`) |
| **Investigador** | Lee código, inspecciona Supabase/SQLite en solo lectura, audita, investiga librerías/modelos | ❌ No |
| **Implementador Backend/Bot** | `app.py`, `bot_engine.py`, `receiver.py`, `sender.py`, crons, scripts, datos | ✅ Sí |
| **Verificador Backend/Bot** | Verifica imports, lógica, FSM, queries, regresiones; tests locales | ❌ No |
| **Implementador Front** | `index.html`, `templates/*.html`, Tailwind/JS | ✅ Sí |
| **Verificador Front** | Sintaxis Jinja/HTML, contrato JSON del template, flujos de UI, responsive | ❌ No |
| **Generador de Contenido** | Redacta matrices mensuales de Instagram (30 días), copys, ganchos y CSVs para Canva | ❌ No (solo `.csv` y `.json`) |
| **Verificador de Contenido** | Audita copys (voseo rioplatense, sin promesas falsas, formato CSV Canva, pilares) | ❌ No |

**Invocación del Coordinador:** abrir una conversación nueva y decir: *"Asume el rol de Coordinador"*. El agente leerá este archivo y sabrá que tiene prohibido modificar `.py` o `.html`, y que su tarea es planificar y entregar prompts para las conversaciones ejecutoras.

**Regla para el Coordinador:** al redactar prompts para el Implementador o Generador de Contenido, **NUNCA** pedirle que verifique o audite su propio código o copy. El prompt debe terminar indicando que avise al terminar, para que el usuario pase el trabajo al Verificador.

**Regla para el Verificador:** si falla 3 veces en la misma subtarea → escalar al usuario con diagnóstico.

---

### 📱 Flujo de Marketing de Contenidos (Instagram en Piloto Automático)
1. **Coordinador:** Da el prompt al **Generador de Contenido** especificando el mes y los 6 pilares.
2. **Generador de Contenido:** Crea los archivos CSV para Canva y el JSON de copys con hashtags.
3. **Verificador de Contenido:** Revisa tono rioplatense, ortografía, ausencia de claims falsos y formato CSV.
4. **Usuario:** Abre Canva Pro → "Crear varios" (Bulk Create) con los CSVs → descarga el ZIP de imágenes a su Mac.
5. **Coordinador:** Ejecuta `scripts/ops/sync_marketing_posts.py` para subir imágenes al VPS y agendar en `messages.db` a las 19:00 hs.
6. **VPS:** `tuwebfacil_scheduler` (Supervisor) dispara automáticamente 1 posteo por día a Instagram Graph API.

#### Directrices Estándar de Copywriting para Instagram:
- **Estructura obligatoria:** Gancho potente → Dolor/Problema → Solución TuWebLista → CTA dual.
- **CTA dual obligatorio:** Incluir siempre la dirección web escrita y el atajo de comentarios:
  `🌐 www.tuweblista.com.ar (link directo en nuestra bio)` + *"O comentá DEMO abajo y te la mandamos por privado"*.
- **Tono:** Español rioplatense (voseo argentino) estricto, empático, sin lenguaje técnico.
- **Hashtags (4 a 6 por post):**
  - Fijos de marca: `#TuWebLista #EmprendedoresArgentinos #NegociosLocales #PymeArgentina #PaginaWeb`
  - Variables de nicho (2 a 3 según el rubro del día): ej. `#GastronomiaArgentina`, `#PeluqueriaCanina`, `#EsteticaArgentina`, `#ElectricistasArgentinos`.
- **Horario estándar de publicación:** 19:00 hs (hora Argentina).

### MCPs Disponibles
- **Context7:** documentación actualizada de librerías (Flask, supabase-py, google-genai, WhatsApp/Graph API).

---

## 📋 Estilo de Commits

```
tipo(scope): descripción en imperativo en español

tipos: feat | fix | refactor | docs | style | test | deploy | chore | security

scopes sugeridos: app | bot | receiver | sender | admin | landing | template | marketing | db | ops | agents

Ejemplos:
security(ops): mover credenciales SSH a .env.deploy
fix(bot): permitir salir de WAITING_FOR_DOMAIN_NAME con "cancelar"
feat(admin): agregar filtro de pagos rechazados
docs(agents): documentar nuevo estado de la FSM
chore(git): ampliar .gitignore con datos runtime
```

### Reglas de PR
- Un PR = una feature o fix.
- El PR no se mergea hasta que el Verificador lo apruebe.
- El título sigue el formato de commits. Descripción: qué cambia, por qué, cómo probar, cómo revertir.

---

## 🔗 Sincronización Obligatoria

Después de cualquier cambio arquitectónico o decisión estratégica, el agente **DEBE**:
1. **Actualizar este `AGENTS.md`** en la sección correspondiente (estructura, modelo de datos, FSM, prohibiciones, estado).
2. **Registrar en `decisions_log.md`** con fecha, decisión y razón.
3. **No editar** `README.md` / `SUMMARY.md` / `ESTRUCTURA_Y_LOGICA_DEL_PROYECTO.md` como fuente de verdad: son **históricos** hasta que se planifique su reescritura.
4. **Deploy** solo según la sección Deploy.

---

## 🩺 Hallazgos de Auditoría (06/10/2026)

| Prioridad | Hallazgo | Ubicación |
|---|---|---|
| **P0** | ~~`Flask(static_folder='.', static_url_path='')` expone públicamente archivos de la raíz~~ — **RESUELTO (13/10/2026):** Parcheado en código (`static_folder='static'`) y en producción. Doble capa: WAF Cloudflare (403) + Flask (404). `/receipts/` protegido bajo auth admin. | `app.py:32, 308` |
| **P0** | ~~`deploy.tar.gz` en directorio web servido~~ — **RESUELTO (13/10/2026):** Removido de `/var/www/tuwebfacil/` hacia `/root/deploy.tar.gz.bak`. | Servidor VPS |
| **P0** | Contraseña **root** del VPS en texto plano en ~30 scripts. Recomendado: rotarla, pasar a llave SSH y `.env.deploy`. | `scripts/ops/*`, `scripts/fixes/*`, `check_logs.py` |
| **P0** | El deploy pisa `messages.db` de producción con la copia local (vacía) → pérdida de mensajes/marketing/transferencias. | `deploy_vps.py` |
| **P1** | Contraseña de admin hardcodeada y **commiteable** (`ADMIN_PASS`), `SECRET_KEY` con fallback hardcodeado (no está en `.env`). | `app.py:33, 460` |
| **P1** | Webhook de WhatsApp sin verificación de `hub.verify_token` ni firma `X-Hub-Signature-256`. | `receiver.py` |
| **P1** | `/receipts/<file>` y `/uploads/<file>` públicos sin auth (comprobantes de pago accesibles por URL). | `app.py:304-310` |
| **P1** | `receiver.py` corre con `debug=True` en producción. | `receiver.py:70` |
| **P1** | `.gitignore` insuficiente; Git con 1 solo commit y gran volumen de cambios sin commitear; remoto en GitHub. | raíz |
| **P1** | Desconocido si el código del VPS == local, y si el VPS es compartido. | — |
| **P2** | Modelos Gemini inconsistentes + SDK deprecado `google-generativeai`. | ver sección IA |
| **P2** | Estado del bot y `DEMO_SITES` en memoria (se pierden al reiniciar; `DEMO_SITES` no se comparte entre los 2 workers de Gunicorn). | `bot_engine.py`, `app.py` |
| **P2** | `verificar_y_consumir_cuota()` es un stub (`True, 999`) pero los mensajes del bot muestran "Te quedan 999 ediciones". Onboarding promete "30 ediciones / límite de 10". | `bot_engine.py:114`, `scripts/onboarding_cron.py` |
| **P2** | `approve_payment` escribe configs de Nginx y ejecuta `systemctl`/`certbot` desde el proceso web (requiere root). | `app.py:712-835` |
| **P2** | Sin suite de tests local; QA solo contra producción. | — |
| **P3** | Código y docs legacy (utils.py 131 KB, MP, marketing_bot, competitor_analysis), scripts sueltos en raíz, dependencias sin uso en `requirements.txt` y faltantes (`paramiko`). | raíz |
| **P3** | Mensajes con marca vieja "TuWebFacil" en crons (`daily_billing_cron.py`, `onboarding_cron.py`) y User-Agent de Nominatim. | varios |

---

## 📊 Estado Actual del Proyecto (06/10/2026)

| Módulo | Estado | Deuda Técnica |
|---|---|---|
| Landing + generador de demos | ✅ Funcional | Gemini + Unsplash + Nominatim. Límite 3 webs/teléfono. `DEMO_SITES` en memoria. |
| Webs de clientes (subdominio / dominio propio) | ✅ Funcional | Ruteo por `SERVER_NAME` + `before_request`. `paused.html` sin uso; suspensión = HTML inline 402. |
| Bot de WhatsApp (FSM) | ✅ Funcional | Estado en memoria. Cuota de ediciones stub. Imports dentro de funciones. Webhook sin verificación de firma. |
| Pagos por transferencia | ✅ Funcional | Columnas de `payments` reutilizadas. Comprobantes servidos sin auth. |
| Publicación con dominio + Nginx + SSL | ✅ Funcional (según código) | Ejecutado desde el proceso web con permisos root. |
| Panel Admin | ✅ Funcional | Contraseña hardcodeada, sin CSRF, rutas GET que mutan estado (`/admin/approve`, `/admin/reject`). |
| Soporte (mensajes al admin) | ✅ Funcional | SQLite local. Teléfono admin hardcodeado. |
| Transferencia de titularidad (`mudanza-XXXX`) | ✅ Funcional | Códigos sin expiración. |
| Marketing Instagram (borradores, programación, publicación) | ✅ Funcional | Modelos Gemini mezclados; scheduler como proceso Supervisor. |
| Prospección Google Maps | ✅ Funcional | — |
| Upsell diario (cron 11:00) | ✅ Agendado | Importa `app` completo (efectos secundarios de import). |
| Billing / Onboarding / Watchdog | ❓ Sin confirmar | Scripts existen; no está confirmado que estén agendados en el VPS. |
| Tests automatizados | ❌ No existe | Solo QA E2E contra producción. |
| Git / Control de versiones | ⚠️ Parcial | 1 commit, mucho trabajo sin commitear, `.gitignore` insuficiente. |
| CI/CD | ❌ No existe | Deploy manual por tarball (defectuoso, ver P0). |
| Documentación | ⚠️ En transición | Este archivo es la nueva fuente única; docs previos son históricos. |

### Backlog sugerido (orden recomendado, cada ítem requiere aprobación)
1. **P0 Seguridad:** verificar exposición pública de archivos → hotfix de `static_folder` → rotar credenciales expuestas (root VPS, Supabase, WhatsApp, Gemini, Instagram, etc.) → sacar credenciales de scripts → corregir `deploy_vps.py`.
2. **P1 Baseline:** comparar código local vs VPS (solo lectura) → ampliar `.gitignore` → commit baseline limpio.
3. **P1 Hardening:** `ADMIN_PASS`/`SECRET_KEY` a `.env`, verificación del webhook, proteger `/receipts`, `debug=False` en receiver.
4. **P2 IA:** ciclo de investigación de modelos Gemini + migración a `google-genai`.
5. **P2 Tests:** suite local con pytest y mocks.
6. **P3 Limpieza:** legacy, requirements, reescritura de README.

---

*Este archivo fue generado el 06/10/2026 por auditoría agéntica del código fuente y debe mantenerse actualizado por cualquier agente que trabaje en TuWebLista.*

