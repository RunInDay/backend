import os
from dotenv import load_dotenv
from supabase import create_client, Client
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / '.env')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# 권한별 클라 분리
supabase_anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)      # 일반 사용자 인증/조회 시
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)      # 회원 생성이나 삭제 시