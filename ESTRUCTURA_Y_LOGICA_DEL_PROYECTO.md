# Documento de Estructura y Lógica del Proyecto TuWebFacil

## Árbol de Directorios

```
TuWebFacil/
├── app.py                      # Aplicación principal Flask
├── competitor_analysis.py      # Análisis de competidores
├── database_schema.md          # Documentación de la estructura de la base de datos
├── index.html                  # Página principal del sistema
├── instrucciones.txt           # Instrucciones del proyecto
├── marketing_bot.py            # Bot de marketing
├── mercadopago_integration.py  # Integración con MercadoPago
├── provision_client.py         # Aprovisionamiento de clientes
├── README.md                   # Documentación general
├── receiver.py                 # Receptor de mensajes (posiblemente para WhatsApp)
├── requirements.txt            # Dependencias del proyecto
├── sender.py                   # Emisor de mensajes (posiblemente para WhatsApp)
├── SUMMARY.md                  # Resumen del proyecto
├── templates/                  # Directorio de plantillas
│   ├── client_template.html    # Plantilla para sitios web de clientes
│   └── paused.html             # Plantilla para sitios pausados
├── test_sistema.py             # Pruebas del sistema
├── utils.py                    # Utilidades generales
└── whatsapp_ux.md              # Documentación de la experiencia de usuario en WhatsApp
```

## Stack Tecnológico

### Backend
- **Flask**: Framework web ligero para Python que maneja las rutas y renderiza las plantillas.
- **Python 3.14**: Lenguaje de programación principal.
- **Supabase**: Base de datos y autenticación, utilizada para almacenar información de clientes, sitios web y contenido.

### APIs y Servicios Externos
- **Groq API**: Servicio de IA utilizado para generar contenido personalizado para los sitios web de los clientes.
- **Unsplash API**: Servicio para obtener imágenes de alta calidad basadas en consultas específicas.
- **Nominatim (OpenStreetMap)**: Servicio de geocodificación para obtener coordenadas a partir de direcciones textuales.
- **MercadoPago**: Integración para procesamiento de pagos y suscripciones.

### Frontend
- **HTML/CSS/JavaScript**: Tecnologías web estándar para la interfaz de usuario.
- **Tailwind CSS**: Framework CSS utilizado para el diseño y estilizado de las páginas.
- **Font Awesome**: Biblioteca de iconos.
- **Jinja2**: Motor de plantillas utilizado por Flask para renderizar HTML dinámico.

### Bibliotecas Python
- **requests**: Para realizar solicitudes HTTP a APIs externas.
- **python-dotenv**: Para cargar variables de entorno desde archivos .env.
- **pandas**: Para análisis de datos.
- **matplotlib**: Para visualización de datos.
- **Pillow**: Para procesamiento de imágenes.

## Lógica del Backend (app.py)

### Configuración Inicial
- Inicialización de Flask y configuración de CORS.
- Carga de variables de entorno para APIs (Groq, Unsplash, Supabase).
- Configuración de la conexión a Supabase.

### Funciones Auxiliares
1. **obtener_coordenadas(ubicacion_texto)**:
   - Utiliza la API de Nominatim para convertir texto de ubicación en coordenadas geográficas.
   - Maneja casos especiales como ubicaciones no proporcionadas o genéricas.
   - Ajusta el nivel de zoom según la especificidad de la ubicación.

2. **buscar_foto_unsplash(query)**:
   - Busca imágenes en Unsplash basadas en consultas específicas.
   - Retorna URLs de imágenes relevantes o una imagen predeterminada si falla.

3. **llamar_a_ia_directo(rubro, bio)**:
   - Envía una solicitud a la API de Groq con un prompt específico.
   - Genera contenido personalizado para el sitio web basado en el rubro y la biografía.
   - Procesa la respuesta para incluir fotos y coordenadas del mapa.

### Rutas Principales
1. **/** (Ruta raíz):
   - Sirve la página principal (index.html).

2. **/process_form** (POST):
   - Recibe datos del formulario (rubro, teléfono, bio).
   - Llama a la IA para generar contenido personalizado.
   - Crea un slug único para la URL del sitio.
   - Almacena datos en Supabase (tablas clients, websites, website_content).
   - Retorna el slug generado para redireccionar al usuario.

