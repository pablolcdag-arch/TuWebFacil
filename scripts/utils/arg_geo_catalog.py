#!/usr/bin/env python3
"""
scripts/utils/arg_geo_catalog.py
Catálogo Geográfico Jerárquico de Argentina optimizado para búsquedas en Google Places API.
Organiza zonas por barrios de Capital Federal, partidos del Conurbano Bonaerense,
capitales provinciales, ciudades cabecera y macro-zona nacional consolidada.
"""

# ==============================================================================
# 1. CABA: Los 48 barrios oficiales de la Ciudad Autónoma de Buenos Aires
# ==============================================================================
CABA = [
    "Agronomía, CABA", "Almagro, CABA", "Balvanera, CABA", "Barracas, CABA", "Belgrano, CABA",
    "Boedo, CABA", "Caballito, CABA", "Chacarita, CABA", "Coghlan, CABA", "Colegiales, CABA",
    "Constitución, CABA", "Flores, CABA", "Floresta, CABA", "La Boca, CABA", "La Paternal, CABA",
    "Liniers, CABA", "Mataderos, CABA", "Monte Castro, CABA", "Monserrat, CABA", "Nueva Pompeya, CABA",
    "Núñez, CABA", "Palermo, CABA", "Parque Avellaneda, CABA", "Parque Chacabuco, CABA", "Parque Chas, CABA",
    "Parque Patricios, CABA", "Puerto Madero, CABA", "Recoleta, CABA", "Retiro, CABA", "Saavedra, CABA",
    "San Cristóbal, CABA", "San Nicolás, CABA", "San Telmo, CABA", "Vélez Sársfield, CABA", "Versalles, CABA",
    "Villa Crespo, CABA", "Villa del Parque, CABA", "Villa Devoto, CABA", "Villa General Mitre, CABA",
    "Villa Lugano, CABA", "Villa Luro, CABA", "Villa Ortúzar, CABA", "Villa Pueyrredón, CABA", "Villa Real, CABA",
    "Villa Riachuelo, CABA", "Villa Santa Rita, CABA", "Villa Soldati, CABA", "Villa Urquiza, CABA"
]

# ==============================================================================
# 2. GBA: Los 35 principales partidos y subzonas clave del Gran Buenos Aires
# ==============================================================================
GBA = [
    "Vicente López, Buenos Aires", "San Isidro, Buenos Aires", "San Fernando, Buenos Aires",
    "Tigre, Buenos Aires", "San Martín, Buenos Aires", "Tres de Febrero, Buenos Aires",
    "Morón, Buenos Aires", "Hurlingham, Buenos Aires", "Ituzaingó, Buenos Aires",
    "Merlo, Buenos Aires", "Moreno, Buenos Aires", "Ramos Mejía, Buenos Aires",
    "San Justo, Buenos Aires", "La Matanza, Buenos Aires", "Avellaneda, Buenos Aires",
    "Lanús, Buenos Aires", "Quilmes, Buenos Aires", "Berazategui, Buenos Aires",
    "Florencio Varela, Buenos Aires", "Almirante Brown, Buenos Aires", "Esteban Echeverría, Buenos Aires",
    "Ezeiza, Buenos Aires", "Lomas de Zamora, Buenos Aires", "Banfield, Buenos Aires",
    "Temperley, Buenos Aires", "San Miguel, Buenos Aires", "Malvinas Argentinas, Buenos Aires",
    "José C. Paz, Buenos Aires", "Pilar, Buenos Aires", "Escobar, Buenos Aires",
    "General Rodríguez, Buenos Aires", "Cañuelas, Buenos Aires", "San Vicente, Buenos Aires",
    "Presidente Perón, Buenos Aires", "Ensenada, Buenos Aires"
]

