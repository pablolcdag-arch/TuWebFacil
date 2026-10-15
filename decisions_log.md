# Bitácora de Decisiones (Decisions Log) — TuWebLista

Este documento registra las decisiones estratégicas y arquitectónicas del proyecto. Todo agente debe leerlo (después de `.agents/AGENTS.md`) para entender el **"por qué"** detrás de las directivas vigentes y qué alternativas ya fueron descartadas.

**Reglas de uso:**
- Las entradas se agregan **al final** (orden cronológico). No se editan ni borran entradas pasadas: si una decisión cambia, se agrega una nueva entrada que la reemplaza y se indica cuál.
- Solo el **Agente Coordinador** (o el usuario) registra decisiones.
- Cada decisión que afecte reglas o arquitectura debe reflejarse también en `.agents/AGENTS.md`.

### Formato de entrada
```markdown
## [DD/MM/AAAA] — Título corto de la decisión
- **Decisión:** Qué se decidió.
- **Razón:** Por qué (problema, evidencia, contexto).
- **Alternativas descartadas:** Qué se evaluó y por qué no. (opcional)
- **Impacto:** Archivos / módulos / procesos afectados. (opcional)
- **Reemplaza a:** Fecha y título de la decisión anterior, si aplica. (opcional)
```

---

## [05/09/2026] — Reestructuración de carpeta y nombre de dominio *(histórica)*
- **Decisión:** Mover el proyecto de la carpeta principal del usuario hacia `Documentos/TuWebLista` y renombrar las menciones del proyecto de "TuWebFacil" a "TuWebLista".
- **Razón:** El dominio final adquirido fue `tuweblista.com.ar` debido a la disponibilidad. Mantener el nombre viejo en la estructura del código y de archivos generaba confusión y pérdida de contexto.
- **Dato adicional:** Los recursos de marketing visual para videos de la plataforma (Reels/TikTok) se unificaron dentro de la carpeta `Marketing_Reels/` del proyecto.
- **Nota (06/10/2026):** El renombre quedó incompleto: el directorio del VPS (`/var/www/tuwebfacil`), los procesos de Supervisor (`tuwebfacil_*`), el remoto de Git y algunos mensajes al cliente siguen usando "TuWebFacil". No renombrar infraestructura sin plan.

---

## [06/10/2026] — Adopción de `.agents/AGENTS.md` como fuente única de verdad
- **Decisión:** Se crea `.agents/AGENTS.md` como Documento Maestro para agentes de IA, construido a partir de una auditoría del código real. `README.md`, `SUMMARY.md`, `ESTRUCTURA_Y_LOGICA_DEL_PROYECTO.md` y `database_schema.md` pasan a ser **documentación histórica**. `.agents/rules/arquitectura_tuweblista.md` se reduce a un puntero hacia `AGENTS.md`.
- **Razón:** Las reglas estaban dispersas en varios archivos y varios estaban desactualizados (mencionaban Mercado Pago, Groq, Python 3.8, nombre TuWebFacil), lo que inducía a errores a los agentes.
- **Impacto:** Flujo de trabajo multiagente (Coordinador / Investigador / Implementador / Verificador) y bucle SDD formalizados.

## [06/10/2026] — Las suites QA E2E requieren autorización explícita
- **Decisión:** `scripts/utils/qa_suite.py` y `qa_admin_suite.py` dejan de ser obligatorias tras cada cambio; solo se ejecutan con autorización explícita del usuario. Se planifica una suite local con pytest + mocks como tarea futura.
- **Razón:** Ambas suites apuntan a producción (`tuweblista.com.ar` y Supabase real) y crean/borran datos.
- **Reemplaza a:** Regla "Obligatoriedad de QA" del antiguo `.agents/rules/arquitectura_tuweblista.md`.

