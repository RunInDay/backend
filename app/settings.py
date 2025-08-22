from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv(path=".env")

class Settings(BaseModel):
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_JWKS_URL: str = os.getenv("SUPABASE_JWKS_URL", "")
    APP_ENV: str = os.getenv("APP_ENV", "local")
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()
