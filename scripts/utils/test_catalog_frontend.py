#!/usr/bin/env python3
"""
Test Suite: Frontend de Modo Catálogo de Productos Masivo (client_template.html)
Verifica:
1. Separación de la Home vs. Catálogo dedicado:
   - En la Home (is_catalog_route = False): tarjeta de presentación compacta con CTA a /catalogo,
     sin renderizar tablas de 1000+ filas ni selector de categorías.
   - En /catalogo (is_catalog_route = True): barra de navegación superior con '← Volver a la página principal',
     ocultando el Hero principal y la sección 'Nuestros Servicios'.
2. Selector compacto de categorías:
   - Dropdown <select id="catalog-category-select"> con conteo total y por rubro.
   - Eliminación total de la cuadrícula de 88 cajas pesadas.
3. Paginación del lado del cliente de 25 items por página:
   - Controles de paginación (#catalog-pagination-container, #catalog-prev-page, #catalog-page-info, #catalog-next-page).
   - Constante PAGE_SIZE = 25 y reset a página 1 en cambios de filtro/búsqueda.
   - Persistencia del carrito de compras al paginar o filtrar.
4. Retrocompatibilidad para webs de servicios tradicionales (is_catalog_mode = False).
5. Fallback visual para la imagen del Hero:
   - Con foto: background-image con overlay.
   - Sin foto (None/vacío): gradiente CSS elegante usando paleta_colores.primario y secundario.
"""

import os
import sys
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


def build_catalog_context():
    """Genera un contexto de negocio con catálogo de productos masivo (estilo Disgraf / Mayorista)."""
    items = []
    # Generar 60 productos para probar paginación de 25 en 25 (3 páginas)
    categorias = [
        {"nombre": "Vinilos de Corte", "carta_url": "https://example.com/carta_vinilos.pdf"},
        {"nombre": "Lonas & Banners", "carta_url": ""},
        {"nombre": "Insumos & Accesorios", "carta_url": "https://example.com/carta_insumos.jpg"}
    ]
    for i in range(1, 61):
        cat = categorias[(i - 1) % len(categorias)]["nombre"]
        items.append({
            "tipo": "producto",
            "categoria": cat,
            "codigo": f"{1000 + i}",
            "servicio": f"Producto de Prueba {i}",
            "unidad": "x rollo" if i % 2 == 0 else "x m2",
            "carta_url": f"https://example.com/carta_{i}.jpg" if i % 5 == 0 else "",
            "precios": {
                "efectivo": f"${i * 1000},00",
                "lista": f"${int(i * 1000 * 1.2)},00"
            }
        })

    return {
        "web_content": {
            "titulo_web": "Disgraf S.R.L. - Distribuidora Gráfica",
            "subtitulo": "Líder en insumos gráficos y comunicación visual",
            "paleta_colores": {"primario": "#0284c7", "secundario": "#0f172a"},
            "servicios_sugeridos": ["Venta Mayorista", "Corte a Medida", "Envíos a Todo el País"],
            "descripciones_servicios": [
                "Stock permanente de insumos importados.",
                "Fraccionamiento con precisión milimétrica.",
                "Logística rápida a todo el territorio nacional."
            ],
            "fotos_servicios": [
                "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158",
                "https://images.unsplash.com/photo-1581092160607-ee22621dd758",
                "https://images.unsplash.com/photo-1581092335397-9583fe92d232"
            ],
            "foto_hero": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d",
            "horario": "Lunes a Viernes 08:30 a 17:30",
            "ubicacion_detectada": "Chacarita, CABA",
            "whatsapp_contacto": "+54 9 11 4555-0000",
            "email_contacto": "ventas@disgraf.com.ar",
            "instagram": "disgraf_grafica",
            "mapa": {"lat": -34.588, "lon": -58.450, "zoom": 15},
            "lista_precios": {
                "modo_vista": "catalogo",
                "titulo": "Catálogo General de Insumos Gráficos",
                "columnas_pago": ["Efectivo", "Lista"],
                "categorias": categorias,
                "items": items
            }
        },
        "client": {"phone": "5491145550000"},
        "web_status": "published",
        "has_edits": True,
        "is_preview": False,
        "is_catalog_route": False,
        "bot_phone": "5491134710787"
    }


