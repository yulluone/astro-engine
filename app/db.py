# /app/db.py
from supabase import create_client, Client
from .config import Config

if not Config.SUPABASE_KEY or not Config.SUPABASE_URL or not Config.SUPABASE_SECRET:
	raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
supabase_admin: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SECRET)