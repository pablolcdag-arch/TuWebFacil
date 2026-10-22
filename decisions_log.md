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

## [14/10/2026] — Implementación del Flujo Interactivo del Día 27 (Trial Closing)
- **Decisión:**
  1. Se actualizó el cron de avisos (`scripts/ops/upsell_cron.py`) para activar el aviso al día 27 de la prueba gratuita (`days_active >= 27`), descartando webs con dominios propios, clientes con suscripción activa paga o webs ya avisadas (`upsell_logs`).
  2. Se despacha un mensaje interactivo con botones de WhatsApp (`TRIAL_SUBDOMINIO` con título "🟢 Subdominio $2.000" de 19 caracteres y `TRIAL_DOMINIO` con título "💎 Dominio Propio" de 16 caracteres), respetando el límite estricto de <= 20 caracteres por botón de Meta.
  3. En `bot_engine.py`, se implementó la interceptación de respuestas (botones o texto: "1", "subdominio", "opcion 1", "2", "dominio", "opcion 2"):
     - Opción 1: Transiciona a `WAITING_FOR_RECEIPT` con `temp_data = {"plan": "subdominio", "monto": 2000}` e instruye la transferencia bancaria al alias `tuweblista`.
     - Opción 2: Transiciona a `WAITING_FOR_DOMAIN_NAME` con `temp_data = {"plan": "custom_domain", "monto": 10500}`, busca disponibilidad en NIC.ar vía `whois` y, si está libre, pasa a `WAITING_FOR_RECEIPT` preservando `plan`, `monto` y `dominio`.
     - Al recibir imagen de comprobante en `WAITING_FOR_RECEIPT`, se registra el pago en Supabase y se resetea el estado a `IDLE`.
  4. Se implementó la suite de prueba integral `scripts/utils/test_day27_flow.py` con 100% PASS, y se verificó compatibilidad con `qa_user_sessions_audit.py` sin regresiones.
- **Razón:** Automatizar el cierre comercial del trial de 30 días 3 días antes de su vencimiento, maximizando la retención y conversión sin intervención manual.
- **Impacto:** Proceso de upsell y cobranza completamente autónomo e interactivo vía WhatsApp.

## [14/10/2026] — Implementación de la Pantalla de "Sitio Pausado" (Día 30) y Flujo de Reactivación
- **Decisión:**
  1. Se rediseñó por completo `templates/paused.html` con estética oscura moderna, Tailwind CSS, botón dinámico de reactivación directa a WhatsApp y erradicación total del branding legacy "TuWebFacil" hacia **TuWebLista**.
  2. En `app.py`, se reemplazó el texto plano hardcodeado de mantenimiento por `render_template('paused.html', bot_phone=BOT_PHONE, slug=...)` con código HTTP 402 (*Payment Required*) tanto para subdominios como para dominios personalizados.
  3. En `daily_billing_cron.py`, se implementó la detección de webs con trial vencido (`days_active >= 30`) sin suscripción activa paga, suspendiéndolas a `status = 'maintenance'` y reportando el resumen diario por WhatsApp al administrador.
  4. En `bot_engine.py`, se implementó la intención de reactivación ("reactivar mi web", "reactivar") guiando al usuario con las instrucciones de pago por transferencia y pase a `WAITING_FOR_RECEIPT`.
  5. Se implementó la suite automatizada `scripts/utils/test_paused_flow.py` con 100% PASS, validada conjuntamente con `test_day27_flow.py` y `qa_user_sessions_audit.py` (0 regresiones).
- **Razón:** Proveer un cierre elegante al ciclo de prueba de 30 días, protegiendo los datos del usuario durante 15 días y habilitando un canal directo de reactivación por WhatsApp sin fricciones.
- **Impacto:** Ciclo de vida del cliente (Día 0 Demo -> Día 27 Aviso interactivo -> Día 30 Pausado -> Reactivación) 100% automatizado y en producción.

## [16/10/2026] — Implementación de Lista de Precios & Servicios Interactiva (Etapa 1 — Estilo Soteria)
- **Decisión:**
  1. Se implementó el motor de ingesta inteligente en `scripts/utils/price_list_parser.py`, capaz de parsear archivos tabulares (.xlsx, .xls, .csv, .tsv), documentos PDF (.pdf) y texto plano libre con detección heurística de columnas (Servicio, Efectivo, Transferencia, Tarjeta, etc.) y normalización automática de moneda argentina (`format_price()`).
  2. En `bot_engine.py`, se incorporó la opción "📋 Lista de Precios" (`EDIT_PRECIOS`) en `EDIT_MENU` (manteniendo exactamente 10 opciones interactivas para Meta) y los nuevos estados `WAITING_FOR_PRICE_LIST` y `CONFIRM_PRICE_LIST_DRAFT`.
  3. Se diseñó el flujo de seguridad con **Vista Previa de Borrador**: antes de publicar, el bot genera un token seguro (`secrets.token_hex(4)`), almacena el borrador temporalmente en `user_sessions.temp_data` (SQLite WAL) y envía un enlace de preview (`?preview=TOKEN`) con 2 botones de respuesta rápida ("✅ Publicar Precios" [18 chars] y "❌ Cancelar" [10 chars], ambos $\le 20$ caracteres).
  4. En `app.py`, se habilitó la ruta `/precios` y el overlay seguro en memoria para renderizar el borrador con `is_preview=True` sin tocar Supabase hasta la confirmación explícita del cliente.
  5. En `templates/client_template.html`, se construyó la sección `#precios` con diseño 100% responsive:
     - Desktop: tabla completa con bordes suaves, columnas de pago dinámicas y botón WhatsApp.
     - Mobile: selector de pestañas táctiles (`[ 💵 Efectivo ] [ 📲 Transferencia ] [ 💳 Tarjeta ]`), tarjetas compactas sin scroll horizontal y actualización reactiva de precios.
     - Buscador instantáneo Vanilla JS tolerante a mayúsculas y acentos (`normalize("NFD")`).
     - Banner de borrador superior ámbar destacado (`is_preview=True`).
     - Botón de reserva de turnos directo a WhatsApp con mensaje preformateado y codificado (`urlencode`).
  6. Se actualizaron `requirements.txt` (`openpyxl`, `pypdf`) y `scripts/ops/safe_deploy.py` para sincronizar `price_list_parser.py` e instalar dependencias en el VPS de forma automatizada.
  7. Se crearon las suites de pruebas automatizadas `scripts/utils/test_price_list_backend.py` y `scripts/utils/test_price_list_frontend.py`, auditadas y aprobadas al 100% por los verificadores QA, certificando cero regresiones en los flujos preexistentes.
- **Razón:** Permitir que profesionales y comercios de servicios (centros de estética, peluquerías, talleres, consultorios) publiquen listas de precios con múltiples modalidades de pago gestionadas íntegramente por WhatsApp y con control previo antes de salir al público.
- **Impacto:** Apertura del segmento de profesionales y centros de estética (arquetipo Soteria), potenciando la conversión de visitantes web a turnos agendados por WhatsApp.

## [16/10/2026] — Soporte para Quitar / Eliminar Lista de Precios desde WhatsApp
- **Decisión:**
  1. En `bot_engine.py`, se implementó la detección dinámica en `EDIT_MENU` (`edit_precios`): si el cliente ya cuenta con una `lista_precios` activa en su web, el bot lo notifica y le brinda la posibilidad tanto de actualizarla (enviando nuevo archivo/foto/texto) como de eliminarla escribiendo palabras clave (`quitar` o `borrar`).
  2. En el estado `WAITING_FOR_PRICE_LIST`, se interceptan las palabras clave `["quitar", "borrar", "eliminar", "ocultar"]`:
     - Remueve `lista_precios` del JSON `content` (`content.pop("lista_precios", None)`).
     - Persiste la actualización en Supabase incrementando la versión mediante `actualizar_web_content()`.
     - Confirma la eliminación por WhatsApp con el enlace de la web actualizada y redirige al menú de edición.
     - Si el usuario no tenía lista publicada, informa que no existía ninguna lista previa sin realizar escrituras innecesarias en base de datos.
  3. Se actualizó la suite `scripts/utils/test_price_list_backend.py` incorporando el Test 7 de eliminación y adaptación de menú (100% PASS).
  4. En `app.py`, se implementó la tabla SQLite `price_drafts` para persistir el historial de borradores generados por el bot, garantizando que los enlaces de vista previa (`/precios?preview=TOKEN`) se mantengan accesibles incluso si la sesión del usuario en `user_sessions` cambia de estado antes de la confirmación.
  5. En `templates/client_template.html`, se corrigió la declaración del buscador y se optimizó el selector táctil de pestañas para mobile (`tabPills`), permitiendo alternar fluidamente entre métodos de pago y recalculando el mensaje preformateado de WhatsApp en tiempo real.