# ==============================================================================
# 3. SANTA FE: Rosario (barrios clave), Santa Fe Capital y ciudades cabecera
# ==============================================================================
SANTA_FE = [
    # Rosario
    "Centro, Rosario, Santa Fe", "Pichincha, Rosario, Santa Fe", "Echesortu, Rosario, Santa Fe",
    "Barrio Martin, Rosario, Santa Fe", "Alberdi, Rosario, Santa Fe", "Fisherton, Rosario, Santa Fe",
    # Santa Fe Capital
    "Centro, Santa Fe Capital, Santa Fe", "Recoleta, Santa Fe Capital, Santa Fe",
    "Candioti, Santa Fe Capital, Santa Fe", "Barrio Sur, Santa Fe Capital, Santa Fe",
    "Guadalupe, Santa Fe Capital, Santa Fe",
    # Ciudades cabecera
    "Rafaela, Santa Fe", "Venado Tuerto, Santa Fe", "Reconquista, Santa Fe",
    "Esperanza, Santa Fe", "Santo Tomé, Santa Fe", "San Lorenzo, Santa Fe",
    "Villa Gobernador Gálvez, Santa Fe", "Casilda, Santa Fe", "Cañada de Gómez, Santa Fe"
]

# ==============================================================================
# 4. CORDOBA: Córdoba Capital (barrios clave) y ciudades cabecera
# ==============================================================================
CORDOBA = [
    # Córdoba Capital
    "Centro, Córdoba", "Nueva Córdoba, Córdoba", "Güemes, Córdoba",
    "Cerro de las Rosas, Córdoba", "General Paz, Córdoba", "Alta Córdoba, Córdoba",
    "Alberdi, Córdoba", "Urca, Córdoba", "Cofico, Córdoba", "Villa Belgrano, Córdoba",
    # Ciudades cabecera
    "Río Cuarto, Córdoba", "Villa María, Córdoba", "Carlos Paz, Córdoba",
    "San Francisco, Córdoba", "Alta Gracia, Córdoba", "Bell Ville, Córdoba",
    "Río Tercero, Córdoba", "Jesús María, Córdoba", "Villa Dolores, Córdoba",
    "Marcos Juárez, Córdoba"
]

# ==============================================================================
# 5. MENDOZA: Gran Mendoza y ciudades cabecera
# ==============================================================================
MENDOZA = [
    "Centro, Mendoza", "Quinta Sección, Mendoza", "Sexta Sección, Mendoza",
    "Godoy Cruz, Mendoza", "Guaymallén, Mendoza", "Las Heras, Mendoza",
    "Luján de Cuyo, Mendoza", "Chacras de Coria, Mendoza", "Maipú, Mendoza",
    "San Rafael, Mendoza", "San Martín, Mendoza", "Tunuyán, Mendoza",
    "Rivadavia, Mendoza", "General Alvear, Mendoza"
]

# ==============================================================================
# 6. TUCUMAN: San Miguel de Tucumán y ciudades clave
# ==============================================================================
TUCUMAN = [
    "Centro, San Miguel de Tucumán", "Barrio Norte, San Miguel de Tucumán",
    "Barrio Sur, San Miguel de Tucumán", "Yerba Buena, Tucumán",
    "Concepción, Tucumán", "Tafí Viejo, Tucumán", "Banda del Río Salí, Tucumán",
    "Aguilares, Tucumán"
]

# ==============================================================================
# 7. BUENOS AIRES INTERIOR: La Plata, Mar del Plata y cabeceras del interior bonaerense
# ==============================================================================
BUENOS_AIRES_INTERIOR = [
    "Centro, La Plata, Buenos Aires", "City Bell, La Plata, Buenos Aires", "Tolosa, La Plata, Buenos Aires",
    "Los Hornos, La Plata, Buenos Aires", "Centro, Mar del Plata, Buenos Aires", "Playa Grande, Mar del Plata, Buenos Aires",
    "Güemes, Mar del Plata, Buenos Aires", "La Perla, Mar del Plata, Buenos Aires", "Bahía Blanca, Buenos Aires",
    "Tandil, Buenos Aires", "San Nicolás de los Arroyos, Buenos Aires", "Pergamino, Buenos Aires",
    "Olavarría, Buenos Aires", "Junín, Buenos Aires", "Zárate, Buenos Aires",
    "Campana, Buenos Aires", "Necochea, Buenos Aires", "Chivilcoy, Buenos Aires",
    "Mercedes, Buenos Aires", "Azul, Buenos Aires"
]

