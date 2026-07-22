# TuWebFacil: Fábrica de Sitios y Agencia de Marketing Autónoma

TuWebFacil es una plataforma que crea, gestiona y vende sitios web automáticamente. Utiliza inteligencia artificial para generar contenido, analizar competidores y proporcionar una experiencia de usuario intuitiva a través de WhatsApp.

## Arquitectura del Sistema

El sistema está compuesto por varios módulos que trabajan juntos para proporcionar una solución completa:

### Componentes Principales

1. **Core (app.py)**: Aplicación Flask que maneja las interacciones con Telegram o WhatsApp y utiliza Gemini AI para generar respuestas.

2. **Receptor de WhatsApp (receiver.py)**: Maneja los webhooks de WhatsApp, procesa los mensajes entrantes y detecta enlaces de Instagram.

3. **Emisor de WhatsApp (sender.py)**: Proporciona funcionalidad para enviar mensajes a través de la API de WhatsApp Cloud.

4. **Integración con Mercado Pago (mercadopago_integration.py)**: Gestiona suscripciones y pagos a través de Mercado Pago, con notificaciones automáticas por WhatsApp.

5. **Bot de Marketing (marketing_bot.py)**: Genera contenido diario para Instagram y analiza competidores.

6. **Análisis de Competencia (competitor_analysis.py)**: Proporciona análisis detallado de competidores y genera estrategias de contenido.

7. **UX de WhatsApp (whatsapp_ux.md)**: Diseño de la experiencia de usuario para la gestión post-venta a través de WhatsApp.

### Base de Datos (Supabase)

La estructura de la base de datos está diseñada para manejar clientes, suscripciones, contenido web y análisis de competidores. Ver `database_schema.md` para más detalles.

## Flujo de Trabajo

1. **Captación de Clientes**:
   - Los clientes contactan a través de WhatsApp
   - El sistema detecta enlaces de Instagram y analiza el perfil del cliente
   - Se genera una propuesta de sitio web basada en el análisis

2. **Creación de Sitio Web**:
   - El sistema utiliza Gemini AI para generar contenido personalizado
   - Se crea un sitio web basado en plantillas predefinidas
   - El cliente recibe un enlace para ver su sitio web

3. **Gestión Post-Venta**:
   - El cliente puede gestionar su sitio web a través de WhatsApp
   - Sistema de menús intuitivo para Alta, Baja y Modificaciones (ABM)
   - Funcionalidad de "Undo" para revertir cambios

4. **Suscripciones y Pagos**:
   - Integración con Mercado Pago para gestionar suscripciones mensuales
   - Notificaciones automáticas por WhatsApp en caso de fallo en el pago
   - Gestión de ciclo de vida de suscripciones

5. **Marketing Autónomo**:
   - Generación diaria de contenido para Instagram
   - Análisis de competidores para encontrar oportunidades
   - Estrategias de contenido personalizadas

## Configuración del Entorno

### Requisitos

- Python 3.8+
- Flask
- Supabase
- Google Generative AI (Gemini)
- Mercado Pago SDK
- Instagram Graph API

### Variables de Entorno

Crear un archivo `.env` con las siguientes variables:

```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_api_key
WHATSAPP_TOKEN=your_whatsapp_token
PHONE_NUMBER_ID=your_phone_number_id
TELEGRAM_TOKEN=your_telegram_token
MERCADOPAGO_ACCESS_TOKEN=your_mercadopago_token
INSTAGRAM_ACCESS_TOKEN=your_instagram_token
INSTAGRAM_BUSINESS_ID=your_instagram_business_id
```

### Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/tuwebfacil/tuwebfacil.git
cd tuwebfacil
```

2. Crear y activar un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar la base de datos en Supabase según el esquema definido en `database_schema.md`.

5. Iniciar el servidor:
```bash
python app.py
```

## Uso del Sistema

### Configuración de Webhooks

1. **WhatsApp**:
   - Configurar un webhook en Meta Developers
   - Apuntar el webhook a `https://tu-dominio.com/webhook`
   - Verificar el número de teléfono

2. **Telegram**:
   - Configurar un webhook para el bot de Telegram
   - Apuntar el webhook a `https://tu-dominio.com/telegram`