- **Razón:** Permitir a los clientes despublicar listas de precios o promociones vencidas de forma autónoma desde WhatsApp sin requerir asistencia manual de soporte técnico, asegurando robustez en las vistas previas y una experiencia táctil impecable en celulares.
- **Impacto:** Autonomía 100% para el ciclo de vida completo de la lista de precios (crear, previsualizar, publicar, actualizar y eliminar) con UX móvil optimizada.

## [17/10/2026] — Implementación de Selección Múltiple de Servicios y Presupuesto por WhatsApp (Carrito de Tratamientos)
- **Decisión:**
  1. En `templates/client_template.html`, se incorporaron checkboxes interactivos (`.price-item-checkbox` en la tabla desktop y `.price-item-checkbox-mobile` en tarjetas mobile) para permitir que los usuarios seleccionen múltiples tratamientos o zonas simultáneamente.
  2. Se diseñó e implementó la barra flotante sticky inferior (`#price-multi-bar`), estilizada con `bg-slate-900/95 backdrop-blur-md text-white`, que despliega el contador dinámico de tratamientos elegidos, el total estimado por modalidad de pago en vivo, el botón "Limpiar" y el botón verde "Pedir Turno" directo a WhatsApp.
  3. En el bundle JavaScript, se implementó la sincronización bidireccional de checkboxes, el parser numérico tolerante a moneda argentina (`parsePriceValue`), el formateador ARS (`formatARS`), la actualización reactiva del total según la pestaña activa en mobile (`currentMobileCol`) y la persistencia de selecciones ante búsquedas en tiempo real.
  4. Se diseñó el generador de mensaje unificado para WhatsApp con viñetas y desglose de precios por servicio y totales por modalidad de pago (`encodeURIComponent`), preservando al mismo tiempo los botones individuales de "Pedir Turno" para consultas puntuales.
  5. Se actualizó la suite `scripts/utils/test_price_list_frontend.py` incorporando el Test 6 completo (100% PASS), auditado y aprobado formalmente por el Verificador Frontend con cero regresiones en los flujos críticos (Día 27, Pausado, SQLite WAL).
  6. Se resolvió la jerarquía de capas elevando `#price-multi-bar` a `z-[150]` (y `bottom-6 md:bottom-8`), evitando que quede solapado por el banner demo inferior (`#bottom-dark-banner` con `z-[100]`), y se rediseñó con identidad visual explícita de carrito (`🛒 Carrito: X tratamientos`, total destacado y botón `Pedir Presupuesto (X)`).
  7. Se implementó la sincronización reactiva de botones individuales de fila (`handleRowWaBtnClick`): si existen tratamientos seleccionados (`selectedServices.size > 0`), hacer clic en el botón verde de cualquier fila auto-incluye el servicio y despacha el presupuesto consolidado completo a WhatsApp, adaptando además el texto de los botones a `Pedir Presupuesto (X)` con anillo de énfasis `ring-primary`.
- **Razón:** En centros de estética, peluquerías y profesionales de la salud/belleza, los clientes suelen combinar varios tratamientos o zonas en una misma consulta. Esta funcionalidad permite armar presupuestos combinados en un solo clic, aumentando el ticket promedio del negocio sin fricción.
- **Impacto:** Experiencia de compra tipo "carrito ágil" 100% integrada a WhatsApp en el frontend, sin requerir cambios de backend ni migraciones de base de datos.

## [17/10/2026] — Implementación de Submenú de Precios y FSM Interactiva para Promociones por Fecha (Backend Fase 1)
- **Decisión:**
  1. En `bot_engine.py`, se implementó el submenú interactivo en `EDIT_MENU` (`edit_precios`): si el cliente ya tiene una lista de precios publicada, se despliega una lista interactiva de WhatsApp (`WAITING_FOR_PRICE_MENU_OPTION`) con opciones para actualizar precios, iniciar promoción por fecha, detener promoción activa (si existe) y quitar lista, respetando estrictamente el límite de $\le 10$ filas de Meta.
  2. Se diseñó e implementó la máquina de estados finitos (FSM) interactiva paso a paso para la configuración de promociones por fecha (reserva anticipada / jornadas):
     - `WAITING_FOR_PROMO_TITLE`: Ingesta del título del evento o jornada (ej: "Jornada Láser 17 de Noviembre").
     - `WAITING_FOR_PROMO_DISCOUNT_1`: Validación estricta de porcentaje entero entre 1 y 99 con repregunta defensiva.
     - `WAITING_FOR_PROMO_DATE_1`: Helper `parse_promo_date` con cálculo inteligente de año (soporta `DD/MM` y `DD/MM/AAAA`) y formateo en español rioplatense (ej: "27 de Octubre de 2026") y formato ISO `YYYY-MM-DD`.
     - `WAITING_FOR_PROMO_TIER2_CHOICE`: Botones interactivos $\le 20$ caracteres ("➕ Sí, agregar tramo" / "🚀 No, solo este").
     - `WAITING_FOR_PROMO_DISCOUNT_2` y `WAITING_FOR_PROMO_DATE_2`: Configuración opcional del segundo tramo de descuento.
  3. Se creó el generador de borrador `generar_borrador_promocion`: inyecta el objeto `promocion_fecha` dentro de una copia profunda de `lista_precios`, persiste el borrador en la tabla SQLite `price_drafts` y envía la vista previa interactiva (`/precios?preview=TOKEN`) con botones $\le 20$ caracteres ("✅ Activar Promo" / "❌ Cancelar").
  4. En `CONFIRM_PROMO_DRAFT`, la confirmación persiste en Supabase `website_content.content["lista_precios"]["promocion_fecha"]` incrementando la versión en base de datos.
  5. Se implementó el helper y acción `detener_promocion_activa` (`PROMO_DETENER`), accesible tanto desde el submenú como por palabras clave globales ("detener promo", "frenar promo", "pausar promo"), permitiendo a los comerciantes frenar la promoción inmediatamente cuando completan la agenda sin alterar los precios base.
  6. Se amplió la suite `scripts/utils/test_price_list_backend.py` con el Test 10 integral (100% PASS), auditada y aprobada por el Verificador Backend con cero regresiones en los flujos preexistentes.
- **Razón:** Permitir a los negocios de servicios (estética, depilación, consultorios, talleres) crear campañas de reserva anticipada por WhatsApp con fechas y porcentajes validados, protegiendo la agenda y eliminando ambigüedades en la interpretación de fechas y precios.
- **Impacto:** Apertura comercial para promociones escalonadas (*early-bird*) gestionadas 100% por WhatsApp con vista previa obligatoria y freno de parada de emergencia.

## [17/10/2026] — Implementación de Banner de Jornada y Precios Tachados en Tiempo Real (Frontend Fase 1)
- **Decisión:**
  1. En `templates/client_template.html`, se implementó el contenedor responsivo `#promo-banner-container` en la sección `#precios`, renderizado condicionalmente cuando `lista_precios.promocion_fecha` está activa:
     - Muestra el encabezado de jornada (ícono de megáfono, título y badge `PROMO ACTIVA` o `PRÓXIMAMENTE`).
     - Despliega las tarjetas/píldoras interactivas de escalas (`.promo-scale-pill`) con fechas límite legibles (`hasta_display`), porcentaje de descuento y estado en tiempo real.
  2. En el bundle JavaScript de la plantilla, se diseñó la lógica reactiva en el cliente:
     - Compara la fecha actual (`new Date()` en formato local `YYYY-MM-DD`) contra la fecha límite de cada escala (`esc.hasta`).
     - Detecta automáticamente la escala vigente hoy, destacando su píldora con borde esmeralda, fondo enriquecido y el indicador animado `¡ACTIVO HOY!`.
     - Si la fecha límite expiró, marca la píldora como finalizada (`opacity-50 line-through`); si la fecha es futura, la mantiene en espera informativa.
  3. Precios tachados y descuentos dinámicos:
     - **Tabla Desktop:** Para cada celda de precio, renderiza el precio regular tachado (`line-through opacity-60 text-xs`) y calcula el valor promocional destacado en negrita esmeralda (`text-emerald-600 font-bold`) acompañado del badge `-X% OFF`.
     - **Tarjetas Mobile:** Aplica idéntico tratamiento en las filas móviles y se recalcula reactivamente al conmutar entre pestañas de modalidades de pago (Efectivo / Transferencia / Tarjeta).
  4. Sincronización con el Carrito Multi-Servicio (`#price-multi-bar` z-[150]):
     - Las sumas estimadas de los tratamientos seleccionados computan directamente los valores promocionales con descuento aplicado.
     - El generador de mensaje para WhatsApp desglosa los servicios con sus importes bonificados e incluye una línea destacada con la jornada y el descuento de reserva anticipada aplicado.
  5. Retrocompatibilidad: El template degrada de forma 100% limpia y sin errores JavaScript cuando un cliente no tiene lista de precios o no tiene promociones por fecha configuradas.
  6. Se amplió la suite `scripts/utils/test_price_list_frontend.py` incorporando el Test 7 integral (100% PASS), verificado y aprobado formalmente con balance estricto de tags Jinja2 y cero regresiones.
