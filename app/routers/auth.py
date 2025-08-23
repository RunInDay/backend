# app/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query
from pydantic import BaseModel, EmailStr
import httpx
from app.settings import settings
from app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

AUTH_BASE = f"{settings.SUPABASE_URL}/auth/v1"
COMMON_HEADERS = {
    "apikey": settings.SUPABASE_ANON_KEY,
    "Content-Type": "application/json",
}
TIMEOUT = httpx.Timeout(5.0, connect=5.0)

# 요청/응답 모델
class SignupBody(BaseModel):
    email: EmailStr
    password: str
    data: dict | None = None
    redirect_to: str | None = None  # 이메일 확인 링크 리다이렉트

class ProfileData(BaseModel):
    nickname: str | None = None
    favorite: list[str] | None = None       # 관심사
    place_favorite: list[str] | None = None # 관심 장소
    profile_image: str | None = None     # 이미지 URL 또는 스토리지 경로

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class RefreshBody(BaseModel):
    refresh_token: str

class AuthTokens(BaseModel):
    access_token: str
    token_type: str | None = None
    expires_in: int | None = None
    refresh_token: str | None = None
    expires_at: int | None = None

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    nickname: str | None = None
    profile_image: str | None = None
    favorite: list[str] | None = None
    place_favorite: list[str] | None = None

def _pick_user_public(user: dict) -> UserPublic:
    meta = (user or {}).get("user_metadata", {}) or {}
    return UserPublic(
        id=user.get("id"),
        email=user.get("email"),
        nickname=meta.get("nickname"),
        profile_image=meta.get("profile_image"),           # 실제 응답 키에 맞춤
        favorite=meta.get("favorite"),
        place_favorite=meta.get("place_favorite"),
    )

def dump_data(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump(exclude_none=True)
    if isinstance(obj, dict):
        return {k: v for k, v in obj.items() if v is not None}
    return obj


# 회원가입 (프록시)
@router.post("/signup")
async def signup(
    body: SignupBody,
    include_user: bool = Query(False, description="true면 user 요약 포함"),
) -> dict:
    payload = {"email": body.email, "password": body.password}
    if body.data is not None:
        payload["data"] = dump_data(body.data)  # 앞서 만든 ProfileData 기준
    if body.redirect_to:
        payload["redirect_to"] = body.redirect_to

    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        r = await cx.post(f"{AUTH_BASE}/signup", headers=COMMON_HEADERS, json=payload)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)

    j = r.json()

    # signup 응답은 프로젝트 설정(이메일 확인 on/off)에 따라 토큰이 없을 수 있음
    out: dict = {}
    if "access_token" in j:
        out.update(AuthTokens(
            access_token=j.get("access_token"),
            token_type=j.get("token_type"),
            expires_in=j.get("expires_in"),
            expires_at=j.get("expires_at"),
            refresh_token=j.get("refresh_token"),
        ).model_dump(exclude_none=True))

    if include_user and j.get("user"):
        out["user"] = _pick_user_public(j["user"]).model_dump(exclude_none=True)

    # 토큰이 없다면 안내만 반환
    if not out:
        out = {"status": "pending_confirmation"}

    return out

@router.post("/login")
async def login(
    body: LoginBody,
    include_user: bool = Query(False, description="true면 user 요약 포함"),
) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        r = await cx.post(
            f"{AUTH_BASE}/token?grant_type=password",
            headers=COMMON_HEADERS,
            json={"email": body.email, "password": body.password},
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)

    j = r.json()
    out = AuthTokens(
        access_token=j.get("access_token"),
        token_type=j.get("token_type"),
        expires_in=j.get("expires_in"),
        expires_at=j.get("expires_at"),
        refresh_token=j.get("refresh_token"),
    ).model_dump(exclude_none=True)

    if include_user and j.get("user"):
        out["user"] = _pick_user_public(j["user"]).model_dump(exclude_none=True)

    return out

@router.post("/refresh")
async def refresh(body: RefreshBody):
    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        r = await cx.post(
            f"{AUTH_BASE}/token?grant_type=refresh_token",
            headers=COMMON_HEADERS,
            json={"refresh_token": body.refresh_token},
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    
    j = r.json()
    out = AuthTokens(
        access_token=j.get("access_token"),
        token_type=j.get("token_type"),
        expires_in=j.get("expires_in"),
        expires_at=j.get("expires_at"),
        refresh_token=j.get("refresh_token"),
    ).model_dump(exclude_none=True)
    return out

@router.post("/logout")
async def logout(authorization: str = Header(default="")):
    # 클라이언트가 보낸 access_token으로 세션 종료
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        r = await cx.post(f"{AUTH_BASE}/logout", headers={**COMMON_HEADERS, "Authorization": authorization})
    # 보통 204 No Content
    if r.status_code not in (200, 204):
        raise HTTPException(r.status_code, r.text)
    return {"ok": True}

@router.get("/me")
def me(ctx=Depends(get_current_user)):
    # 이미 구현해 둔 JWT 검증 디펜던시 사용
    return {"claims": ctx["claims"]}

@router.get("/user")
async def user(authorization: str = Header(default="")):
    # 토큰 서버측 유효성 확인(레거시 ES256일 때 안전)
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
        r = await cx.get(f"{AUTH_BASE}/user", headers={**COMMON_HEADERS, "Authorization": authorization})
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return r.json()