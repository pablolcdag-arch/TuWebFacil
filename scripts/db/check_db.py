import os
import requests
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

headers = {"apikey": key, "Authorization": f"Bearer {key}"}
res = requests.get(f"{url}/rest/v1/", headers=headers)
print(res.status_code)
print(res.text)