- **Razón:** Maximizar la conversión de clientes finales visibilizando de inmediato el beneficio de la reserva anticipada (urgencia visual mediante precios tachados) sin obligar al usuario a iniciar la conversación por WhatsApp para conocer el descuento real.
- **Impacto:** Experiencia visual de alta gama en la web pública del cliente con sincronización total entre banner, tabla, pestañas móviles, carrito y mensaje de WhatsApp.

## [17/10/2026] — Promoción de Precios al Menú Principal y Formato Estricto de Fechas con Año
- **Decisión:**
  1. En `bot_engine.py`, se promovió la gestión de precios directamente al Menú Principal (`MAIN_MENU`), ubicando `{"id": "MAIN_PRECIOS", "title": "📋 Precios y Promos", "description": "Gestionar lista y promociones"}` en segunda posición (índice 1). La lista principal queda con 7 opciones, respetando holgadamente el límite de $\le 10$ filas de WhatsApp Cloud API.
  2. Se extrajo la lógica de apertura a la función modular `mostrar_menu_precios(wa_id)`:
     - Si la web ya posee lista de precios, despacha el submenú interactivo (`PRECIOS_ACTUALIZAR`, `PROMO_FECHA_START`, `PROMO_DETENER` si aplica, `PRECIOS_QUITAR` y `PRECIOS_VOLVER`).
     - Si no posee lista, despacha el instructivo de carga de archivos (Excel, PDF, imagen o texto) y transiciona a `WAITING_FOR_PRICE_LIST`.
  3. En `EDIT_MENU`, se removió `EDIT_PRECIOS` de la lista interactiva, reduciéndola de 10 a 9 opciones enfocadas estrictamente en textos, imágenes y datos de contacto, manteniendo el alias en código por retrocompatibilidad.
  4. Navegación y salidas: Salir mediante `PRECIOS_VOLVER`, detener una promo activa o eliminar la lista ahora redirige limpiamente al Menú Principal ("Panel de Control"), reseteando el estado sin bloqueos en SQLite.
  5. En la máquina de estados de promociones por fecha (`WAITING_FOR_PROMO_DISCOUNT_1`, `WAITING_FOR_PROMO_DATE_1`, `WAITING_FOR_PROMO_DISCOUNT_2`, `WAITING_FOR_PROMO_DATE_2`), se modificaron los mensajes interactivos y fallbacks de error para exigir explícitamente el año completo en formato `DD/MM/AAAA` (ej. `27/10/2026` y `15/11/2026`), eliminando la sugerencia sin año `27/10` para prevenir cualquier ambigüedad en el calendario.
  6. Se actualizó la suite `scripts/utils/test_price_list_backend.py` (Tests 4, 7 y 10) validando el acceso desde `MAIN_MENU`, retrocompatibilidad con `EDIT_MENU`, contrato de caracteres y validación de fechas (100% PASS).
- **Razón:** Los comerciantes actualizan precios y promociones con mucha mayor frecuencia que los textos o fotos institucionales; tener "Precios y Promos" en el menú principal reduce la fricción operativa a cero y descomprime el submenú de edición. Asimismo, exigir el año explícito en las fechas elimina errores de interpretación humana y rollovers accidentales de año.
- **Impacto:** Arquitectura de navegación del bot más intuitiva, mayor visibilidad para la herramienta de precios y prompts conversacionales 100% deterministas.

## [18/10/2026] — Corrección en Bot: Resolución y Entrega de URL Real en "Ver mi página web"
- **Decisión:**
  1. En `bot_engine.py`, dentro del manejador del menú principal (`MAIN_MENU`), se corrigió la opción `MAIN_VER_LINK` (y sus variantes `"ver mi pagina web"`, `"ver mi página web"`, `"ver web"`, `"1"`):
     - Ahora invoca dinámicamente `obtener_web_del_cliente(wa_id)`.
     - Si la web posee dominio propio (`custom_domain`), formatea y envía `https://{custom_domain}`.
     - Si la web opera bajo subdominio, formatea y envía `https://{slug}.tuweblista.com.ar`.
     - Incluye mensaje amigable con emojis, enlace clickeable directo y consejo para compartirlo en redes sociales o con clientes.
     - Si no se detecta ninguna web vinculada al número remitente, envía mensaje defensivo informando la situación.
  2. En `scripts/utils/test_price_list_backend.py`, se ampliaron los tests unitarios dentro del Test 4 (4E, 4F, 4G) cubriendo la entrega bajo subdominio, dominio propio y el fallback sin web registrada (100% PASS).
- **Razón:** La opción enviaba un texto estático que prometía el enlace temporal pero omitía la consulta a Supabase y la URL final, impidiendo a los comerciantes acceder rápidamente a su web desde WhatsApp.
- **Impacto:** Entrega inmediata y precisa del enlace web (demo o publicada) en un solo toque desde el menú principal.

## [18/10/2026] — Erradicación de Mensajes Muertos (Dead-Ends): Botón Interactivo Menú Principal
- **Decisión:**
  1. En `bot_engine.py`, se estandarizó la entrega de botones interactivos (`send_whatsapp_buttons`) incorporando `[ 📱 Menú Principal ]` (`id: "btn_menu"`, 16 caracteres, cumpliendo estrictamente con el límite $\le 20$ de Meta) y la correspondiente leyenda de texto en los 6 flujos informativos y de confirmación del bot:
     - `MAIN_VER_LINK`: Entrega de link web (éxito y fallback).
     - `WAITING_FOR_ADMIN_MESSAGE`: Confirmación de mensaje recibido por soporte.
     - `CONFIRM_PRICE_LIST_DRAFT`: Confirmación de publicación de lista de precios.
     - `CONFIRM_PROMO_DRAFT`: Confirmación de activación y publicación de promoción.
     - `WAITING_FOR_TRANSFER_PHONE`: Entrega de código `MUDANZA-XXXX`.
     - `EDIT_IMAGENES`: Instructivo de subida y confirmación de foto actualizada.
  2. En el inicio de `procesar_mensaje`, se incorporó `btn_menu` y `main_menu` a la lista de escape universal:
     `if texto_limpio in ["menu", "menú", "volver", "inicio", "cancelar", "btn_menu", "main_menu"]:`
     Garantiza que al tocar el botón en WhatsApp se limpie cualquier sesión intermedia en SQLite y se despliegue inmediatamente el Panel de Control.
  3. En `scripts/utils/test_price_list_backend.py`, se ampliaron los tests 4E, 4F, 4G, 4H, 6B y 10I verificando la presencia del botón `btn_menu` y la reactividad universal ante su pulsación (100% PASS).
- **Razón:** En el diseño de experiencia conversacional (UX), dejar mensajes terminales sin un llamado a la acción (Call To Action) claro genera fricción y desorienta al usuario. Incorporar el botón interactivo permite regresar al menú en un solo toque en el celular sin necesidad de tipear.
- **Impacto:** Navegación ergonómica, continua y sin callejones sin salida en toda la interacción con el bot.

