#!/usr/bin/env python3
"""
Test Suite: Frontend de Lista de Precios & Servicios (client_template.html)
Verifica:
1. Renderizado sin lista_precios (retrocompatibilidad 100%, sin errores ni sección #precios).
2. Renderizado con lista_precios completa (sección #precios, encabezados, buscador en vivo, tabla desktop y tarjetas/pestañas mobile).
3. Renderizado con is_preview=True (banner destacado de borrador con texto exacto).
4. Verificación de enlaces preformateados de WhatsApp: teléfono limpio y texto codificado correctamente con urlencode.
"""

import os
import sys
import re
import urllib.parse
import jinja2

# Ajustar PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from app import app, format_phone


def get_jinja_template():
    """Obtiene el template client_template.html desde el entorno de Flask o Jinja2 directo."""
    try:
        return app.jinja_env.get_template('client_template.html')
    except Exception:
        loader = jinja2.FileSystemLoader(os.path.join(PROJECT_ROOT, 'templates'))
        env = jinja2.Environment(loader=loader, autoescape=True)
        env.filters['format_phone'] = format_phone
        return env.get_template('client_template.html')


def build_base_context():
    """Genera un contexto base válido sin lista_precios."""
    return {
        "web_content": {
            "titulo_web": "Centro de Estética Lumière",
            "subtitulo": "Tratamientos corporales y faciales de avanzada",
            "paleta_colores": {"primario": "#4F46E5", "secundario": "#7C3AED"},
            "servicios_sugeridos": ["Depilación Láser", "Limpieza Facial", "Masajes Reductores"],
            "descripciones_servicios": [
                "Tecnología definitiva indolora.",
                "Higiene profunda y renovación celular.",
                "Modelación y drenaje linfático."
            ],
            "fotos_servicios": [
                "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881",
                "https://images.unsplash.com/photo-1512290900672-1f41d9c1a5b8",
                "https://images.unsplash.com/photo-1544367567-0f2fcb009e0b"
            ],
            "foto_hero": "https://images.unsplash.com/photo-1521791136364-798a7bc0d26e",
            "horario": "Lunes a Viernes 09:00 a 19:00",
            "ubicacion_detectada": "Palermo, Ciudad Autónoma de Buenos Aires",
            "whatsapp_contacto": "+54 9 11 3471-0787",
            "email_contacto": "contacto@lumiere.com.ar",
            "instagram": "estetica.lumiere",
            "mapa": {"lat": -34.588, "lon": -58.430, "zoom": 15}
        },
        "client": {"phone": "5491134710787"},
        "web_status": "published",
        "has_edits": True,
        "is_preview": False,
        "bot_phone": "5491134710787"
    }


def build_sample_price_list():
    """Genera una estructura representativa de lista_precios (Soteria 3 modalidades)."""
    return {
        "titulo": "Lista de Precios Oficial",
        "columnas_pago": ["Efectivo", "Transferencia", "Tarjeta"],
        "items": [
            {
                "servicio": "Abdomen",
                "precios": {
                    "efectivo": "$48.089,77",
                    "transferencia": "$55.303,24",
                    "tarjeta": "$63.478,50"
                }
            },
            {
                "servicio": "Axilas",
                "precios": {
                    "efectivo": "$25.000",
                    "transferencia": "$28.750",
                    "tarjeta": "$33.000"
                }
            },
            {
                "servicio": "Rostro Completo",
                "precios": {
                    "efectivo": "$30.500,50",
                    "transferencia": "$35.075,58",
                    "tarjeta": "$40.260,66"
                }
            }
        ]
    }


