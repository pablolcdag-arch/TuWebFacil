import bot_engine

# Simular mensaje 1: "cancelar"
print("Enviando 'cancelar'")
bot_engine.procesar_mensaje("54911999900QA", "cancelar", "QA Test")

# Simular mensaje 2: "quiero confirmar mi web"
print("Enviando 'Hola bot, quiero probar edición'")
bot_engine.procesar_mensaje("54911999900QA", "Hola bot, quiero probar edición", "QA Test")

# Simular mensaje 3: "1"
print("Enviando '1'")
bot_engine.procesar_mensaje("54911999900QA", "1", "QA Test")

# Simular mensaje 4: "1"
print("Enviando '1'")
bot_engine.procesar_mensaje("54911999900QA", "1", "QA Test")

# Simular mensaje 5: "Título Editado por QA Automático"
print("Enviando 'Título...'")
bot_engine.procesar_mensaje("54911999900QA", "Título Editado por QA Automático", "QA Test")