## [18/10/2026] — Leyendas de Salida y Cancelación en Todos los Estados de Edición
- **Decisión:**
  1. En `bot_engine.py`, se estandarizó la incorporación de la leyenda explícita de escape al final de los mensajes en los 12 estados conversacionales de solicitud de texto:
     `💡 _Si no querés cambiarlo ahora, escribí *cancelar* o *volver* para regresar al menú._`
     - Aplicado a: Título (`WAITING_FOR_TITLE`), Subtítulo (`WAITING_FOR_SUBTITLE`), Ubicación (`WAITING_FOR_LOCATION`), Horarios (`WAITING_FOR_SCHEDULE`), WhatsApp (`WAITING_FOR_WHATSAPP`), Email (`WAITING_FOR_EMAIL`), Instagram (`WAITING_FOR_INSTAGRAM`), Servicios 1, 2 y 3 (`EDIT_MENU_SERVICIOS`), Descripción de servicios (`WAITING_FOR_SERVICE_TITLE`), Búsqueda de dominio (`WAITING_FOR_DOMAIN_NAME`), Mensaje a soporte (`WAITING_FOR_ADMIN_MESSAGE`) y Transferencia de administración (`WAITING_FOR_TRANSFER_PHONE`).
  2. Al ingresar `cancelar` o `volver`, el motor intercepta la palabra universalmente, ejecuta `clear_user_state(wa_id)` descartando cambios en memoria sin tocar `website_content` en Supabase y redirige al Panel de Control principal (`MAIN_MENU`).
  3. En `scripts/utils/test_price_list_backend.py`, se incorporó el **TEST 11** validando la presencia de las leyendas de cancelación en los mensajes iniciales y verificando la inocuidad y reseteo de sesión ante `cancelar` y `volver` (100% PASS, 11/11 tests).
- **Razón:** Prevenir que usuarios que ingresan por curiosidad, error o que se arrepienten a mitad de un cambio queden forzados a ingresar un dato o crean que el bot quedó bloqueado sin salida.
- **Impacto:** Experiencia conversacional transparente, guiada y libre de trampas de entrada en todos los módulos de edición del bot.

## [18/10/2026] — Estandarización Universal del Botón Interactivo 'Volver al Menú' en Estados de Entrada y Reintento
- **Decisión:**
  1. En `bot_engine.py`, se definió el objeto canónico de botón interactivo:
     `BTN_VOLVER_MENU = [{"id": "btn_menu", "title": "📱 Volver al Menú"}]` (17 caracteres, respetando el límite $\le 20$ de Meta).
  2. Se sustituyó `send_whatsapp_message` por `send_whatsapp_buttons(wa_id, msg, BTN_VOLVER_MENU)` de forma exhaustiva en:
     - Todos los estados de edición de textos y datos generales (Título, Subtítulo, Ubicación, Horarios, WhatsApp, Email, Instagram, Servicios 1-3, Descripción, Dominio, Soporte y Transferencia).
     - Solicitud de carga de lista de precios (`WAITING_FOR_PRICE_LIST`) y comprobante de transferencia bancaria (`WAITING_FOR_RECEIPT`).
     - Pasos 1, 2, 3, 4 y final del asistente interactivo de promociones por fecha.
     - Mensajes de validación defensiva y reintento (dominio ocupado, porcentaje fuera de rango, fecha no interpretable, texto de precios sin estructura y teléfono inválido).
  3. Los usuarios en celular pueden indistintamente tipear texto libre (guardando el cambio) o tocar el botón verde `[ 📱 Volver al Menú ]` para abortar la operación en 1 solo clic sin tipear nada.
  4. En `scripts/utils/test_price_list_backend.py`, se ampliaron los tests 4, 7, 10 y el Test 11 (11A a 11H) auditando la presencia del botón y el reseteo limpio ante `btn_menu`.
  5. Se actualizaron los mocks de las suites auxiliares `test_day27_flow.py` y `test_paused_flow.py` para capturar tanto mensajes directos como botones interactivos (100% PASS en las 4 suites del sistema).
- **Razón:** Reducir la fricción en celulares a un solo toque físico, permitiendo a los comerciantes cancelar o volver sin la carga cognitiva ni motriz de abrir el teclado para escribir "cancelar".
- **Impacto:** Ergonomía móvil superior y consistencia absoluta en todo el árbol conversacional de TuWebLista.

## [18/10/2026] — Implementación de Promociones por Cantidad de Zonas (Combos) y Regla de Acumulación
- **Decisión:**
  1. En `bot_engine.py`, se implementó la FSM interactiva para la creación y gestión de **Promociones por Cantidad de Zonas (Combos)**:
     - Opción `PROMO_ZONAS_START` ("🎯 Promo por Zonas") en el submenú de precios (`mostrar_menu_precios`), manteniendo la lista WhatsApp $\le 6$ filas.
     - `WAITING_FOR_PROMO_ZONAS_DISCOUNT_1`: Ingreso y validación de porcentaje entero $[1, 99]$ para 2 zonas con botón de escape `btn_menu`.
     - `WAITING_FOR_PROMO_ZONAS_TIER2_CHOICE`: Selección interactiva de segundo tramo para 3+ zonas con botones $\le 20$ chars (`btn_zonas_t2_si`, `btn_zonas_t2_no`).
     - `WAITING_FOR_PROMO_ZONAS_DISCOUNT_2`: Validación de porcentaje estrictamente mayor al tramo 1 y $\le 99$.
     - `WAITING_FOR_PROMO_ZONAS_ACUMULABLE`: Pregunta con botones interactivos (`btn_acum_si`, `btn_acum_no`) si la promo por zonas es acumulable con la promo por fecha (reserva anticipada/jornadas).
     - Generación de borrador con token seguro de 8 chars en `price_drafts` (SQLite WAL) y vista previa (`/precios?preview=TOKEN`).
     - En `CONFIRM_PROMO_ZONAS_DRAFT`: confirmación persistiendo en Supabase `website_content.content["lista_precios"]["promocion_zonas"]` e incrementando versión; o descarte limpio.
     - Detención selectiva (`detener_promocion_activa` / `WAITING_FOR_STOP_PROMO_CHOICE`): si ambas promos están activas, ofrece 3 botones (`[ 📅 Frenar Fecha ]`, `[ 🎯 Frenar Zonas ]`, `[ 🛑 Frenar Ambas ]`); si solo una está activa, la detiene directamente.
  2. En `templates/client_template.html`, se implementó la visualización y reactividad en el frontend:
     - Contenedor `#promo-zonas-container` con píldoras interactivas (`.promo-zone-pill`) que destacan las escalas de cantidad y badge explicativo de acumulación.
     - En el Carrito Flotante (`#price-multi-bar` z-[150]): recálculo dinámico en tiempo real según la cantidad de zonas tildadas (`selectedServices.size`), aplicando la regla de combinación (acumulable: suma de porcentajes; no acumulable: mayor beneficio), recalculando sobre los precios base y actualizando el badge y total en vivo.
     - Generador de mensaje de WhatsApp: desglose detallado de tratamientos, bonificaciones aplicadas y total final.
  3. En `scripts/utils/test_price_list_backend.py`, se implementó el **TEST 12** cubriendo todo el ciclo FSM del bot (100% PASS).
  4. En `scripts/utils/test_price_list_frontend.py`, se implementó el **TEST 8** cubriendo el renderizado del banner, badges, cálculo JS y mensaje de WhatsApp (100% PASS).
  5. Cero regresiones en `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Permitir a los negocios de estética, depilación, belleza y servicios armar promociones por combos de zonas/servicios directamente desde WhatsApp, aumentando el ticket promedio de compra con una experiencia táctil intuitiva y transparente tanto para el comerciante como para el cliente final.
- **Impacto:** Motor comercial completo en la lista de precios con soporte para promociones de calendario (fecha), promociones por volumen (zonas) y reglas matemáticas de combinación sin fricciones.

## [18/10/2026] — Actualización Reactiva de Precios en Filas y Tarjetas de Zonas Seleccionadas
- **Decisión:**
  1. En `templates/client_template.html`, se implementó la función reactiva `updateRowsAndCardsPrices()` vinculada al ciclo de vida del carrito multi-servicio (`updateStickyBar()`):
     - **Servicios seleccionados (`selectedServices.has(sName)`):** Cuando se activa un descuento efectivo (`effectiveDiscount > 0`, ya sea por promo fecha, combo de zonas o combinación acumulable), las celdas de precio de la tabla desktop (`.desktop-price-cell`) y el valor de las tarjetas móviles (`.price-value`) actualizan su contenido en tiempo real mostrando el precio base regular tachado (`line-through`), el nuevo precio bonificado en negrita esmeralda (`text-emerald-600 font-extrabold`) y el badge actualizado `-${effectiveDiscount}% OFF`.
     - **Servicios no seleccionados (`!selectedServices.has(sName)`):** Mantienen el precio base con el descuento de fecha (`activeDiscount`) si la jornada está activa, o el precio de lista regular sin tachados si no hay promo fecha.
     - **Limpieza / Deselección:** Al desmarcar los checkboxes o presionar "Limpiar" (`multiClearBtn`), todas las filas y tarjetas retornan instantáneamente a su estado de reposo base.
     - **Sincronización táctil mobile:** Se sincronizó `updateMobileCardPrice()` para evaluar si la tarjeta pertenece a un servicio seleccionado al conmutar entre pestañas de modalidades de pago (`currentMobileCol`).
  2. En `scripts/utils/test_price_list_frontend.py`, se ampliaron las aserciones de `[TEST 8]` auditando la reactividad visual en celdas y tarjetas ante la selección de zonas bajo `effectiveDiscount` (100% PASS, Tests 1 al 8).
  3. Cero regresiones en `test_price_list_backend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Proporcionar al cliente final retroalimentación visual inmediata en la misma lista: al tildar la segunda o tercera zona ve cómo los precios de las zonas que acaba de elegir bajan al instante en la pantalla, maximizando la percepción de ahorro y la conversión a pedidos por WhatsApp.
