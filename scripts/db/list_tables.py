import os
import requests
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

headers = {"apikey": key, "Authorization": f"Bearer {key}"}
# Query the pg_catalog via REST to list tables
res = requests.get(f"{url}/rest/v1/", headers=headers)
print(res.json())

