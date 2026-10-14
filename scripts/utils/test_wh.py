import requests
import json

WEBHOOK_URL = "http://149.50.151.121:5002/webhook"
# Faking a webhook request for a message
def test_webhook():
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "5491100009999",
                        "type": "text",
                        "text": {"body": "2"} # 2 means "Editar Textos" in MAIN_MENU
                    }],
                    "contacts": [{"wa_id": "5491100009999", "profile": {"name": "Test User"}}]
                }
            }]
        }]
    }
    requests.post(WEBHOOK_URL, json=payload)
    
    # Send '1' to edit Title
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "1"
    requests.post(WEBHOOK_URL, json=payload)
    print("Requests sent.")

if __name__ == "__main__":
    test_webhook()