def run_tests():
    print("=" * 75)
    print("🚀 INICIANDO TEST SUITE: LISTA DE PRECIOS & SERVICIOS (FRONTEND UX)")
    print("=" * 75)

    template = get_jinja_template()
    assert template is not None, "Error al cargar templates/client_template.html"
    print("  ✅ Template client_template.html cargado con éxito en Jinja2.")

    # -------------------------------------------------------------------------
    # TEST 1: Renderizado sin lista_precios (Retrocompatibilidad)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Verificando retrocompatibilidad cuando NO hay lista_precios...")
    ctx_empty = build_base_context()
    html_empty = template.render(**ctx_empty)

    assert '<section id="precios"' not in html_empty, "El contenedor #precios no debe renderizarse si no hay lista_precios"
    assert 'id="price-search-input"' not in html_empty, "El buscador no debe aparecer si no hay lista_precios"
    assert 'id="price-pills-container"' not in html_empty, "Las pestañas táctiles no deben aparecer si no hay lista_precios"
    assert 'id="price-multi-bar"' not in html_empty, "La barra flotante de selección múltiple no debe aparecer si no hay lista_precios"
    assert 'price-item-checkbox' not in html_empty, "Los checkboxes de selección no deben aparecer si no hay lista_precios"
    assert 'VISTA PREVIA (Borrador sin publicar)' not in html_empty, "No debe mostrar banner de borrador si is_preview=False"
    assert 'Nuestros Servicios' in html_empty, "Debe renderizar la sección de servicios original normalmente"
    assert 'Depilación Láser' in html_empty, "Debe renderizar los servicios sugeridos estándar"
    print("  ✅ Retrocompatibilidad perfecta: el template se renderiza idéntico a hoy sin errores Jinja.")

    # -------------------------------------------------------------------------
    # TEST 2: Renderizado con lista_precios completa (Responsive & Buscador)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verificando renderizado completo de la Lista de Precios...")
    ctx_full = build_base_context()
    ctx_full["web_content"]["lista_precios"] = build_sample_price_list()
    html_full = template.render(**ctx_full)

    # 2.A: Contenedor y Encabezados
    assert 'id="precios"' in html_full, "Debe contener el elemento <section id='precios'>"
    assert 'Lista de Precios Oficial' in html_full, "Debe mostrar el título de la lista de precios"
    assert 'Consultá nuestros tratamientos y reservá tu turno por WhatsApp.' in html_full, "Debe mostrar el subtítulo oficial"

    # 2.B: Buscador en tiempo real
    assert 'id="price-search-input"' in html_full, "Debe incluir el input del buscador con id='price-search-input'"
    assert 'placeholder="Buscar tratamiento o servicio..."' in html_full, "Debe incluir el placeholder esperado"
    assert 'id="price-search-clear"' in html_full, "Debe incluir el botón de limpiar búsqueda"
    assert 'id="price-no-results"' in html_full, "Debe incluir el contenedor de mensaje amigable cuando no hay resultados"

    # 2.C: Tabla de Computadora / Tablet (hidden md:block)
    assert 'id="desktop-price-table-wrapper"' in html_full, "Debe incluir el contenedor desktop de la tabla"
    assert 'hidden md:block' in html_full, "La vista de computadora debe tener clase responsive 'hidden md:block'"
    assert 'Tratamiento / Servicio' in html_full, "La cabecera de la tabla debe contener 'Tratamiento / Servicio'"
    assert 'Acción' in html_full, "La cabecera de la tabla debe contener la columna 'Acción'"
    for col in ["Efectivo", "Transferencia", "Tarjeta"]:
        assert f'<th scope="col" class="py-5 px-6 text-center">{col}</th>' in html_full, f"La cabecera debe contener la columna '{col}'"

    # 2.D: Filas y Datos de los Servicios en Desktop
    for item in ctx_full["web_content"]["lista_precios"]["items"]:
        srv = item["servicio"]
        assert srv in html_full, f"El servicio '{srv}' debe figurar en el HTML"
        for p in item["precios"].values():
            assert p in html_full, f"El precio '{p}' de '{srv}' debe figurar en el HTML"

    # 2.E: Celular (block md:hidden) - Selector de Pestañas / Pills
    assert 'id="mobile-price-section"' in html_full, "Debe incluir la sección mobile con id='mobile-price-section'"
    assert 'block md:hidden' in html_full, "La vista celular debe tener clase responsive 'block md:hidden'"
    assert 'price-tab-pill' in html_full, "Debe contener botones con clase 'price-tab-pill'"
    assert '💵' in html_full, "Pestaña Efectivo debe tener emoji representativo 💵"
    assert '📲' in html_full, "Pestaña Transferencia debe tener emoji representativo 📲"
    assert '💳' in html_full, "Pestaña Tarjeta debe tener emoji representativo 💳"

    # 2.F: Tarjetas Compactas Mobile
    assert 'price-item-card' in html_full, "Debe contener tarjetas con clase 'price-item-card'"
    assert 'price-value' in html_full, "Debe contener valor de precio destacado con clase 'price-value'"
    assert 'price-method-badge' in html_full, "Debe contener badge del método activo 'price-method-badge'"
    print("  ✅ Contenedor #precios, buscador en vivo, tabla desktop y pestañas táctiles mobile verificados.")

    # -------------------------------------------------------------------------
    # TEST 3: Renderizado con is_preview=True (Banner de Borrador)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Verificando modo Vista Previa (is_preview=True vs False)...")
    ctx_preview = build_base_context()
    ctx_preview["web_content"]["lista_precios"] = build_sample_price_list()
    ctx_preview["is_preview"] = True

    html_preview = template.render(**ctx_preview)
    expected_banner_text = "🔍 VISTA PREVIA (Borrador sin publicar) — Los cambios aún no son públicos. Revisá tus precios y confirmá en WhatsApp."
    assert expected_banner_text in html_preview, "Debe contener exactamente el texto del banner de vista previa"
    assert "bg-amber-500" in html_preview or "bg-amber" in html_preview, "El banner debe tener color de alerta/ámbar visible"

    # Comprobar que con is_preview=False desaparece
    ctx_preview["is_preview"] = False
    html_no_preview = template.render(**ctx_preview)
    assert expected_banner_text not in html_no_preview, "No debe contener el banner de vista previa si is_preview=False"
    print("  ✅ Banner superior de vista previa verificado con éxito (activación y desactivación).")

    # -------------------------------------------------------------------------
    # TEST 4: Verificación de Enlaces Preformateados de WhatsApp & urlencode
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Verificando links preformateados de WhatsApp y codificación urlencode...")
    ctx_wa = build_base_context()
    ctx_wa["web_content"]["titulo_web"] = "Estética & Spa Lumière"
    ctx_wa["web_content"]["whatsapp_contacto"] = "+54 9 11 3471-0787"
    ctx_wa["web_content"]["lista_precios"] = build_sample_price_list()

    html_wa = template.render(**ctx_wa)

    # Extraer todos los links de wa.me en la sección #precios
    wa_links = re.findall(r'href="(https://wa\.me/[^"]+)"', html_wa)
    assert len(wa_links) > 0, "Debe haber enlaces a wa.me en el template"

    # Filtrar solo los links de turnos de la lista de precios (contienen 'reservar%20un%20turno' o 'reservar+un+turno')
    price_wa_links = [
        link for link in wa_links 
        if "reservar" in link and "turno" in link
    ]
    assert len(price_wa_links) >= 6, f"Esperados al menos 6 links (3 desktop + 3 mobile), obtenidos: {len(price_wa_links)}"

    expected_phone = "5491134710787"
    for link in price_wa_links:
        # 1. El link debe apuntar al teléfono limpio (sin +, sin espacios, sin guiones)
        parsed_url = urllib.parse.urlparse(link)
        assert parsed_url.netloc == "wa.me", f"El host debe ser wa.me: {link}"
        phone_in_url = parsed_url.path.strip("/")
        assert phone_in_url == expected_phone, f"Teléfono en URL '{phone_in_url}' != esperado '{expected_phone}'"

        # 2. El parámetro 'text' debe existir y estar codificado
        query_params = urllib.parse.parse_qs(parsed_url.query)
        assert "text" in query_params, f"El enlace no contiene el parámetro 'text': {link}"

        # 3. Al decodificar 'text', debe cumplir el formato:
        # Hola {titulo_web}! Quiero consultar disponibilidad para reservar un turno de: {servicio} ({metodo}: {precio})
        raw_text_decoded = query_params["text"][0]
        assert raw_text_decoded.startswith("Hola Estética & Spa Lumière! Quiero consultar disponibilidad para reservar un turno de: "), \
            f"El texto inicial de WhatsApp no coincide: {raw_text_decoded}"
        assert "(Efectivo: " in raw_text_decoded, f"Debe incluir el método y precio inicial: {raw_text_decoded}"
        assert raw_text_decoded.endswith(")"), f"El mensaje debe cerrar con paréntesis: {raw_text_decoded}"

        # 4. Asegurar que no hay caracteres de espacio sin codificar en el enlace href
        assert " " not in link, f"El enlace href contiene espacios sin codificar: {link}"

    # 4.B: Probar fallback a client.phone si whatsapp_contacto es None o vacío
    ctx_fallback = build_base_context()
    ctx_fallback["web_content"]["whatsapp_contacto"] = ""
    ctx_fallback["client"]["phone"] = "+54 9 11 9988-7766"
    ctx_fallback["web_content"]["lista_precios"] = build_sample_price_list()
    html_fallback = template.render(**ctx_fallback)

    assert "https://wa.me/5491199887766?" in html_fallback, "Debe tomar client.phone sanitizado si whatsapp_contacto está vacío"
    print("  ✅ Enlaces wa.me verificados: teléfono normalizado, query params 100% conformes al contrato y urlencode válido.")

    # -------------------------------------------------------------------------
    # TEST 5: Scroll Automático a #precios en JavaScript
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Verificando script de scroll automático a #precios...")
    assert "window.location.hash === '#precios'" in html_full, "El script debe detectar #precios en el hash"
    assert "window.location.pathname.endsWith('/precios')" in html_full, "El script debe detectar /precios en el pathname"
    assert "scrollIntoView({ behavior: 'smooth' })" in html_full, "El script debe invocar scrollIntoView con 'smooth'"
    print("  ✅ Lógica de scroll automático detectada en el bundle de JavaScript del template.")

    # -------------------------------------------------------------------------
    # TEST 6: Selección Múltiple de Servicios y Sticky Bar (Carrito)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Verificando Selección Múltiple y Sticky Bar (#price-multi-bar)...")
    # 6.A Checkboxes en desktop
    assert 'class="price-item-checkbox' in html_full, "Deben existir checkboxes con clase 'price-item-checkbox' en desktop"
    desktop_cb_count = len(re.findall(r'class="[^"]*price-item-checkbox(?![a-zA-Z0-9\-_])[^"]*"', html_full))
    assert desktop_cb_count == 3, f"Esperados 3 checkboxes desktop, encontrados {desktop_cb_count}"
    assert '<th scope="col" class="py-5 px-4 text-center w-14">Elegir</th>' in html_full, "La tabla desktop debe tener la columna de cabecera 'Elegir'"

    # 6.B Checkboxes en mobile
    assert 'class="price-item-checkbox-mobile' in html_full, "Deben existir checkboxes con clase 'price-item-checkbox-mobile' en mobile"
    mobile_cb_count = len(re.findall(r'class="[^"]*price-item-checkbox-mobile[^"]*"', html_full))
    assert mobile_cb_count == 3, f"Esperados 3 checkboxes mobile, encontrados {mobile_cb_count}"

    # 6.C Barra flotante inferior de selección múltiple (Carrito de Presupuesto)
    assert 'id="price-multi-bar"' in html_full, "Debe existir la barra flotante con id='price-multi-bar'"
    assert 'z-[150]' in html_full, "La barra flotante #price-multi-bar debe tener z-[150] para superponerse a cualquier banner demo"
    assert 'id="multi-count"' in html_full, "Debe existir el contador con id='multi-count'"
    assert 'id="multi-btn-count"' in html_full, "Debe existir el contador en el botón con id='multi-btn-count'"
    assert 'Carrito:' in html_full, "La barra debe titularse explícitamente como 'Carrito:'"
    assert 'id="multi-totals-summary"' in html_full, "Debe existir el contenedor del total con id='multi-totals-summary'"
    assert 'id="multi-primary-total"' in html_full, "Debe existir el total destacado con id='multi-primary-total'"
    assert 'id="multi-clear-btn"' in html_full, "Debe existir el botón de deseleccionar con id='multi-clear-btn'"
    assert 'id="multi-wa-btn"' in html_full, "Debe existir el botón de WhatsApp con id='multi-wa-btn'"

    # 6.D Funciones de cálculo y lógica JS en el bundle
    assert 'function parsePriceValue' in html_full, "El script JS debe definir la función parsePriceValue"
    assert 'function formatARS' in html_full, "El script JS debe definir la función formatARS"
    assert 'selectedServices' in html_full, "El script JS debe mantener el estado selectedServices"
    assert 'function updateStickyBar' in html_full, "El script JS debe definir la función updateStickyBar"
    assert 'function setServiceSelected' in html_full, "El script JS debe definir la función setServiceSelected"
    assert 'function handleRowWaBtnClick' in html_full, "El script JS debe definir la función handleRowWaBtnClick para sincronizar los botones de fila"
    assert 'Pedir Presupuesto' in html_full, "El script JS debe actualizar el texto de botones a 'Pedir Presupuesto'"

    # 6.E Comprobar formato del mensaje compuesto para WhatsApp
    assert 'Total estimado' in html_full, "El script JS debe formatear el mensaje con 'Total estimado'"
    assert 'Quiero consultar disponibilidad y presupuesto para reservar un turno con estos tratamientos' in html_full, \
        "El script JS debe incluir el encabezado compuesto para múltiples tratamientos"
    print("  ✅ Selección múltiple verificada: checkboxes en desktop/mobile, sticky bar z-[150] y botones de fila sincronizados al carrito.")

    # -------------------------------------------------------------------------
    # TEST 7: Promoción por Fecha / Jornada (Banner y Precios Tachados Dinámicos)
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Verificando Banner de Jornada y Precios Tachados por Promoción...")
    ctx_promo = build_base_context()
    sample_prices = build_sample_price_list()
    sample_prices["promocion_fecha"] = {
        "titulo": "Jornada Láser 17 de Noviembre",
        "activa": True,
        "escalas": [
            {
                "hasta": "2026-10-27",
                "hasta_display": "27 de Octubre de 2026",
                "descuento": 30,
                "label": "30% OFF Anticipado"
            },
            {
                "hasta": "2026-11-15",
                "hasta_display": "15 de Noviembre de 2026",
                "descuento": 15,
                "label": "15% OFF"
            }
        ]
    }
    ctx_promo["web_content"]["lista_precios"] = sample_prices
    html_promo = template.render(**ctx_promo)

    # 7.A: Banner de Jornada / Evento
    assert 'id="promo-banner-container"' in html_promo, "Debe existir el contenedor #promo-banner-container cuando hay promoción activa"
    assert 'Jornada Láser 17 de Noviembre' in html_promo, "Debe mostrar el título de la jornada en el banner"
    assert 'Evento Especial' in html_promo, "Debe incluir la etiqueta 'Evento Especial'"
    assert 'id="promo-active-badge"' in html_promo, "Debe incluir el badge animado #promo-active-badge"
    assert 'id="promo-scales-list"' in html_promo, "Debe incluir la lista de escalas #promo-scales-list"
    assert 'data-until="2026-10-27"' in html_promo, "Debe incluir data-until en la píldora de la escala 1"
    assert 'data-discount="30"' in html_promo, "Debe incluir data-discount en la píldora de la escala 1"
    assert 'data-label="30% OFF Anticipado"' in html_promo, "Debe incluir data-label en la píldora de la escala 1"
    assert 'Hasta el 27 de Octubre de 2026' in html_promo, "Debe mostrar 'Hasta el 27 de Octubre de 2026'"
    assert '30% OFF' in html_promo, "Debe mostrar '30% OFF'"
    assert 'data-until="2026-11-15"' in html_promo, "Debe incluir data-until en la píldora de la escala 2"
    assert 'data-discount="15"' in html_promo, "Debe incluir data-discount en la píldora de la escala 2"
    assert 'Hasta el 15 de Noviembre de 2026' in html_promo, "Debe mostrar 'Hasta el 15 de Noviembre de 2026'"
    assert '15% OFF' in html_promo, "Debe mostrar '15% OFF'"

    # 7.B: Atributos para JavaScript en filas y tarjetas
    assert 'data-regular-prices=' in html_promo, "Las filas y tarjetas deben preservar sus precios base en data-regular-prices"
    assert 'data-regular-price=' in html_promo, "Las celdas desktop deben incluir data-regular-price"

    # 7.C: Script con evaluación dinámica de fechas y recálculo en tiempo real
    assert 'const promoData =' in html_promo, "El script JS debe recibir promoData desde Jinja"
    assert 'todayStr <=' in html_promo or 'todayStr <= esc.hasta' in html_promo, "El script JS debe comparar todayStr con esc.hasta"
    assert 'activeDiscount =' in html_promo, "El script JS debe calcular activeDiscount"
    assert 'function applyRealtimeDiscounts' in html_promo, "El script JS debe definir applyRealtimeDiscounts"
    assert 'function updateMobileCardPrice' in html_promo, "El script JS debe definir updateMobileCardPrice"
    assert 'function getDiscountedPricesObject' in html_promo, "El script JS debe definir getDiscountedPricesObject"
    assert 'line-through' in html_promo, "El script JS debe contener la clase line-through para precios tachados"
    assert 'text-emerald-600' in html_promo, "El script JS debe formatear los precios con descuento en verde esmeralda"
    assert 'OFF aplicado' in html_promo, "El script JS debe añadir el aviso de descuento aplicado en el total del carrito"
    assert 'Promo aplicada:' in html_promo, "El script JS debe inyectar la línea de promoción en el mensaje de WhatsApp"

    # 7.D: Ausencia cuando la promo está inactiva o ausente
    ctx_inactive = build_base_context()
    inactive_prices = build_sample_price_list()
    inactive_prices["promocion_fecha"] = {
        "titulo": "Jornada Pasada",
        "activa": False,
        "escalas": []
    }
    ctx_inactive["web_content"]["lista_precios"] = inactive_prices
    html_inactive = template.render(**ctx_inactive)
    assert 'id="promo-banner-container"' not in html_inactive, "No debe renderizar #promo-banner-container si activa=False"
    print("  ✅ Banner de Jornada, píldoras de escalas, lógica JS de tachados y retrocompatibilidad verificadas al 100%.")

    # -------------------------------------------------------------------------
    # TEST 8: Promoción por Zonas / Combos y Regla de Acumulación
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Verificando Banner de Combo de Zonas, Píldoras y Lógica de Acumulación...")
    
    # 8.A: Renderizado con promocion_zonas activa y acumulable=True
    ctx_zonas_acum = build_base_context()
    prices_zonas_acum = build_sample_price_list()
    prices_zonas_acum["promocion_zonas"] = {
        "titulo": "Promo Combos de Zonas",
        "activa": True,
        "acumulable": True,
        "escalas": [
            {
                "cantidad": 2,
                "descuento": 10,
                "label": "2 zonas: 10% OFF"
            },
            {
                "cantidad": 3,
                "descuento": 20,
                "label": "3 o más zonas: 20% OFF"
            }
        ]
    }
    ctx_zonas_acum["web_content"]["lista_precios"] = prices_zonas_acum
    html_zonas_acum = template.render(**ctx_zonas_acum)

    # 1. Presencia del contenedor/badge de combo de zonas
    assert 'id="promo-zonas-container"' in html_zonas_acum, "Debe existir el contenedor #promo-zonas-container cuando hay promocion_zonas activa"
    assert 'Combo de Zonas' in html_zonas_acum, "Debe mostrar el badge 'Combo de Zonas'"
    assert 'Promo Combos de Zonas' in html_zonas_acum, "Debe mostrar el título de la promoción por zonas"
    assert 'id="promo-zonas-scales-list"' in html_zonas_acum, "Debe incluir el contenedor #promo-zonas-scales-list"

    # 2. Etiquetas de escalas y píldoras .promo-zone-pill
    assert 'promo-zone-pill' in html_zonas_acum, "Debe contener elementos con clase 'promo-zone-pill'"
    assert 'data-cantidad="2"' in html_zonas_acum, "Debe incluir data-cantidad='2' en la escala 1"
    assert 'data-descuento="10"' in html_zonas_acum, "Debe incluir data-descuento='10' en la escala 1"
    assert '2 zonas: 10% OFF' in html_zonas_acum, "Debe mostrar la etiqueta '2 zonas: 10% OFF'"
    assert 'data-cantidad="3"' in html_zonas_acum, "Debe incluir data-cantidad='3' en la escala 2"
    assert 'data-descuento="20"' in html_zonas_acum, "Debe incluir data-descuento='20' en la escala 2"
    assert '3 o más zonas: 20% OFF' in html_zonas_acum, "Debe mostrar la etiqueta '3 o más zonas: 20% OFF'"

    # 3. Indicador de acumulable
    assert '¡Acumulable con la Promo por Fecha!' in html_zonas_acum, "Debe mostrar el indicador de que es acumulable"

    # 8.B: Renderizado con promocion_zonas activa y acumulable=False
    ctx_zonas_no_acum = build_base_context()
    prices_zonas_no_acum = build_sample_price_list()
    prices_zonas_no_acum["promocion_zonas"] = {
        "titulo": "Promo Combos de Zonas",
        "activa": True,
        "acumulable": False,
        "escalas": [
            {
                "cantidad": 2,
                "descuento": 15,
                "label": "2 zonas: 15% OFF"
            }
        ]
    }
    ctx_zonas_no_acum["web_content"]["lista_precios"] = prices_zonas_no_acum
    html_zonas_no_acum = template.render(**ctx_zonas_no_acum)

    # Indicador de no acumulable
    assert 'No acumulable con otras promociones (aplica el mayor descuento)' in html_zonas_no_acum, \
        "Debe mostrar el indicador de que no es acumulable con otras promociones"

    # 8.C: Coexistencia con promocion_fecha activa
    ctx_both = build_base_context()
    prices_both = build_sample_price_list()
    prices_both["promocion_fecha"] = {
        "titulo": "Jornada Láser 17 de Noviembre",
        "activa": True,
        "escalas": [
            {"hasta": "2026-10-27", "hasta_display": "27 de Octubre de 2026", "descuento": 30, "label": "30% OFF"}
        ]
    }
    prices_both["promocion_zonas"] = prices_zonas_acum["promocion_zonas"]
    ctx_both["web_content"]["lista_precios"] = prices_both
    html_both = template.render(**ctx_both)
    assert 'id="promo-banner-container"' in html_both, "Debe coexistir #promo-banner-container"
    assert 'id="promo-zonas-container"' in html_both, "Debe coexistir #promo-zonas-container"

    # 8.D: Verificación de JavaScript: zoneDiscount, effectiveDiscount y regla de acumulación
    assert 'const promoZonasData =' in html_zonas_acum, "El script JS debe extraer promoZonasData"
    assert 'zoneDiscount' in html_zonas_acum, "El script JS debe calcular zoneDiscount"
    assert 'effectiveDiscount' in html_zonas_acum, "El script JS debe calcular effectiveDiscount"
    assert 'promoZonasData.acumulable' in html_zonas_acum, "El script JS debe verificar promoZonasData.acumulable"
    assert 'discountExplanation' in html_zonas_acum, "El script JS debe construir discountExplanation"
    assert 'Promociones aplicadas:' in html_zonas_acum, "El script JS debe formatear el mensaje con Promociones aplicadas cuando se acumulan"
    assert 'Mayor beneficio' in html_zonas_acum, "El script JS debe formatear la leyenda de Mayor beneficio cuando no se acumulan"

    # 8.E: Verificación de Actualización Reactiva de Precios en Filas y Tarjetas para Servicios Seleccionados
    assert 'function updateRowsAndCardsPrices' in html_zonas_acum, "El script JS debe definir updateRowsAndCardsPrices"
    assert '-${effectiveDiscount}% OFF' in html_zonas_acum, "El script JS debe formatear el badge de descuento para servicios seleccionados con -${effectiveDiscount}% OFF"
    assert 'selectedServices.has' in html_zonas_acum, "El script JS debe verificar selectedServices.has para actualizar las filas/tarjetas"
    assert 'updateMobileCardPrice(card, currentMobileCol)' in html_zonas_acum, "El script JS debe sincronizar las tarjetas móviles con currentMobileCol"

    # 8.F: Retrocompatibilidad cuando promocion_zonas está inactiva o ausente
    ctx_inactive_zonas = build_base_context()
    prices_inactive_zonas = build_sample_price_list()
    prices_inactive_zonas["promocion_zonas"] = {
        "titulo": "Promo Inactiva",
        "activa": False,
        "escalas": []
    }
    ctx_inactive_zonas["web_content"]["lista_precios"] = prices_inactive_zonas
    html_inactive_zonas = template.render(**ctx_inactive_zonas)
    assert 'id="promo-zonas-container"' not in html_inactive_zonas, "No debe renderizar #promo-zonas-container si activa=False"
    print("  ✅ Banner de Combo de Zonas, píldoras, badges de acumulación, lógica de cálculo y actualización reactiva de filas/tarjetas en JS verificados al 100%.")

    print("\n" + "=" * 75)
    print("🎉 TODAS LAS PRUEBAS FRONTEND DE LA ETAPA 1 PASARON CON ÉXITO (100% PASS)")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
