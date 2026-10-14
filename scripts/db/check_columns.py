import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

res = supabase.table("payments").insert({"client_id": "ef54e8f6-e777-473c-a918-dfd967878689"}).execute()
print(res)