## [06/10/2026] — Modelo de Gemini: congelado hasta ciclo de investigación
- **Decisión:** No se cambia el modelo ni el SDK de Gemini en módulos que funcionan hasta que un Agente Investigador releve los modelos vigentes y el usuario apruebe una propuesta (modelo canónico + migración de `google-generativeai` a `google-genai`).
- **Razón:** Hoy conviven `gemini-flash-lite-latest`, `gemini-3.6-flash`, `gemini-2.5-flash` y `gemini-1.5-flash` con un SDK deprecado; cambiar sin evidencia podría romper la generación de webs (core del negocio).

---

## [14/10/2026] — Fixes en publicación de dominios propios (custom_domain y SSL)
- **Decisión / Correcciones:**
  1. Se corrigió `check_custom_domain()` en `app.py` para normalizar el host removiendo el prefijo `www.`, permitiendo que tanto `dominio.com.ar` como `www.dominio.com.ar` resuelvan a la misma web sin redirigir al dominio base.
  2. Se añadió tolerancia a `content` ya parseado como `dict` (proveniente del bot o de Supabase) en `check_custom_domain()` para evitar `TypeError: must be str, not dict` (error 500).
  3. Se confirmó el flujo de SSL con Certbot: los dominios en Cloudflare deben incluir el registro DNS para `www` para que Let's Encrypt valide ambos certificados sin `NXDOMAIN`.
- **Razón:** Primer cliente Premium real (`soteria.com.ar`) en producción evidenció el fallo en la resolución de `www` y el parsing de contenido JSON.
- **Impacto:** Ambos dominios (`soteria.com.ar` y `www.soteria.com.ar`) responden 200 OK bajo HTTPS sin conflicto con otros servicios del VPS.

## [14/10/2026] — Saneamiento de scripts de operaciones y protección de Disgraf Hub
- **Decisión:**
  1. Se eliminaron scripts de prueba huérfanos con credenciales hardcodeadas en texto plano y comandos destructivos (`supervisorctl restart all`).
  2. Se crearon herramientas canónicas en `scripts/ops/`: `safe_deploy.py` (despliegue quirúrgico con whitelist estricta y reinicio exclusivo de `tuwebfacil_*`) y `view_logs.py` (inspección remota segura de logs).
  3. Las credenciales SSH del VPS se aislaron en `.env.deploy`, ignorado por Git.
  4. Se actualizó `.gitignore` blindando bases de datos SQLite locales, comprobantes (`receipts/`), resúmenes bancarios, logs y assets pesados.
- **Razón:** Blindar la coexistencia con Disgraf Hub en el VPS compartido y evitar la fuga de credenciales o sobreescritura accidental de datos en producción.
- **Impacto:** Operaciones seguras y desacopladas sin riesgo para Disgraf Hub ni caída de servicios en producción.

## [14/10/2026] — Auditoría de modelos de IA y rotación de GEMINI_API_KEY
- **Decisión:**
  1. Se reemplazó la clave de Gemini por una generada en un proyecto nuevo y limpio (`Tuweblista`). La anterior sufría de `403 PERMISSION_DENIED: Your project has been denied access` debido a la exposición pública previa del `.env`.
  2. Se confirmó que `gemini-1.5-flash` y `gemini-2.0-flash` fueron retirados por Google (404), y que `gemini-3.6-flash` y `gemini-3.8-flash` presentan alta saturación y fallos 503 temporales.
  3. Se estandarizó el modelo en `app.py` (`generar_plantilla_dinamica` y `generate_promo_ai`), `instagram_auto_poster.py` y `verificar_pagos.py` usando `gemini-flash-lite-latest`, el cual responde con alta velocidad, voseo correcto y generación de JSON perfecta.
- **Razón:** Resolver el bloqueo 403 y garantizar estabilidad y velocidad en la generación de demos y copys.
- **Impacto:** Creación de páginas web demo 100% operativa en producción y local.

