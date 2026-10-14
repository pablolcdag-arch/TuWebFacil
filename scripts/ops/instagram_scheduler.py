import os
import sqlite3
import time
import datetime
import logging
from dotenv import load_dotenv

# Asegurar que estamos en el root del proyecto para cargar las env y paths
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
load_dotenv()

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] SCHEDULER: %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)

# Tenemos que importar la función de post_to_instagram de app.py sin inicializar flask
# Como app.py está en el root, podemos agregarlo al sys.path
import sys
sys.path.append(os.getcwd())
try:
    from instagram_auto_poster import post_to_instagram
except ImportError:
    logging.error("No se pudo importar post_to_instagram de instagram_auto_poster.py")
    sys.exit(1)

def run_scheduler():
    db_path = os.path.join(os.getcwd(), 'messages.db')
    logging.info(f"Iniciando Instagram Scheduler. DB: {db_path}")
    
    while True:
        try:
            if not os.path.exists(db_path):
                logging.warning("No se encontró la base de datos aún.")
                time.sleep(60)
                continue
                
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # Buscar posteos programados que ya hayan pasado la fecha/hora actual y estén en estado 'scheduled'
            current_time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
            
            c.execute("SELECT id, copy_text, design_description FROM marketing_content WHERE status = 'scheduled' AND scheduled_for <= ?", (current_time,))
            posts_to_publish = c.fetchall()
            
            for post in posts_to_publish:
                post_id, caption, image_url = post
                logging.info(f"Publicando post programado ID: {post_id}")
                
                success = post_to_instagram(image_url, caption)
                if success:
                    c.execute("UPDATE marketing_content SET status = 'published' WHERE id = ?", (post_id,))
                    conn.commit()
                    logging.info(f"Post {post_id} publicado con éxito.")
                else:
                    # En caso de error lo marcamos como error para que no intente infinitamente (o lo dejamos scheduled, mejor 'error')
                    c.execute("UPDATE marketing_content SET status = 'error_publish' WHERE id = ?", (post_id,))
                    conn.commit()
                    logging.error(f"Error al publicar el post {post_id}.")
            
            conn.close()
            
        except Exception as e:
            logging.error(f"Error en el ciclo del scheduler: {e}")
            
        # Esperar un minuto antes de la próxima revisión
        time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