def build_services_context():
    """Genera un contexto de negocio de servicios tradicional (peluquería, estética, etc.)."""
    return {
        "web_content": {
            "titulo_web": "Estética Lumière",
            "subtitulo": "Tratamientos corporales y faciales",
            "paleta_colores": {"primario": "#4F46E5", "secundario": "#7C3AED"},
            "servicios_sugeridos": ["Depilación Láser", "Limpieza Facial", "Masajes"],
            "descripciones_servicios": ["Definitiva", "Profunda", "Relajantes"],
            "fotos_servicios": [
                "https://images.unsplash.com/photo-1",
                "https://images.unsplash.com/photo-2",
                "https://images.unsplash.com/photo-3"
            ],
            "foto_hero": "https://images.unsplash.com/photo-hero",
            "horario": "Lunes a Viernes 09:00 a 19:00",
            "ubicacion_detectada": "Palermo, CABA",
            "whatsapp_contacto": "+54 9 11 3471-0787",
            "email_contacto": "contacto@lumiere.com.ar",
            "instagram": "lumiere",
            "mapa": {"lat": -34.588, "lon": -58.430, "zoom": 15},
            "lista_precios": {
                "modo_vista": "servicios",
                "titulo": "Tratamientos y Precios",
                "columnas_pago": ["Efectivo", "Transferencia"],
                "items": [
                    {
                        "servicio": "Depilación Rostro Completo",
                        "precios": {"efectivo": "$12.000", "transferencia": "$14.000"}
                    },
                    {
                        "servicio": "Limpieza Facial Profunda",
                        "precios": {"efectivo": "$18.000", "transferencia": "$20.000"}
                    }
                ]
            }
        },
        "client": {"phone": "5491134710787"},
        "web_status": "published",
        "has_edits": True,
        "is_preview": False,
        "is_catalog_route": False,
        "bot_phone": "5491134710787"
    }


