import json

data = {
    "entry": [{
        "changes": [{
            "value": {
                "contacts": [{"wa_id": "54911999900QA", "profile": {"name": "QA_NAME"}}],
                "messages": [{"from": "54911999900QA", "type": "text", "text": {"body": "Hola bot, quiero probar edición"}}]
            }
        }]
    }]
}

try:
    if 'messages' in data['entry'][0]['changes'][0]['value']:
        mensaje_obj = data['entry'][0]['changes'][0]['value']['messages'][0]
        contacto_obj_list = data['entry'][0]['changes'][0]['value'].get('contacts', [])
        contacto_obj = contacto_obj_list[0] if contacto_obj_list else {}
        
        wa_id = contacto_obj.get('wa_id', mensaje_obj.get('from', ''))
        nombre = contacto_obj.get('profile', {}).get('name', 'Usuario')
        
        msg_type = mensaje_obj.get('type', 'text')
        media_id = None
        
        print("Success!", wa_id, nombre, msg_type, mensaje_obj['text']['body'])
    else:
        print("No messages")
except Exception as e:
    print("Error:", e)