3. **/<client_slug>**:
   - Busca el sitio web correspondiente al slug en la base de datos.
   - Verifica si el sitio está activo o pausado.
   - Si está pausado, muestra la plantilla paused.html.
   - Si está activo, obtiene el contenido y datos del cliente y renderiza client_template.html.

### Puntos Críticos en el Backend
- **Generación de Slugs**: Combina el rubro normalizado con un identificador único para crear URLs amigables.
- **Estado de Pausa**: Verifica el estado del sitio web antes de mostrarlo, redirigiendo a una página especial si está pausado.
- **Geocodificación**: Manejo de ubicaciones para mostrar mapas precisos, con fallbacks para casos donde no se proporciona ubicación.
- **Integración con IA**: Uso de Groq para generar contenido personalizado con reglas específicas para asegurar calidad.

## Estructura de la Base de Datos

La base de datos está implementada en Supabase y consta de las siguientes tablas principales:

### 1. clients
Almacena información básica de los clientes.
- **id**: UUID, clave primaria (autogenerada)
- **created_at**: Timestamp de creación (autogenerado)
- **name**: Nombre del cliente
- **phone**: Número de teléfono WhatsApp del cliente (único)
- **email**: Dirección de correo electrónico
- **instagram_handle**: Usuario de Instagram
- **business_type**: Tipo de negocio/industria
- **status**: Estado del cliente (lead, active, inactive, etc.)
- **notes**: Notas adicionales sobre el cliente

### 2. websites
Almacena información sobre los sitios web de los clientes.
- **id**: UUID, clave primaria (autogenerada)
- **created_at**: Timestamp de creación (autogenerado)
- **client_id**: Clave foránea a la tabla clients
- **domain**: Dominio del sitio web (si se usa un dominio personalizado)
- **subdomain**: Subdominio de TuWebFacil
- **template_id**: ID de la plantilla utilizada
- **status**: Estado del sitio web (draft, published, archived, paused)
- **last_updated**: Timestamp de última actualización
- **seo_title**: Título SEO
- **seo_description**: Descripción SEO
- **analytics_id**: ID de Google Analytics (si aplica)

### 3. website_content
Almacena el contenido real de los sitios web en formato JSON.
- **id**: UUID, clave primaria (autogenerada)
- **created_at**: Timestamp de creación (autogenerado)
- **website_id**: Clave foránea a la tabla websites
- **version**: Número de versión del contenido
- **is_current**: Si esta es la versión actual
- **content**: Contenido del sitio web en formato JSON
- **content_type**: Tipo de contenido (page, blog, gallery, etc.)
- **path**: Ruta URL para este contenido
- **metadata**: Metadatos adicionales

### Relaciones Principales
- Un cliente puede tener múltiples sitios web (one-to-many).
- Un sitio web puede tener múltiples entradas de contenido, pero solo una activa (one-to-many con filtro is_current).
- Existen otras tablas para suscripciones, pagos, análisis de competidores, etc., que se relacionan principalmente con la tabla clients.

### Estructura JSON del Contenido
El contenido generado por la IA y almacenado en website_content.content incluye:
- **titulo_web**: Nombre del negocio
- **subtitulo**: Descripción breve del negocio
- **servicios_sugeridos**: Lista de servicios ofrecidos
- **descripciones_servicios**: Descripciones detalladas de cada servicio
- **fotos_queries**: Términos de búsqueda para imágenes
- **fotos_servicios**: URLs de imágenes obtenidas de Unsplash
- **horario**: Horario de atención
- **ubicacion_detectada**: Ubicación del negocio
- **mapa**: Coordenadas geográficas y nivel de zoom
- **paleta_colores**: Colores primario y secundario para el diseño

## Flujo de la Plantilla (client_template.html)

### Estructura General
La plantilla utiliza Jinja2 para renderizar dinámicamente el contenido generado por la IA y almacenado en la base de datos.