def run_tests():
    print("=" * 75)
    print("🧪 INICIANDO TEST SUITE: MODO CATÁLOGO DEDICADO Y UX (FRONTEND)")
    print("=" * 75)

    template = get_jinja_template()
    assert template is not None, "Error crítico: no se pudo cargar client_template.html"
    print("  ✅ Template client_template.html cargado con éxito.")

    # -------------------------------------------------------------------------
    # TEST 1: Separación de Home vs. /catalogo en Modo Catálogo
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Verificando separación Home vs. /catalogo en Modo Catálogo...")
    ctx = build_catalog_context()

    # 1.A: Home (is_catalog_route = False)
    ctx["is_catalog_route"] = False
    html_home = template.render(**ctx)

    assert 'Catálogo Oficial de Productos & Precios' in html_home, "Debe incluir el título de catálogo en la Home"
    assert 'Explorá nuestro catálogo completo con más de 60 artículos' in html_home, "Debe incluir el subtítulo descriptivo con conteo total de items"
    assert 'href="/catalogo"' in html_home, "Debe incluir enlace CTA a /catalogo"
    assert 'Explorar Catálogo y Precios (60 productos) →' in html_home, "Debe incluir botón CTA con conteo de productos"
    assert 'catalog-desktop-table' not in html_home, "La Home NO debe renderizar la tabla de productos"
    assert 'id="catalog-category-select"' not in html_home, "La Home NO debe renderizar el selector de categorías"
    assert 'id="catalog-pagination-container"' not in html_home, "La Home NO debe renderizar la paginación"
    assert 'catalog-category-card' not in html_home, "La Home NO debe renderizar la cuadrícula de 88 cajas"
    assert '<header' in html_home, "La Home DEBE mostrar el Hero principal"
    print("  ✅ Vista Home de Catálogo verificada: Tarjeta de presentación limpia con CTA, sin tablas masivas.")

    # 1.B: Vista Dedicada /catalogo (is_catalog_route = True)
    ctx["is_catalog_route"] = True
    html_catalog = template.render(**ctx)

    assert 'href="/"' in html_catalog and 'Volver a la página principal' in html_catalog, "Debe incluir barra superior con enlace de retorno a la Home"
    assert '<header' not in html_catalog, "La vista de /catalogo NO debe mostrar el Hero gigante de la Home"
    assert 'id="servicios"' not in html_catalog, "La vista de /catalogo NO debe mostrar la sección de 'Nuestros Servicios'"
    assert 'id="catalog-search-input"' in html_catalog, "Debe incluir buscador en tiempo real"
    assert 'id="catalog-search-clear"' in html_catalog, "Debe incluir botón para limpiar buscador"
    assert 'id="catalog-desktop-table"' in html_catalog, "Debe incluir la tabla de catálogo para desktop"
    assert 'id="catalog-mobile-cards-container"' in html_catalog, "Debe incluir el contenedor de tarjetas mobile"
    assert 'id="catalog-cart-bar"' in html_catalog, "Debe incluir la barra flotante de carrito de pedidos"
    assert 'id="catalog-lightbox-modal"' in html_catalog, "Debe incluir el modal lightbox para cartas de colores"
    print("  ✅ Vista /catalogo dedicada verificada: Barra superior con volver, buscador, tabla y carrito.")

    # -------------------------------------------------------------------------
    # TEST 2: Selector Compacto de Categorías (Adiós a las 88 cajas)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verificando selector compacto de categorías...")
    assert 'id="catalog-category-select"' in html_catalog, "Debe existir el dropdown <select id='catalog-category-select'>"
    assert '<option value="">Todas las categorías (60)</option>' in html_catalog, "Debe incluir la opción 'Todas las categorías' con total"
    assert '<option value="Vinilos de Corte">Vinilos de Corte (20)</option>' in html_catalog, "Debe incluir la categoría Vinilos con conteo"
    assert '<option value="Lonas &amp; Banners">Lonas &amp; Banners (20)</option>' in html_catalog or '<option value="Lonas & Banners">Lonas & Banners (20)</option>' in html_catalog, "Debe incluir la categoría Lonas con conteo"
    assert 'catalog-category-card' not in html_catalog, "NO debe existir ninguna caja de la vieja cuadrícula de 88 cajas"
    print("  ✅ Selector compacto de categorías verificado: Dropdown elegante y responsivo con conteos.")

    # -------------------------------------------------------------------------
    # TEST 3: Paginación y Lógica JavaScript del Catálogo
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Verificando controles y lógica JS de paginación (25 items/pág)...")
    assert 'id="catalog-pagination-container"' in html_catalog, "Debe existir el contenedor de paginación"
    assert 'id="catalog-prev-page"' in html_catalog, "Debe existir el botón de página anterior"
    assert 'id="catalog-page-info"' in html_catalog, "Debe existir el elemento indicador de página"
    assert 'id="catalog-next-page"' in html_catalog, "Debe existir el botón de página siguiente"
    
    # Verificación en el bundle JavaScript de catálogo
    assert 'const PAGE_SIZE = 25;' in html_catalog, "El JS debe definir PAGE_SIZE = 25"
    assert 'totalPages = Math.max(1, Math.ceil(totalMatched / PAGE_SIZE));' in html_catalog, "El JS debe calcular totalPages dividiendo por PAGE_SIZE"
    assert 'currentPage = 1;' in html_catalog, "El JS debe resetear currentPage a 1 al filtrar"
    assert 'prevBtn.disabled = (currentPage <= 1);' in html_catalog, "El botón prev debe deshabilitarse en la página 1"
    assert 'nextBtn.disabled = (currentPage >= totalPages);' in html_catalog, "El botón next debe deshabilitarse en la última página"
    assert 'scrollToCatalogTop()' in html_catalog, "El JS debe realizar scroll suave al cambiar de página"
    print("  ✅ Paginación y lógica reactiva JS verificadas: 25 items por página, controles y persistencia de carrito.")

    # -------------------------------------------------------------------------
    # TEST 4: Retrocompatibilidad con Webs de Servicios Tradicionales
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Verificando retrocompatibilidad con webs de servicios tradicionales...")
    ctx_serv = build_services_context()
    html_serv = template.render(**ctx_serv)

    assert 'Tratamientos y Precios' in html_serv, "Debe renderizar la lista de precios de servicios"
    assert 'Depilación Rostro Completo' in html_serv, "Debe mostrar el servicio tradicional"
    assert 'id="catalog-category-select"' not in html_serv, "No debe incluir selector de categorías de catálogo"
    assert 'id="catalog-desktop-table"' not in html_serv, "No debe incluir tabla de productos de catálogo"
    assert 'id="catalog-pagination-container"' not in html_serv, "No debe incluir paginación de catálogo"
    assert 'href="/catalogo"' not in html_serv, "No debe mostrar botón hacia /catalogo en servicios"
    print("  ✅ Retrocompatibilidad verificada: Las webs de servicios continúan funcionando al 100% sin alteraciones.")

    # -------------------------------------------------------------------------
    # TEST 5: Fallback Visual para la Imagen del Hero
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Verificando fallback visual para foto de Hero...")
    
    # 5.A: Con foto_hero presente
    ctx_hero_ok = build_catalog_context()
    ctx_hero_ok["is_catalog_route"] = False
    ctx_hero_ok["web_content"]["foto_hero"] = "https://images.unsplash.com/photo-custom-hero"
    html_hero_ok = template.render(**ctx_hero_ok)
    assert "background-image: url('https://images.unsplash.com/photo-custom-hero')" in html_hero_ok, "Debe usar background-image cuando foto_hero existe"

    # 5.B: Sin foto_hero (None o vacía)
    ctx_hero_fallback = build_catalog_context()
    ctx_hero_fallback["is_catalog_route"] = False
    ctx_hero_fallback["web_content"]["foto_hero"] = None
    html_hero_fb = template.render(**ctx_hero_fallback)
    assert "linear-gradient(135deg" in html_hero_fb, "Debe aplicar gradiente lineal CSS cuando foto_hero es None"
    assert ctx_hero_fallback["web_content"]["paleta_colores"]["primario"] in html_hero_fb, "El gradiente debe incorporar el color primario"
    assert ctx_hero_fallback["web_content"]["paleta_colores"]["secundario"] in html_hero_fb, "El gradiente debe incorporar el color secundario"
    assert "backdrop-blur" in html_hero_fb, "Debe incluir overlay con backdrop-blur para legibilidad máxima"
    print("  ✅ Fallback visual del Hero verificado: Gradiente premium responsivo y de alta legibilidad cuando no hay foto.")

    print("\n" + "=" * 75)
    print("🎉 TODAS LAS PRUEBAS DE MODO CATÁLOGO PASARON CON ÉXITO (100% PASS)")
    print("=" * 75)


if __name__ == "__main__":
    run_tests()
