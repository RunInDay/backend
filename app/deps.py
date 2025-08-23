# backend-fastapi/app/deps.py
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from jwt import PyJWKClient
import jwt
from app.settings import settings
from supabase import create_client, Client

security = HTTPBearer(auto_error=True)
_jwk_client = PyJWKClient(settings.SUPABASE_JWKS_URL)

def get_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return auth.split(" ", 1)[1].strip()

def supabase_as_user(token: str) -> Client:
    supa = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    # RLS 평가에 유저 토큰 사용
    supa.postgrest.auth(token)
    return supa

def supabase_admin() -> Client:
    # 관리자/배치 전용. 외부 요청 경로에 노출 금지.
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

def get_current_user(token: str = Depends(get_bearer_token)):
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            audience=None,
            options={"verify_aud": False}
        )
        # payload 예시: {'sub': '<uuid>', 'email': '...', 'role': 'authenticated', ...}
        return {"token": token, "claims": payload}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")
