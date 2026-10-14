# Guía de Configuración de Meta API (Instagram & WhatsApp)

Esta guía documenta el proceso exacto que realizamos para vincular la aplicación de TuWebLista con Meta for Developers, con el objetivo de poder realizar publicaciones automáticas en Instagram y enviar mensajes por WhatsApp.

## 1. Requisitos Previos Indispensables
1. La cuenta de Instagram debe ser **Profesional** o **Creador**.
2. La cuenta de Instagram debe estar vinculada obligatoriamente a una **Página de Facebook (Fanpage)**. No funciona si solo está vinculada a un perfil personal.
   - *Para vincularla*: Desde la app de Instagram > Editar Perfil > Información pública de la empresa > Página > Seleccionar o crear Fanpage.

## 2. Creación de la Aplicación en Meta
1. Ir a [developers.facebook.com](https://developers.facebook.com/).
2. Crear aplicación > Otros > Tipo de aplicación: **Empresa**.
3. En el panel de la app (menú izquierdo), agregar los productos:
   - API de WhatsApp Business
   - API Graph de Instagram

## 3. Generación del Token de Acceso
1. En el menú superior, ir a **Herramientas > Explorador de la API Graph**.
2. En la barra lateral derecha:
   - Aplicación de Meta: `TuWebLista`
   - Usuario o página: `Token de usuario` (User Token)
3. Agregar Permisos (buscarlos por categoría o por nombre):
   - `whatsapp_business_management`
   - `whatsapp_business_messaging`
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list` (o en su defecto `pages_read_engagement`)
   - `business_management`
4. Hacer clic en **"Generate Access Token"** (botón azul).
5. Se abrirá una ventana de Facebook. **MUY IMPORTANTE**: Hacer clic en "Editar configuración" y marcar las casillas de TODAS las Fanpages y Cuentas de Instagram vinculadas.
6. Copiar el token corto generado.

## 4. Extender la Vida del Token (Token de Larga Duración)
1. Ir al [Depurador de Tokens de Acceso](https://developers.facebook.com/tools/debug/accesstoken/).
2. Pegar el token corto y hacer clic en **Depurar**.
3. Ir hasta el final de la página y hacer clic en **"Ampliar token de acceso"** (Extend Access Token).
4. Se generará un nuevo token muy largo. Este es el `INSTAGRAM_ACCESS_TOKEN` definitivo (dura 60 días).

## 5. Obtener el ID de Instagram Business
1. Volver al Explorador de la API Graph.
2. Pegar el token largo recién obtenido en la caja de "Identificador de acceso".
3. En la barra de consulta (GET), escribir: `me/accounts?fields=instagram_business_account`
4. Clic en **Enviar**.
5. En la respuesta JSON (caja de la izquierda), buscar el número dentro de `"instagram_business_account": { "id": "178..." }`.
6. Ese número largo es el `INSTAGRAM_BUSINESS_ID`.

## 6. Variables de Entorno (.env)
Una vez obtenidos los datos, se deben guardar en el archivo `.env` del VPS de producción:
```env
INSTAGRAM_ACCESS_TOKEN=EA... (Token Largo)
INSTAGRAM_BUSINESS_ID=178... (ID de Instagram)
```