# ==============================================================================
# 8. RESTO DE PROVINCIAS: Capitales y principales urbes de las 23 provincias
# ==============================================================================
RESTO_PROVINCIAS = [
    # Salta
    "Salta Capital, Salta", "San Ramón de la Nueva Orán, Salta", "Tartagal, Salta", "Cafayate, Salta",
    # Jujuy
    "San Salvador de Jujuy, Jujuy", "San Pedro de Jujuy, Jujuy", "Palpalá, Jujuy", "Perico, Jujuy",
    # San Juan
    "San Juan Capital, San Juan", "Rawson, San Juan", "Rivadavia, San Juan", "Chimbas, San Juan", "Caucete, San Juan",
    # Entre Ríos
    "Paraná, Entre Ríos", "Concordia, Entre Ríos", "Gualeguaychú, Entre Ríos", "Concepción del Uruguay, Entre Ríos", "Gualeguay, Entre Ríos", "Colón, Entre Ríos",
    # Corrientes
    "Corrientes Capital, Corrientes", "Goya, Corrientes", "Paso de los Libres, Corrientes", "Curuzú Cuatiá, Corrientes", "Mercedes, Corrientes",
    # Misiones
    "Posadas, Misiones", "Oberá, Misiones", "Eldorado, Misiones", "Puerto Iguazú, Misiones", "Apóstoles, Misiones",
    # Chaco
    "Resistencia, Chaco", "Presidencia Roque Sáenz Peña, Chaco", "Villa Ángela, Chaco", "Barranqueras, Chaco", "Fontana, Chaco",
    # Formosa
    "Formosa Capital, Formosa", "Clorinda, Formosa", "Pirané, Formosa",
    # Santiago del Estero
    "Santiago del Estero Capital, Santiago del Estero", "La Banda, Santiago del Estero", "Termas de Río Hondo, Santiago del Estero", "Frías, Santiago del Estero",
    # Catamarca
    "San Fernando del Valle de Catamarca, Catamarca", "Valle Viejo, Catamarca", "Tinogasta, Catamarca",
    # La Rioja
    "La Rioja Capital, La Rioja", "Chilecito, La Rioja", "Chamical, La Rioja",
    # San Luis
    "San Luis Capital, San Luis", "Villa Mercedes, San Luis", "Merlo, San Luis",
    # Neuquén
    "Neuquén Capital, Neuquén", "San Martín de los Andes, Neuquén", "Cutral Có, Neuquén", "Plottier, Neuquén", "Zapala, Neuquén", "Villa La Angostura, Neuquén",
    # Río Negro
    "Bariloche, Río Negro", "General Roca, Río Negro", "Cipolletti, Río Negro", "Viedma, Río Negro", "Villa Regina, Río Negro",
    # Chubut
    "Comodoro Rivadavia, Chubut", "Trelew, Chubut", "Puerto Madryn, Chubut", "Rawson, Chubut", "Esquel, Chubut",
    # Santa Cruz
    "Río Gallegos, Santa Cruz", "Caleta Olivia, Santa Cruz", "El Calafate, Santa Cruz", "Pico Truncado, Santa Cruz",
    # Tierra del Fuego
    "Ushuaia, Tierra del Fuego", "Río Grande, Tierra del Fuego",
    # La Pampa
    "Santa Rosa, La Pampa", "General Pico, La Pampa", "Toay, La Pampa"
]

# ==============================================================================
# 9. ARGENTINA: Macro-zona nacional consolidada y ordenada (~250 nodos)
# ==============================================================================
def _consolidar_argentina():
    zonas = []
    zonas.extend(CABA)
    zonas.extend(GBA)
    zonas.extend(CORDOBA)
    zonas.extend(SANTA_FE)
    zonas.extend(MENDOZA)
    zonas.extend(TUCUMAN)
    zonas.extend(BUENOS_AIRES_INTERIOR)
    zonas.extend(RESTO_PROVINCIAS)
    
    # Preservar orden eliminando posibles duplicados
    vistas = set()
    resultado = []
    for z in zonas:
        if z not in vistas:
            vistas.add(z)
            resultado.append(z)
    return resultado

