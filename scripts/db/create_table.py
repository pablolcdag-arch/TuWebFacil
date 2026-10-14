import sqlite3
import os
db_path = os.path.join('/var/www/tuwebfacil', 'messages.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS marketing_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_type TEXT,
    copy_text TEXT,
    design_description TEXT,
    status TEXT
)''')
conn.commit()
conn.close()
print("Table created successfully")
