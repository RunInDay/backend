import os
from dotenv import load_dotenv
from supabase import create_client
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / '.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