## [14/10/2026] — Automatización de Marketing en Instagram y Flujo Bulk Canva
- **Decisión:**
  1. Se diseñó la estrategia de marketing mensual para `@tuweblistaok` basada en un ciclo de 6 pilares rotativos (Dolor/Objeción, Nichos de Comercio, Educación, Demostración de Bot, Prueba Social y Oferta Directa).
  2. Se adoptó el flujo híbrido: Generación de matriz editorial y copys con IA -> Bulk Create en Canva Pro -> Sincronización automática de imágenes y agenda en `messages.db` del VPS mediante `sync_marketing_posts.py`.
  3. Se programaron los primeros 30 días de contenido para publicarse automáticamente todos los días a las 19:00 hs (del 15/10/2026 al 13/11/2026) a través de `tuwebfacil_scheduler` e Instagram Graph API.
  4. Se formalizó la creación del rol multiagente **Generador de Contenido** y **Verificador de Contenido** para desacoplar la redacción creativa del Coordinador en los meses subsiguientes.
- **Razón:** Lograr presencia continua y profesional sin demanda de tiempo manual diario.
- **Impacto:** Canal de Instagram funcionando en piloto automático con 30 días de publicaciones activas.

## [14/10/2026] — Estrategia de Pricing Transparente: $2.000/mes y Política "Cero Tarjetas"
- **Decisión:**
  1. Se redujo el abono mensual del plan Profesional de $4.000 a **$2.000 ARS/mes** (menos que el costo de un alfajor triple o un café).
  2. El costo inicial de alta de dominio propio pasa a **$10.500 ARS** ($8.500 registro anual en NIC Argentina al costo + $2.000 de mantenimiento del primer mes).
  3. Se consolidó como gancho comercial y de conversión la política de **"CERO tarjetas de crédito/débito y CERO suscripciones o débitos automáticos"**: el cliente transfiere mes a mes al alias `tuweblista` solo si desea continuar con el servicio, eliminando toda fricción o temor a cargos sorpresa.
  4. Se actualizaron en concordancia: landing page (`index.html`), bot de WhatsApp (`bot_engine.py`), prompts de marketing (`app.py`, `instagram_auto_poster.py`) y documentación maestra (`AGENTS.md`).
- **Razón:** Eliminar la barrera de entrada y la fricción financiera en comerciantes y microemprendedores argentinos, transformando la contratación en una compra impulsiva de bajo costo y máxima retención.
- **Impacto:** Menor costo de adquisición de clientes, mayor conversión desde la demo gratuita y alineación total entre los mensajes publicitarios, la landing y el bot de WhatsApp.

## [14/10/2026] — Migración de Sesiones del Bot a SQLite (`user_sessions`), Modo WAL y Auditoría QA
- **Decisión:**
  1. Se migró la máquina de estados del bot de WhatsApp (`user_states` en RAM) a una tabla persistente `user_sessions` en `messages.db` (`phone`, `estado`, `temp_data`, `updated_at`).
  2. Se adoptó el patrón de resiliencia: lecturas con caché en RAM, escrituras sincronizadas en SQLite, degradación elegante a `IDLE` en caso de fallo de disco y tolerancia a JSON corrupto.
  3. QA detectó y subsanó un bug bloqueante de file descriptor leaks (`with sqlite3.connect` no cierra la conexión en Python), implementando el cierre explícito con `try...finally: if conn: conn.close()`.
  4. Se activó el modo de concurrencia `PRAGMA journal_mode=WAL;` en SQLite para permitir lecturas y escrituras multihilo simultáneas sin bloqueos de base de datos.
  5. Se crearon y aprobaron las suites de verificación automatizadas en `scripts/utils/qa_user_sessions_audit.py` y `scripts/utils/test_user_sessions.py`.
- **Razón:** Evitar que los usuarios pierdan su sesión y contexto de edición ante reinicios del proceso o del VPS, y garantizar estabilidad concurrente ante ráfagas de mensajes.
- **Impacto:** Sesiones de usuario 100% persistentes y seguras ante caídas o deploys.