- **Impacto:** Experiencia de usuario (UX) de nivel e-commerce moderno en la lista interactiva de servicios.

## [19/10/2026] — Optimización Responsive Mobile: Desacoplamiento de Tarjetas y Carrito Flotante Mobile-First
- **Decisión:**
  1. En `templates/client_template.html`, se corrigió el solapamiento visual en las tarjetas de servicios móviles (`.price-item-card`):
     - Se reubicó la etiqueta de método de pago (`.price-method-badge`) en la cabecera de la tarjeta junto al título del servicio (`<h4>`), contenida en un contenedor flexible con wrap (`<div class="flex items-center gap-1.5 flex-wrap">`).
     - Se desacopló el bloque de precios (`.price-value`) en su propio contenedor `<div class="mt-1">`. De esta manera, el precio regular tachado, el precio final bonificado y el badge `-${effectiveDiscount}% OFF` disponen de todo el ancho horizontal sin competir con la etiqueta de pago ni solaparse detrás del botón verde de WhatsApp.
     - En `.mobile-wa-btn`, se aseguró `shrink-0`, padding adaptable `px-3 py-2 sm:px-3.5 sm:py-2.5` y `<span class="whitespace-nowrap">` para evitar rupturas de layout en pantallas angostas.
  2. En `templates/client_template.html`, se reestructuró la barra flotante inferior del carrito (`#price-multi-bar`):
     - **Layout Responsivo Mobile-First:** Se configuró como columna en mobile y fila en desktop (`flex flex-col md:flex-row md:items-center md:justify-between gap-3 md:gap-4`).
     - **Fila Superior (Mobile):** Muestra el contador del carrito (`🛒 Carrito: X tratamientos`) a la izquierda y el botón de acción rápida `#multi-clear-btn-mobile` a la derecha.
     - **Fila Intermedia (`#multi-totals-summary`):** Formateo estructurado con total en grande y la leyenda de descuento (`discountExplanation`) renderizada como una pastilla destacada (`bg-amber-400/10 text-amber-300 border border-amber-400/20 px-2 py-0.5 rounded-md text-[11px] font-bold`), evitando el quiebre de texto en 8 líneas verticales.
     - **Fila Inferior / CTA Principal (Mobile):** El botón de WhatsApp (`#multi-wa-btn`) se expande al 100% del ancho en móviles (`w-full md:w-auto`) para una interacción táctil natural con el pulgar.
     - **En Desktop (`md:`):** Se preserva la barra horizontal compacta con `#multi-clear-btn` visible junto al CTA.
     - **JavaScript Unificado:** La función `clearSelection` quedó vinculada tanto al botón `#multi-clear-btn` (desktop) como a `#multi-clear-btn-mobile` (mobile).
  3. En `scripts/utils/test_price_list_frontend.py`, se ampliaron las aserciones de `[TEST 6]` auditando la presencia de `#multi-clear-btn-mobile` y las clases responsive `flex flex-col md:flex-row` (100% PASS, Tests 1 al 8).
  4. Cero regresiones en `test_price_list_backend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Resolver problemas de maquetado en teléfonos móviles donde las palabras de los métodos de pago quedaban ocultas detrás de los botones de presupuesto y el carrito flotante se deformaba en una caja vertical desproporcionada.
- **Impacto:** Experiencia de usuario (UX) móvil limpia, ergonómica y profesional tanto en pantallas angostas (360px - 390px) como en tablets y computadoras de escritorio.

## [20/10/2026] — Exención del Límite de 3 Páginas Web para el Administrador (Prospección Outbound)
- **Decisión:**
  1. En `app.py`, se configuró la variable de entorno `ADMIN_PHONE = os.getenv("ADMIN_PHONE", "5491134710787")`.
  2. En la ruta `POST /process_form`, se implementó la normalización telefónica defensiva comparando los últimos 10 dígitos del número remitente contra el teléfono del administrador (`is_admin_phone`).
  3. Si la solicitud proviene del teléfono administrador, se omite el límite de 3 páginas web por número de teléfono, permitiendo crear páginas demo ilimitadas para prospección comercial directa hacia comercios y profesionales.
  4. Los usuarios regulares y números no administrativos continúan sujetos a la regla de seguridad de máximo 3 páginas por teléfono.
  5. Cero regresiones en `test_price_list_backend.py`, `test_price_list_frontend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Habilitar la estrategia de prospección comercial outbound ("Demo Servida en Bandeja"), permitiendo al administrador armar demos personalizadas para comercios contactados por Google Maps o redes sin toparse con el bloqueo de cupo.
- **Impacto:** Capacidad operativa de prospección a gran escala para captación de clientes de forma proactiva.

