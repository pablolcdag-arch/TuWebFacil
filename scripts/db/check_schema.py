import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    print("websites:", supabase.table("websites").select("*").limit(1).execute().data)
    print("website_content:", supabase.table("website_content").select("*").limit(1).execute().data)
except Exception as e:
    print("Error:", e)