3. **Mercado Pago**:
   - Configurar webhooks para notificaciones de pagos y suscripciones
   - Apuntar a los endpoints correspondientes

### Gestión de Clientes

1. **Recepción de Mensajes**:
   - Los mensajes de WhatsApp son recibidos por `receiver.py`
   - Los mensajes de Telegram son recibidos por `app.py`

2. **Procesamiento de Mensajes**:
   - Se utiliza Gemini AI para entender la intención del usuario
   - Se genera una respuesta personalizada

3. **Gestión de Sitios Web**:
   - Los clientes pueden gestionar su sitio web a través de WhatsApp
   - Sistema de estados para guiar al usuario a través de diferentes operaciones

### Marketing Autónomo

1. **Generación de Contenido**:
   - Ejecutar `python marketing_bot.py` para generar contenido diario
   - El contenido se almacena en Supabase y puede ser revisado antes de publicarse

2. **Análisis de Competidores**:
   - Ejecutar `python competitor_analysis.py` para analizar competidores
   - Generar estrategias de contenido basadas en el análisis

## Estructura de Archivos

```
TuWebFacil/
├── app.py                     # Aplicación Flask principal
├── receiver.py                # Receptor de webhooks de WhatsApp
├── sender.py                  # Emisor de mensajes de WhatsApp
├── mercadopago_integration.py # Integración con Mercado Pago
├── marketing_bot.py           # Bot de marketing para Instagram
├── competitor_analysis.py     # Análisis de competidores
├── database_schema.md         # Esquema de la base de datos
├── whatsapp_ux.md             # Diseño de la UX de WhatsApp
├── .env                       # Variables de entorno
├── requirements.txt           # Dependencias
└── README.md                  # Este archivo
```

## Módulos Detallados

### Core (app.py)

El núcleo del sistema que maneja las interacciones con Telegram y utiliza Gemini AI para generar respuestas. Proporciona una interfaz para que los clientes interactúen con el sistema.

### Receptor de WhatsApp (receiver.py)

Maneja los webhooks de WhatsApp, procesa los mensajes entrantes y detecta enlaces de Instagram. Este módulo es el punto de entrada para las interacciones de WhatsApp.

### Emisor de WhatsApp (sender.py)

Proporciona funcionalidad para enviar mensajes a través de la API de WhatsApp Cloud. Se utiliza para enviar respuestas, notificaciones y actualizaciones a los clientes.

### Integración con Mercado Pago (mercadopago_integration.py)

Gestiona suscripciones y pagos a través de Mercado Pago. Proporciona funcionalidades para:
- Crear planes de suscripción
- Gestionar suscripciones de clientes
- Procesar pagos
- Manejar notificaciones de pagos fallidos
- Enviar notificaciones por WhatsApp

### Bot de Marketing (marketing_bot.py)

Genera contenido diario para Instagram y analiza competidores. Utiliza Gemini AI para crear:
- Textos para publicaciones
- Descripciones de diseño visual
- Mensajes clave
- Llamadas a la acción

### Análisis de Competencia (competitor_analysis.py)

Proporciona análisis detallado de competidores y genera estrategias de contenido. Incluye:
- Análisis de cuentas de Instagram de competidores
- Informes comparativos
- Estrategias de contenido basadas en debilidades de competidores
- Seguimiento del crecimiento de competidores

### UX de WhatsApp (whatsapp_ux.md)

Diseño de la experiencia de usuario para la gestión post-venta a través de WhatsApp. Define:
- Máquina de estados para la conversación
- Estructura de menús
- Funcionalidad de "Undo"
- Validación de contenido

## Contribución

1. Fork del repositorio
2. Crear una rama para tu feature (`git checkout -b feature/amazing-feature`)
3. Commit de tus cambios (`git commit -m 'Add some amazing feature'`)
4. Push a la rama (`git push origin feature/amazing-feature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo LICENSE para más detalles.

## Contacto

TuWebFacil - [@tuwebfacil](https://instagram.com/tuwebfacil)

Link del proyecto: [https://github.com/tuwebfacil/tuwebfacil](https://github.com/tuwebfacil/tuwebfacil)