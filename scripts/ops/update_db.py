import sqlite3
import os

db_path = os.path.join(os.getcwd(), 'messages.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Add columns to marketing_content
try:
    c.execute("ALTER TABLE marketing_content ADD COLUMN canva_prompt TEXT")
except Exception as e:
    print("canva_prompt:", e)

try:
    c.execute("ALTER TABLE marketing_content ADD COLUMN scheduled_for DATETIME")
except Exception as e:
    print("scheduled_for:", e)

# Create marketing_settings table
c.execute('''
    CREATE TABLE IF NOT EXISTS marketing_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_text TEXT,
        hashtags TEXT,
        image_keywords TEXT
    )
''')

# Insert default row if empty
c.execute("SELECT COUNT(*) FROM marketing_settings")
if c.fetchone()[0] == 0:
    default_prompt = """Sos el Community Manager y Copywriter Experto de "TuWebLista". Tu objetivo principal es redactar contenido persuasivo, dinámico y atractivo para redes sociales que convierta seguidores en clientes. Español de Argentina (usá el "vos"). Profesional, empático, claro y muy directo. Escribí un texto extremadamente CORTO para acompañar la imagen, máximo 3 oraciones."""
    default_hashtags = "#TuWebLista #VenderMas #NegocioLocal #DisenoWebArgentina"
    default_image = "Diseño profesional y minimalista con estética de WhatsApp (tonos verdes y blancos). En el centro, un smartphone moderno mostrando una página web. Texto principal atractivo."
    
    c.execute("INSERT INTO marketing_settings (prompt_text, hashtags, image_keywords) VALUES (?, ?, ?)", 
              (default_prompt, default_hashtags, default_image))

conn.commit()
conn.close()
print("DB Updated")