## [20/10/2026] — Implementación del Motor de Ajuste de Precios y Promociones por Producto (Fase 1: Backend & Bot FSM)
- **Decisión:**
  1. En `bot_engine.py`, se implementó la FSM y el motor conversacional interactivo para el ajuste de precios y promociones por ítem:
     - Opción `PRECIOS_AJUSTAR` ("✏️ Ajustar Precios/Promos") en el submenú de precios (`mostrar_menu_precios`).
     - `WAITING_FOR_ADJUST_SELECTION`: Muestra la lista numerada de servicios con precios actuales y badges (`🏷️ X% OFF`), permitiendo seleccionar `1`, varios (`1, 3` o `1 y 3`) o `todos`.
     - `WAITING_FOR_ADJUST_TYPE_ALL`: Selección guiada por botones interactivos (`[ 📈 Aumentar Precios ]` y `[ 📉 Bajar Precios ]`) para evitar que el usuario deba escribir signos en el teclado del celular.
     - `WAITING_FOR_ADJUST_PERCENT_VALUE`: Ingreso simple de porcentaje entero ($1$ a $99$) con validación defensiva.
     - `WAITING_FOR_SINGLE_PRODUCT_ACTION`: Botones contextuales (`[ 💰 Precio Exacto ]`, `[ 🏷️ Poner en Promo ]`, `[ ⏹️ Quitar Promo ]` / `[ 📈 Aumentar por % ]`).
     - `WAITING_FOR_EXACT_PRICE_VALUE`: Ingreso de monto exacto para un producto con actualización proporcional de columnas alternativas.
     - `WAITING_FOR_PROD_PROMO_PERCENT`: Asignación de descuento individual o múltiple (`"descuento": X` en el ítem de `lista_precios.items`).
     - `WAITING_FOR_MULTI_PRODUCT_ACTION`: Acciones sobre múltiples productos (`[ 🏷️ Poner en Promo ]`, `[ 📈 Ajustar por % ]`, `[ ⏹️ Quitar Promos ]`).
     - `CONFIRM_PRICE_ADJUST_DRAFT`: Generación de vista previa en `price_drafts` con token de 8 caracteres hex (`/precios?preview=TOKEN`), confirmación con botón `[ ✅ Publicar Precios ]` o descarte limpio con `[ ❌ Cancelar ]`.
     - Protección anti-confusión en `WAITING_FOR_PRICE_LIST`: Intercepta frases de intención de ajuste (*"aumentar"*, *"cambiar precios"*, *"subir precios"*, *"descuentos"*) antes del parser de IA, ofreciendo botones guiados (`[ ✏️ Ajustar Precios ]` y `[ 📱 Menú Principal ]`).
     - `round_clean_price()`: Redondeo prolijo a múltiplos de \$100 ($\ge \$5.000$) o \$50 ($<\$5.000$).
  2. En `scripts/utils/test_price_list_backend.py`, se implementó el bloque `[TEST 13]` con cobertura integral de todos los flujos de ajuste, asignación y quita de promos, anti-confusión y reseteos (100% PASS).
  3. Cero regresiones en `test_price_list_frontend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Permitir a los comerciantes gestionar la inflación (aumentos masivos o individuales) y armar promociones selectivas por producto directamente desde WhatsApp con máxima ergonomía móvil (sin signos `+`, `-` ni `%`), evitando que tengan que rehacer sus planillas Excel.
- **Impacto:** Herramienta comercial y operativa indispensable para comerciantes en Argentina, reduciendo la fricción de actualización de precios a segundos.

## [20/10/2026] — Implementación del Renderizado Visual de Promociones por Producto en la Web de Clientes (Fase 2: Frontend)
- **Decisión:**
  1. En `templates/client_template.html`, se implementó la inyección tolerante a nulos de atributos de datos `data-item-discount="{{ item.descuento or 0 }}"` en:
     - Tabla desktop: filas (`.price-table-row`), checkboxes (`.price-item-checkbox`) y botones individuales de WhatsApp (`.desktop-wa-btn`).
     - Tarjetas mobile: contenedor (`.price-item-card`), checkboxes móviles (`.price-item-checkbox-mobile`) y botones de WhatsApp (`.mobile-wa-btn`).
  2. En JavaScript vanilla de `client_template.html`:
     - **Renderizado Dinámico y Conmutación de Pestañas Mobile:** `updateMobileCardPrice(card, colName)` calcula en tiempo real el descuento efectivo `finalDisc` considerando si el ítem está seleccionado, si aplica combo de zonas acumulable o mayor beneficio contra `activeDiscount`, inyectando el precio regular tachado (`line-through text-gray-400 font-normal mr-1.5`), el precio promocional en verde (`font-bold text-emerald-600`) y el badge `-${finalDisc}% OFF` (`bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded text-xs font-semibold`). Al conmutar pestañas de pago (Efectivo, Transferencia, Tarjeta), el cálculo y layout se actualizan reactivamente sin saltos.
     - **Tabla Desktop:** `updateRowsAndCardsPrices(effectiveDiscount)` actualiza celdas desktop con precios tachados, precios destacados y badges de descuento individual cuando corresponda.
     - **Carrito Flotante (#price-multi-bar):** `updateStickyBar()` evalúa los descuentos individuales por producto para sumar con exactitud los totales finales por columna de pago (`finalTotalsByCol`) aun cuando no exista ninguna promoción global activa (`effectiveDiscount === 0`).
     - **Inicialización:** `applyRealtimeDiscounts()` ejecuta el renderizado visual inicial de productos con descuento al cargar la página.
  3. En `scripts/utils/test_price_list_frontend.py`, se incorporó el bloque `[TEST 9]` validando atributos Jinja, renderizado condicional de precios tachados, badges `OFF`, reactividad móvil, cálculo de carrito con descuentos individuales y retrocompatibilidad con ítems sin descuento (100% PASS).
  4. Cero regresiones en `test_price_list_backend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Reflejar inmediatamente en la experiencia web del cliente final las promociones configuradas por el comerciante desde WhatsApp, asegurando un diseño atractivo, consistente y con total claridad en los precios tachados y bonificados tanto en celulares como en computadoras.
- **Impacto:** Conversión incrementada en webs de clientes gracias a ofertas y descuentos visuales transparentes y calculados al centavo en el carrito y pedidos de WhatsApp.

## [20/10/2026] — Implementación del Modo Super-Admin Multisitio, Acuse SLA 24hs y Notificaciones Automáticas a Clientes
- **Decisión:**
  1. En `bot_engine.py`, se implementó la lógica de seguridad y detección del Super-Admin (`is_admin_phone`) comparando los últimos 10 dígitos del teléfono contra `ADMIN_PHONE` (`5491134710787`).
  2. **Conmutación de Contexto Multisitio para el Administrador:**
     - Comandos `web <slug>` o `slug <slug>`: buscan la web en Supabase por `subdomain` o `seo_title` y fijan `admin_active_web_id` en `user_sessions.temp_data` en SQLite (WAL).
     - Comandos `mis webs`, `admin webs` y `buscar <texto>`: despliegan listas interactivas de WhatsApp ($\le 10$ filas, títulos $\le 24$ chars, descripciones $\le 72$ chars) permitiendo seleccionar y cambiar de sitio web con un solo toque.
     - Comandos `web actual` (muestra la web activa) y `web salir` (limpia el contexto).
     - Se adaptó `obtener_web_del_cliente(phone)` para que, si quien consulta es `ADMIN_PHONE`, enrute automáticamente a la web fijada en `admin_active_web_id` con todos los datos del cliente titular (`client_name`, `client_phone`, `client_id`).
  3. **Despacho Automático de Avisos al Cliente Titular:**
     - Se creó el helper `notificar_cliente_cambio_publicado(wa_id_editor, web_info, descripcion_cambio)`.
     - Cuando el administrador confirma y publica un cambio en una web ajena (asignación de imágenes en `WAITING_FOR_IMAGE_ROLE`, publicación de lista de precios en `CONFIRM_PRICE_LIST_DRAFT` o ajustes de precios/promociones en `CONFIRM_PRICE_ADJUST_DRAFT`), el bot envía automáticamente un WhatsApp al cliente titular con el enlace directo a su web.
  4. **Receptor de Solicitudes Outbound con SLA (24 hs hábiles):**
     - En `IDLE`, si un cliente regular envía una imagen o texto solicitando cambios, el bot le responde con un acuse de recibo cordial indicando el plazo de hasta 24 hs hábiles (Lunes a Viernes).
     - Simultáneamente, despacha una alerta a `ADMIN_PHONE` con el detalle del pedido y el comando sugerido `web <slug>` para tomar el control inmediato.
  5. En `scripts/utils/test_price_list_backend.py`, se implementó la sección `[TEST 14]` cubriendo la detección de admin, conmutación de contexto, aislamiento de clientes regulares, acuse de recibo con SLA y despacho automático de notificaciones a clientes (100% PASS).
  6. Cero regresiones en `test_price_list_frontend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Habilitar el modelo comercial Outbound ("Demo Servida en Bandeja" y servicio "Llave en Mano" / Concierge), permitiendo al administrador editar y gestionar decenas de páginas web de clientes desde su celular en segundos, automatizando el aviso de entrega al cliente y estableciendo expectativas claras de servicio (SLA).
- **Impacto:** Operación "manos libres" para el administrador y percepción de servicio VIP para los comerciantes sin fricción tecnológica.

## [21/10/2026] — Generación Masiva de Demos desde CSV con Lista de Precios IA y Banner Explicativo
- **Decisión:**
  1. En `app.py`, se actualizó `generar_plantilla_dinamica()` para que el modelo canónico de IA (`gemini-flash-lite-latest`) genere una `lista_precios` adaptada al rubro del comercio, con 3 columnas de pago estándar en pesos argentinos (`Efectivo`, `Transferencia`, `Tarjeta`) y descuentos promocionales de ejemplo. Asimismo, se robusteció `plantilla_base` con un fallback determinista para garantizar que ninguna demo carezca de catálogo interactivo.
  2. En `templates/client_template.html`, se incorporó un banner superior explicativo condicionado a `web_status == 'demo'` (`z-[160]`), informando que la web es 100% personalizable y que puede utilizarse con el subdominio gratuito incluido o con dominio propio `.com.ar` (con el trámite de registro a cargo de TuWebLista) por el mismo abono mensual de \$2.000. El banner se oculta automáticamente cuando el sitio pasa a estado `published`.
  3. Se creó el script operativo `scripts/ops/generate_demos_from_csv.py` con interfaz CLI para procesar archivos CSV provenientes del scraper de Google Maps (`/admin/maps_scraper`), mapear encabezados heterogéneos (`nombre`, `telefono`, `direccion`, `rubro`), normalizar teléfonos, generar slugs limpios, persistir en Supabase con `status="demo"` y exportar el CSV enriquecido con `slug` y `link_demo` bajo codificación `utf-8-sig` (compatible nativamente con Microsoft Excel).
  4. Se creó la suite de prueba integral `scripts/utils/test_bulk_demo_generator.py` (Tests 1 al 5) certificando el contrato JSON, fallback, renderizado del banner y ejecución end-to-end con 100% PASS.
  5. Cero regresiones en `test_price_list_backend.py`, `test_price_list_frontend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Potenciar el impacto visual y la tasa de conversión en la prospección Outbound ("Demo Servida en Bandeja"), mostrando una web completa y viva con catálogo y modalidades de pago desde el primer segundo, eliminando el temor a la complejidad técnica y automatizando la generación de decenas de páginas sin intervención manual.