### Variables Jinja2 Principales
- **web_content**: Objeto JSON con todo el contenido del sitio web.
  - **web_content.titulo_web**: Título principal del sitio.
  - **web_content.subtitulo**: Subtítulo o eslogan.
  - **web_content.paleta_colores**: Colores personalizados para el sitio.
  - **web_content.servicios_sugeridos**: Lista de servicios a mostrar.
  - **web_content.descripciones_servicios**: Descripciones de los servicios.
  - **web_content.fotos_servicios**: URLs de imágenes para cada servicio.
  - **web_content.horario**: Horario de atención.
  - **web_content.ubicacion_detectada**: Ubicación textual.
  - **web_content.mapa**: Coordenadas para el mapa (lat, lon, zoom).

- **client**: Objeto con información del cliente.
  - **client.phone**: Número de teléfono para el botón de WhatsApp.

### Secciones Principales
1. **Header/Hero**: Muestra el título, subtítulo y un botón de contacto por WhatsApp.
2. **Servicios**: Muestra los servicios generados por la IA con imágenes y descripciones.
3. **Contacto y Ubicación**: Muestra información de contacto, horarios y un mapa interactivo.
4. **Footer**: Muestra información de copyright y créditos.
5. **Botón Flotante de WhatsApp**: Presente en todas las páginas para facilitar el contacto.

### Personalización Visual
- La plantilla utiliza Tailwind CSS para el diseño.
- Los colores se personalizan según la paleta generada por la IA.
- Se aplican gradientes y efectos visuales para mejorar la apariencia.
- Se utilizan fuentes específicas (Plus Jakarta Sans) para una estética profesional.

### Adaptabilidad
- Diseño responsive que se adapta a diferentes tamaños de pantalla.
- Manejo de casos donde cierta información no está disponible (horarios, ubicación).
- Integración de mapas de OpenStreetMap con marcadores personalizados.

## Puntos Críticos del Sistema

### 1. Manejo de Slugs
- Los slugs se generan a partir del rubro del negocio, normalizando el texto (eliminando acentos, convirtiendo a minúsculas).
- Se añade un identificador único (UUID parcial) para evitar colisiones.
- Los slugs son críticos para el enrutamiento y acceso a los sitios web de los clientes.

### 2. Estado de Pausa
- Los sitios web pueden tener un estado "paused" que muestra una plantilla alternativa.
- Este mecanismo permite suspender temporalmente sitios por falta de pago o mantenimiento.
- La verificación se realiza en la ruta `/<client_slug>` antes de renderizar el contenido.

### 3. Geocodificación
- El sistema utiliza Nominatim para convertir direcciones textuales en coordenadas.
- Incluye manejo de errores y casos especiales (ubicaciones genéricas, no proporcionadas).
- Ajusta automáticamente el nivel de zoom según la especificidad de la dirección.

### 4. Integración con IA
- El sistema utiliza Groq para generar contenido personalizado.
- El prompt está cuidadosamente diseñado con reglas específicas para asegurar contenido de calidad.
- Se procesan las respuestas para enriquecerlas con imágenes y datos geográficos.

### 5. Almacenamiento de Versiones
- El sistema mantiene un historial de versiones del contenido del sitio web.
- Solo una versión está marcada como "is_current" en cualquier momento.
- Esto permite implementar funcionalidad de "deshacer" y mantener un historial de cambios.

### 6. Integración de Pagos
- El sistema se integra con MercadoPago para gestionar suscripciones y pagos.
- El estado de la suscripción afecta directamente al estado del sitio web (active/paused).

### 7. Experiencia de Usuario en WhatsApp
- El sistema incluye un flujo de interacción por WhatsApp documentado en whatsapp_ux.md.
- Esta integración es crítica para la comunicación con clientes y la gestión de sus sitios.

## Conclusión

TuWebFacil es un sistema completo para la generación automática de sitios web para pequeños negocios, utilizando inteligencia artificial para personalizar el contenido. La arquitectura combina Flask en el backend, Supabase para la base de datos, y varias APIs externas (Groq, Unsplash, Nominatim) para enriquecer la experiencia. El sistema está diseñado para ser escalable, con capacidad para gestionar múltiples clientes, sitios web y versiones de contenido.