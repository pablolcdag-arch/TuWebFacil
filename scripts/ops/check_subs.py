import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    res = supabase.table("subscriptions").select("*").limit(1).execute()
    print("Subscriptions exists:", res.data)
except Exception as e:
    print("Error:", e)