ARGENTINA = _consolidar_argentina()

# Diccionario maestro de mapeo
CATALOGO_ZONAS = {
    "argentina": ARGENTINA,
    "caba": CABA,
    "gba": GBA,
    "cordoba": CORDOBA,
    "santa_fe": SANTA_FE,
    "mendoza": MENDOZA,
    "tucuman": TUCUMAN,
    "buenos_aires_interior": BUENOS_AIRES_INTERIOR,
    "resto_provincias": RESTO_PROVINCIAS
}

# ==============================================================================
# 10. Presets informativos para APIs y UI
# ==============================================================================
PRESETS = [
    {
        "id": "argentina",
        "nombre": "Argentina Completa",
        "total_zonas": len(ARGENTINA),
        "descripcion": f"Barrido federal completo ({len(ARGENTINA)} zonas de todo el país)"
    },
    {
        "id": "caba",
        "nombre": "CABA (Capital Federal)",
        "total_zonas": len(CABA),
        "descripcion": f"Los {len(CABA)} barrios oficiales porteños"
    },
    {
        "id": "gba",
        "nombre": "Gran Buenos Aires (GBA)",
        "total_zonas": len(GBA),
        "descripcion": f"{len(GBA)} partidos y subzonas clave del conurbano bonaerense"
    },
    {
        "id": "cordoba",
        "nombre": "Córdoba",
        "total_zonas": len(CORDOBA),
        "descripcion": f"Córdoba Capital ({len(CORDOBA)} zonas y cabeceras provinciales)"
    },
    {
        "id": "santa_fe",
        "nombre": "Santa Fe & Rosario",
        "total_zonas": len(SANTA_FE),
        "descripcion": f"Rosario ({len(SANTA_FE)} zonas, Santa Fe Capital y cabeceras)"
    },
    {
        "id": "mendoza",
        "nombre": "Mendoza",
        "total_zonas": len(MENDOZA),
        "descripcion": f"Gran Mendoza y cabeceras provinciales ({len(MENDOZA)} zonas)"
    },
    {
        "id": "tucuman",
        "nombre": "Tucumán",
        "total_zonas": len(TUCUMAN),
        "descripcion": f"San Miguel de Tucumán y ciudades clave ({len(TUCUMAN)} zonas)"
    },
    {
        "id": "buenos_aires_interior",
        "nombre": "Buenos Aires Interior",
        "total_zonas": len(BUENOS_AIRES_INTERIOR),
        "descripcion": f"La Plata, Mar del Plata, Bahía Blanca y más ({len(BUENOS_AIRES_INTERIOR)} zonas)"
    }
]

def obtener_zonas_por_clave(clave: str):
    """
    Retorna la lista de consultas geográficas para una clave dada.
    Si la clave no está en el catálogo, pero es una ubicación puntual ingresada por el usuario,
    la retorna como una lista de un único elemento.
    """
    if not clave:
        return []
    
    clave_norm = str(clave).strip().lower().replace("-", "_")
    if clave_norm in CATALOGO_ZONAS:
        return list(CATALOGO_ZONAS[clave_norm])
    
    # Manejo de aliases comunes
    aliases = {
        "capital_federal": "caba",
        "capital": "caba",
        "buenos_aires": "caba",
        "conurbano": "gba",
        "rosario": "santa_fe",
        "santafe": "santa_fe",
        "cba": "cordoba"
    }
    if clave_norm in aliases:
        return list(CATALOGO_ZONAS[aliases[clave_norm]])
        
    # Zona personalizada (ej: "Palermo, CABA" o "Mar del Plata")
    return [str(clave).strip()]

def obtener_presets():
    """Retorna la lista de presets disponibles para el barrido."""
    return PRESETS
