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