- **Impacto:** Capacidad de procesar y generar 50 demos personalizadas en minutos a costo marginal cero, listas para ser despachadas por WhatsApp.

## [21/10/2026] — Motor de Despacho Outbound, Respuestas FSM y Gestión de Opt-Out
- **Decisión:**
  1. En `sender.py`, se implementó `send_whatsapp_template()` para despachar plantillas oficiales de Meta WhatsApp Cloud API (`type: "template"`) con estructura de componentes y parámetros posicionales (`{{1}}`, `{{2}}`, etc.).
  2. En `receiver.py`, se implementó la extracción defensiva en `button_reply` (`b_reply.get('id') or b_reply.get('title', '')`), permitiendo procesar tanto botones interactivos clásicos como botones de respuesta rápida de plantillas de Meta.
  3. En `bot_engine.py`:
     - Se creó la tabla SQLite `opt_outs` (`phone TEXT PRIMARY KEY, created_at TIMESTAMP`) bajo modo WAL.
     - Se interceptó la respuesta `[ ❌ No me interesa ]`: despacha mensaje de despedida cordial y persiste el número en `opt_outs` para evitar futuros envíos salientes.
     - Se interceptó la respuesta `[ 🚀 Sí, me interesa ]`: despacha la guía conversacional amigable en 4 opciones (precios, fotos, dominio propio o activar por \$2.000) y alerta de inmediato al Super-Admin (`ADMIN_PHONE`) con el comando `web <slug>`.
     - En la consulta de dominio propio (`WAITING_FOR_DOMAIN_NAME`), se implementó la normalización sin obligar a escribir `.com.ar`, la inclusión del enlace oficial de aranceles `https://nic.ar/aranceles` (\$8.500 anuales de NIC.ar) y la advertencia clara de 48 hs para la delegación de DNS.
  4. Se creó el script `scripts/ops/send_outbound_campaign.py` con interfaz CLI (`--input`, `--limit`, `--delay`, `--dry-run`), exclusión de teléfonos en `opt_outs`, prevención de duplicación (`enviado_fecha`) y pacing temporal de 10-15 segundos.
  5. Se creó la suite automatizada `scripts/utils/test_outbound_campaign.py` (Tests 1 al 5) y se certificó 100% PASS en las 6 suites del proyecto sin regresiones.
- **Razón:** Cerrar el circuito tecnológico y operativo para la prospección masiva por WhatsApp oficial de Meta, garantizando una experiencia de usuario fluida, protegiendo la reputación del número ante spam mediante opt-outs y alertando al administrador en tiempo real ante prospectos calificados.
- **Impacto:** Canal Outbound 100% operativo y seguro, listo para ejecutar campañas masivas con alta tasa de respuesta y conversión.

## [21/10/2026] — Filtro Inteligente de Sitios Web en Google Maps Scraper para Prospección Outbound
- **Decisión:**
  1. En `app.py`, en el endpoint `POST /admin/maps_scraper`, se implementó la discriminación de prospectos calificados:
     - Se añadió el campo `website` al llamado a la Google Places Details API (`fields=name,formatted_phone_number,formatted_address,website`).
     - Se captura el parámetro booleano `solo_sin_web` mediante `request.form.getlist('solo_sin_web')` para procesar correctamente listas múltiples generadas por el fallback `<input type="hidden">` del formulario HTML (resolviendo `['false', 'true']` -> `True`, `['false']` -> `False` y llamadas directas/API -> `True` por defecto).
     - Si el comercio no posee sitio web (`""` o whitespace), se clasifica como `"Sin web"` y se incluye en la prospección.
     - Si el comercio tiene enlaces a redes sociales (`SOCIAL_DOMAINS`: instagram, facebook, fb.com, fb.me, linktr.ee, tiktok, wa.me, whatsapp.com), se clasifica como `"Redes (<url>)"` y se incluye en la prospección.
     - Si el comercio cuenta con sitio web propio comercial, se descarta cuando `solo_sin_web=True` (comportamiento por defecto) o se conserva registrando la URL cuando `solo_sin_web=False`.
     - El archivo CSV exportado incorpora la cuarta columna `Sitio Web Detectado`, preservando inalteradas las primeras 3 columnas (`Nombre del Local`, `Teléfono`, `Dirección`) para garantizar total retrocompatibilidad con los scripts `generate_demos_from_csv.py` y `send_outbound_campaign.py`.
  2. En `templates/admin_dashboard.html`, en el formulario `#form-maps-scraper`:
     - Se incorporó un control interactivo con checkbox estilizado en Tailwind CSS (`solo_sin_web`), marcado por defecto (`checked`), acompañado de `<label>` accesible en español rioplatense (*"Solo comercios sin web (o que solo tienen redes sociales)"*).
     - Se incluyó un input oculto fallback `<input type="hidden" name="solo_sin_web" value="false">` para garantizar el envío determinista del valor booleano en peticiones estándar multipart/form-data.
  3. En `scripts/utils/test_maps_scraper_filter.py`, se implementó una suite de pruebas automatizadas con mocks de Google Places API (Text Search y Details), validando descarte de webs propias, retención de redes y sin web, inclusión con filtro inactivo, y estructura de encabezados UTF-8 (100% PASS).
  4. Cero regresiones en `test_outbound_campaign.py`, `test_bulk_demo_generator.py`, `test_price_list_backend.py`, `test_price_list_frontend.py`, `test_day27_flow.py` y `test_paused_flow.py`.
- **Razón:** Maximizar la tasa de conversión y el retorno de inversión en las campañas de prospección saliente ("Demo Servida en Bandeja"), asegurando que el esfuerzo comercial y los mensajes de WhatsApp se dirijan exclusivamente a comerciantes que realmente carecen de una web profesional o que solo dependen de perfiles en redes sociales.
- **Impacto:** Embudo comercial altamente enfocado, cero desperdicio de créditos de mensajería y generación automática de listas de leads de alta intención.

## [21/10/2026] — Optimización de Webs Demo Outbound: Geolocalización Exacta, Promociones Activas Didácticas, Variedad de Fotos y Contacto Humanizado
- **Decisión:**
  1. En `app.py` y `bot_engine.py`:
     - Se corrigió `obtener_coordenadas()`: se eliminó el falso positivo `if "argentina" in ubicacion_texto.lower()` reemplazándolo por `ubicacion_texto.strip().lower() == "argentina"`. Se incorporó sanitización automática para remover códigos postales argentinos (`C1419...`) y simplificar CABA a "Buenos Aires" antes de consultar Nominatim, evitando que direcciones reales colapsen a las coordenadas del centro del país.
     - En `buscar_foto_unsplash()`, se implementó aleatorización real en la selección de imágenes (`page = random.randint(1, 3)`, `per_page=15` y `random.shuffle`) junto con términos complementarios del rubro para garantizar que comercios similares no reciban las mismas fotos.
     - En `generar_plantilla_dinamica()` (IA y fallback), se inyectaron promociones de ejemplo activas:
       - `promocion_fecha`: Descuento del 15% con vigencia calculada dinámicamente a 30 días.
       - `promocion_zonas`: Combos de 2 zonas/servicios (10% OFF) y 3 zonas/servicios (15% OFF).
  2. En `scripts/ops/generate_demos_from_csv.py`:
     - Se amplió `normalizar_telefono()` para admitir prefijos locales argentinos con código de área y móvil (`011 15-XXXX-XXXX` de 13 dígitos y `11 15-XXXX-XXXX` de 12 dígitos) normalizándolos correctamente a `54911XXXXXXXX`.
  3. En `templates/client_template.html`:
     - **Iframe de Google Maps:** Utiliza prioritariamente `web_content.ubicacion_detectada` codificada en `q` a zoom 16, logrando que el mapa muestre con total exactitud la calle y altura del local.
     - **Email de Contacto:** Se reemplazó el fallback `contacto@tuweblista.com.ar` por `tumail@gmail.com` para resguardar la identidad de la plataforma en sitios de prospectos.
     - **Microcopia Humanizada:** Se reemplazó la frase "chateando con el bot" por "por WhatsApp" en el footer.
     - **Notas Didácticas de Promociones:** En los banners de promociones por fecha y combos de zonas, cuando `web_status == 'demo'`, se añadió la nota: *"Promoción de ejemplo activa. Podés activar, pausar o cambiar descuentos en segundos con un simple mensaje de WhatsApp."*
