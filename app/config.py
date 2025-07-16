import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Loads configuration settings from environment variables.
    """
    # Supabase
    SUPABASE_URL: str | None = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str | None = os.getenv("SUPABASE_KEY")
    SUPABASE_SECRET: str | None = os.getenv("SUPABASE_SECRET")

    # AI Services
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    # WhatsApp (for later sprints)
    WHATSAPP_TOKEN: str | None = os.getenv("WHATSAPP_TOKEN")
    VERIFY_TOKEN: str | None = os.getenv("VERIFY_TOKEN")

    # Check that critical variables are set
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set in the environment.")
    
				# Default to False for production safety
    DEV_MODE: bool = os.getenv("DEV_MODE", "false").lower() in ('true', '1', 't')
    
