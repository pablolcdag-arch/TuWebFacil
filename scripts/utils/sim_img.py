from bot_engine import procesar_mensaje
import time
wa_id = "5491134710787"
print("1. Enviar menu")
procesar_mensaje(wa_id, "menu", "Test")
time.sleep(0.5)

print("\n2. Enviar Editar Imagenes")
procesar_mensaje(wa_id, "6", "Test", msg_type="interactive")
time.sleep(0.5)

print("\n3. Enviar Imagen")
# Simular webhook de imagen
procesar_mensaje(wa_id, "", "Test", msg_type="image", media_id="test_media_123")
time.sleep(0.5)

print("\n4. Seleccionar FOTO_HERO")
procesar_mensaje(wa_id, "FOTO_HERO", "Test", msg_type="interactive")