- **Razón:** Maximizar el impacto persuasivo y la credibilidad en la entrega de demos personalizadas para la prospección Outbound ("Demo Servida en Bandeja"), mostrando un mapa perfecto en la puerta del negocio, fotos variadas, promociones listas para usar y una comunicación humana y transparente.
- **Impacto:** Experiencia de usuario impecable, eliminación de fricciones y tasa de respuesta sustancialmente superior en la prospección por WhatsApp.

## [21/10/2026] — Motor de Barrido Masivo en Google Maps (Bulk Maps Scraper) y Control en Panel Admin
- **Decisión:**
  1. Se creó el Catálogo Geográfico Jerárquico de Argentina (`scripts/utils/arg_geo_catalog.py`), estructurando más de 250 nodos de prospección:
     - CABA: Los 48 barrios oficiales.
     - Gran Buenos Aires (AMBA): Los 35 partidos y municipios del conurbano.
     - Provincias de Santa Fe y Córdoba: Grandes urbes divididas por macro-barrios (Rosario, Santa Fe Capital, Córdoba Capital) y ciudades cabeceras del interior (Rafaela, Venado Tuerto, Río Cuarto, Villa María, Carlos Paz, etc.).
     - Mendoza, Tucumán, Buenos Aires Interior y resto de capitales y ciudades de las 23 provincias del país.
     - Macro-zona `TODA_ARGENTINA` consolidada para barridos federales completos.
  2. Se desarrolló el Motor de Barrido en Segundo Plano (`scripts/ops/bulk_maps_scraper.py`):
     - Ejecución multi-hilo (`threading.Thread`) que no bloquea a Gunicorn ni depende del timeout web (120s).
     - Deduplicación en tiempo real por número de teléfono normalizado entre zonas limítrofes.
     - Freno de seguridad configurable (`max_comercios` / Stop Loss) para contención estricta de costos de la API de Google Maps Platform.
     - Estimador en tiempo real de consumo en USD considerando el crédito gratuito mensual de $200 USD.
     - Escritura y persistencia progresiva en tiempo real en la carpeta `leads/prospectos_{rubro}_{zona}.csv`.
     - Sistema de checkpointing / reanudación (`--resume` / `.scraper_state.json`) para continuar sin repetir zonas ya consultadas.
     - Bandera de detención limpia (`stop_requested`) para pausar o frenar a demanda.
  3. En `app.py`, se implementaron las rutas de control bajo sesión administrativa:
     - `GET /admin/bulk_scraper/presets`: Listado dinámico de zonas disponibles.
     - `POST /admin/bulk_scraper/start`: Inicio de tarea asíncrona (409 ante tareas en curso).
     - `GET /admin/bulk_scraper/status`: Telemetría en vivo del barrido (zona actual, leads, saldo consumido, porcentaje, estado).
     - `POST /admin/bulk_scraper/stop`: Detención controlada con guardado progresivo.
     - `GET /admin/bulk_scraper/download/<filename>`: Descarga segura con `secure_filename()` desde la carpeta `leads/`.
  4. En `templates/admin_dashboard.html`, se diseñó la tarjeta interactiva:
     - Formulario con rubro, selector jerárquico de zonas, límite de seguridad y filtro web.
     - Widget de progreso en vivo con barra animada, grid de 4 métricas en tiempo real, botón para detener y botón verde de descarga al finalizar.
     - Lógica JavaScript vanilla con polling cada 2s y auto-restauración de estado en `DOMContentLoaded`.
  5. Se creó la suite automatizada `scripts/utils/test_bulk_maps_scraper.py` (Tests 1 al 4) y se certificó 100% PASS en las 8 suites del proyecto sin ninguna regresión.
  6. Se aisló `leads/*.csv` en `.gitignore` para proteger los datos de contacto y se actualizó `safe_deploy.py` para sincronizar `arg_geo_catalog.py`.
- **Razón:** Eliminar por completo el esfuerzo manual de búsqueda barrio por barrio, permitiendo prospectar miles de comercios calificados a nivel nacional o provincial directamente desde el panel de control, con visualización en tiempo real, seguridad financiera total y cero riesgo de sobrecostos.
- **Impacto:** Capacidad de extracción masiva de leads en un solo clic, automatización de punta a punta del embudo comercial y autonomía operativa 100% desde la web.

## [21/10/2026] — Armonización de Contrato de Telemetría y Blindaje de Alias en Bulk Maps Scraper
- **Decisión:**
  1. En `scripts/utils/arg_geo_catalog.py`, se blindó la función `obtener_zonas_por_clave()` incorporando un diccionario expandido de alias (`"toda_argentina"`, `"nacional"`, `"pais"`, `"argentina_completa"` hacia `"argentina"`; `"bsas_interior"`, `"buenos_aires_provincia"` hacia `"buenos_aires_interior"`). Con esto, cualquier valor que ingrese desde el selector o desde llamados manuales resuelve a la totalidad de las ~250 zonas del país.
  2. En `scripts/ops/bulk_maps_scraper.py`, se enriqueció `BulkMapsScraper.get_status()` para entregar un payload bilingüe dual y redundante (`leads_count` y `comercios_encontrados`, `total_zones` y `total_zonas`, `zone_index` e `indice_zona`, `current_zone` y `zona_actual`, `estimated_cost` y `consumo_usd`, `filename`, `csv_filename`, `download_url` y `progress_percent`).
  3. En `templates/admin_dashboard.html`, se actualizaron las opciones del `<select id="bulk_zona">` a los identificadores canónicos (`argentina`, `buenos_aires_interior`) y se reforzó la función `updateUIWithStatus()` mediante operadores de coalescencia nula (`??`) y formateo estricto de costos a dos decimales con `(crédito gratuito)`.
  4. En `scripts/utils/test_bulk_maps_scraper.py`, se añadieron aserciones específicas para certificar la resolución de aliases y la presencia de todas las claves contractuales en el snapshot de estado.
- **Razón:** Tras el primer barrido de prueba en producción, la divergencia de claves entre el selector (`toda_argentina`) y el catálogo (`argentina`) provocó una búsqueda de zona única que devolvió 13 comercios pero mostró contadores en 0 en el frontend debido al desacople de nombres de propiedades JSON.
- **Impacto:** Conexión y telemetría en tiempo real 100% blindada, visualización en vivo de prospectos, porcentaje y consumo exacto en el panel de administración, y barrido efectivo a lo largo de las más de 250 zonas argentinas.

## [21/10/2026] — Normalización ASCII de Slugs y Adaptación de Descarga de Leads para Cloudflare WAF
- **Decisión:**
  1. En `scripts/ops/bulk_maps_scraper.py`, se refactorizó la función `slugify()` para incorporar `unicodedata.normalize('NFKD', ...)` y conversión forzada a ASCII puro (`ascii.ignore`). De este modo, términos con diacríticos o tildes (como `"Depilación láser"`) se convierten de forma determinista a nombres limpios y seguros (`"depilacion_laser"`), eliminando discrepancias con `secure_filename()` en el servidor.
  2. En `app.py`, se rediseñó el endpoint de descarga `bulk_scraper_download()` para aceptar parámetros vía query string (`/admin/bulk_scraper/download?file=...` o `?filename=...`), manteniendo compatibilidad con la ruta directa. Además, se implementó una estrategia de resolución tolerante: si el archivo sanitizado no existe de forma exacta, busca coincidencias directas con el nombre solicitado en la carpeta `leads/` para rescatar archivos generados previamente con tildes.
  3. En `templates/admin_dashboard.html`, se adaptó la construcción de la URL de descarga para emitir `/admin/bulk_scraper/download?file=...`, evitando segmentos con extensiones `.csv` en la ruta de acceso (URI Path) que activen las reglas de seguridad o inspección profunda de Cloudflare WAF. Asimismo, se reemplazó `target="_blank"` por el atributo HTML5 `download` con el nombre sugerido del archivo.
  4. En `scripts/utils/test_bulk_maps_scraper.py`, se añadieron pruebas unitarias para certificar la normalización de tildes en `slugify()` y la descarga exitosa tanto por ruta directa como por query parameter.
- **Razón:** Tras un barrido masivo exitoso de 282 prospectos en los 48 barrios de CABA, al presionar "Descargar CSV de Leads", Cloudflare WAF bloqueó la petición con HTTP 403 debido a la presencia de caracteres no-ASCII (`depilación_láser`) y extensión `.csv` directa en el path de la URI.
- **Impacto:** Descarga fluida, inmediata y transparente de prospectos comerciales desde el panel de control, 100% inmune a bloqueos por WAF o proxies perimetrales.
