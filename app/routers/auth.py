# auth.py
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional
from starlette.status import (
    HTTP_201_CREATED,
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)


from supabase import create_client, Client
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------- Supabase Client ----------
def get_clients() -> tuple[Client, Client | None]:
    url = settings.SUPABASE_URL
    if not url:
        raise RuntimeError("SUPABASE_URL is missing")

    public_key = settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY
    if not public_key:
        raise RuntimeError("No Supabase key found (ANON/SERVICE_ROLE)")
    supabase_public = create_client(url, public_key)

    supabase_admin = create_client(url, settings.SUPABASE_SERVICE_ROLE_KEY) if settings.SUPABASE_SERVICE_ROLE_KEY else None
    return supabase_public, supabase_admin

supabase, supabase_admin = get_clients()


# ---------- Schemas ----------
class SignUpIn(BaseModel):
    email: EmailStr
    password: str
    username: str
    image: Optional[str] = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: str
    email: EmailStr
    username: Optional[str] = None
    image: Optional[str] = None
    is_verified: bool = False

class UpdateMeIn(BaseModel):
    # user_metadata
    username: Optional[str] = None
    image: Optional[str] = None

class ConfirmDeleteIn(BaseModel):
    password: str

class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str

class ResetRequestIn(BaseModel):
    email: EmailStr
    redirect_to: Optional[str] = None

class ResetConfirmIn(BaseModel):
    new_password: str


# ---------- Helpers ----------
def _pick_user_out(user: dict, is_verified: bool = False) -> UserOut:
    meta = (user or {}).get("user_metadata", {}) or {}
    return UserOut(
        id=user.get("id"),
        email=user.get("email"),
        username=meta.get("username"),
        image=meta.get("image"),
        is_verified=is_verified,
    )

def _options_with_metadata(username: str, image: Optional[str]):
    # supabase-py v2: sign_up({ email, password, options={"data": {...}} })
    return {"data": {"username": username, "image": image}}

def _ensure_profiles_row(user_id: str):
    """
    profiles 테이블에 user_id 고유행 upsert (running_data_id=None, is_verified=False)
    """
    try:
        supabase.table("profiles").upsert(
            {"user_id": user_id, "running_data_id": None, "is_verified": False},
            on_conflict="user_id"
        ).execute()
    except Exception:
        # 테이블 미구성/컬럼 불일치 시 조용히 패스(필요하면 로깅)
        pass

def _get_is_verified(user_id: str) -> bool:
    try:
        res = supabase.table("profiles").select("is_verified").eq("user_id", user_id).limit(1).execute()
        if res.data and isinstance(res.data, list):
            return bool(res.data[0].get("is_verified", False))
    except Exception:
        pass
    return False


# ---------- Dependencies ----------
def get_current_user(authorization: str = Header(default="")) -> UserOut:
    """
    Authorization: Bearer <access_token>로 현재 사용자 확인
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Missing or invalid Authorization header")

    jwt = authorization.split(" ", 1)[1].strip()
    try:
        user_resp = supabase.auth.get_user(jwt)
        user = getattr(user_resp, "user", None)
        if not user:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Invalid token")

        # profiles에서 is_verified 조회
        is_verified = False
        try:
            res = supabase.table("profiles").select("is_verified").eq("user_id", user.id).limit(1).execute()
            if res.data and isinstance(res.data, list):
                is_verified = bool(res.data[0].get("is_verified", False))
        except Exception:
            pass

        return _pick_user_out({"id": user.id, "email": user.email, "user_metadata": user.user_metadata}, is_verified)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Token verification failed")


# ---------- Routes ----------
@router.post("/signup", response_model=UserOut, status_code=HTTP_201_CREATED)
def signup(payload: SignUpIn):
    """
    Supabase Auth 회원가입 + profiles 기본행 upsert
    """
    try:
        resp = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
            "options": _options_with_metadata(payload.username, payload.image),
        })
        user = getattr(resp, "user", None)
        if not user:
            raise HTTPException(HTTP_400_BAD_REQUEST, "Sign up failed")

        _ensure_profiles_row(user.id)
        return _pick_user_out({"id": user.id, "email": user.email, "user_metadata": user.user_metadata}, False)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, f"Sign up error: {e}")


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn):
    """
    로그인 → access_token / refresh_token 반환
    """
    try:
        resp = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password
        })
        session = getattr(resp, "session", None) or resp
        access_token = getattr(session, "access_token", None)
        refresh_token = getattr(session, "refresh_token", None)
        if not access_token or not refresh_token:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Invalid credentials")
        return TokenOut(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Invalid credentials")


@router.post("/logout", status_code=HTTP_200_OK)
def logout(authorization: str = Header(default=""), refresh_token: Optional[str] = None):
    """
    로그아웃: refresh_token 기반으로 세션 무효화 시도 (멱등 처리)
    """
    try:
        if refresh_token:
            supabase.auth.refresh_session(refresh_token=refresh_token)
        supabase.auth.sign_out()
        return {"ok": True}
    except Exception:
        return {"ok": True}


class RefreshIn(BaseModel):
    refresh_token: str

@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn):
    """
    refresh_token으로 새 access_token/refresh_token 발급
    """
    try:
        resp = supabase.auth.refresh_session(refresh_token=payload.refresh_token)
        session = getattr(resp, "session", None) or resp
        access_token = getattr(session, "access_token", None)
        refresh_token = getattr(session, "refresh_token", None)
        if not access_token or not refresh_token:
            raise HTTPException(HTTP_401_UNAUTHORIZED, "Refresh failed")
        return TokenOut(access_token=access_token, refresh_token=refresh_token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Refresh failed")


@router.get("/me", response_model=UserOut)
def me(current: UserOut = Depends(get_current_user)):
    """
    현재 토큰 기준 사용자 정보 조회
    """
    return current

@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UpdateMeIn,
    current: UserOut = Depends(get_current_user),
):
    """
    - username / image → Supabase user_metadata (admin.update_user_by_id)
    """
    # 1) auth 영역 변경(메타데이터)
    attributes = {}
    meta_updates = {}

    if payload.username is not None:
        meta_updates["username"] = payload.username
    if payload.image is not None:
        meta_updates["image"] = payload.image
    if meta_updates:
        attributes["user_metadata"] = meta_updates

    if attributes:
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            # 세션 기반 update_user를 서버에서 처리하려면 사용자 세션을 유지해야 해서 권장 X
            raise HTTPException(
                HTTP_400_BAD_REQUEST,
                "Server cannot update auth fields without SERVICE_ROLE key"
            )
        try:
            supabase.auth.admin.update_user_by_id(current.id, attributes=attributes)
        except Exception as e:
            raise HTTPException(HTTP_400_BAD_REQUEST, f"Auth update failed: {e}")

    # 최신값으로 응답 구성
    new_username = payload.username or current.username
    new_image = payload.image or current.image
    is_verified = _get_is_verified(current.id)

    return _pick_user_out(
        {"id": current.id, "email": current.email, "user_metadata": {"username": new_username, "image": new_image}},
        is_verified
    )

@router.delete("/me", status_code=HTTP_200_OK)
def delete_me(
    body: ConfirmDeleteIn,
    current: UserOut = Depends(get_current_user)):
    """
    - profiles 행 삭제
    - Supabase Auth 사용자 삭제 (SERVICE_ROLE 필요)
    """
    # 0) 비밀번호 확인 (현재 이메일 + 입력한 비밀번호로 로그인 시도)
    try:
        supabase.auth.sign_in_with_password({"email": current.email, "password": body.password})
    except Exception:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Password check failed")
    
    # 1) profiles 정리
    try:
        supabase.table("profiles").delete().eq("user_id", current.id).execute()
    except Exception:
        pass  # 존재하지 않아도 통과

    # 2) auth 사용자 삭제
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            HTTP_400_BAD_REQUEST,
            "Server cannot delete auth user without SERVICE_ROLE key"
        )
    try:
        supabase_admin.auth.admin.delete_user(current.id)
    except Exception as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, f"Auth delete failed: {e}")

    return {"ok": True}

@router.post("/password/change", status_code=HTTP_200_OK)
def change_password(
    body: ChangePasswordIn,
    current: UserOut = Depends(get_current_user),
):
    """
    로그인 상태에서 비밀번호 변경:
    1) old_password로 재인증
    2) SERVICE_ROLE로 새 비밀번호 설정
    """
    # 1) 재인증
    try:
        supabase.auth.sign_in_with_password({"email": current.email, "password": body.old_password})
    except Exception:
        raise HTTPException(HTTP_401_UNAUTHORIZED, "Old password is incorrect")

    # 2) 변경
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(HTTP_400_BAD_REQUEST, "SERVICE_ROLE key required to change password on server")
    try:
        supabase_admin.auth.admin.update_user_by_id(current.id, attributes={"password": body.new_password})
    except Exception as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, f"Password change failed: {e}")

    return {"ok": True}

@router.post("/password/reset/request", status_code=HTTP_200_OK)
def request_password_reset(body: ResetRequestIn):
    """
    비밀번호 재설정 이메일 발송 (사용자가 비밀번호를 잊어버렸을 때)
    - redirect_to를 지정하면 링크 클릭 후 돌아올 페이지로 이동
    """
    try:
        options = {"redirect_to": body.redirect_to} if body.redirect_to else None
        supabase_admin.auth.reset_password_for_email(str(body.email), options=options)
    except Exception as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, f"Reset request failed: {e}")
    return {"ok": True}

@router.post("/password/reset/confirm", status_code=HTTP_200_OK)
def confirm_password_reset(
    body: ResetConfirmIn,
    current: UserOut = Depends(get_current_user),
):
    """
    재설정 링크 클릭 후, 클라이언트가 받은 세션 토큰(Authorization)로 최종 비밀번호 설정.
    - SERVICE_ROLE이 있으면 admin.update_user_by_id 사용
    - 없으면 현재 세션 컨텍스트로 update_user 시도
    """
    try:
        if settings.SUPABASE_SERVICE_ROLE_KEY:
            supabase.auth.admin.update_user_by_id(current.id, attributes={"password": body.new_password})
        else:
            # 세션 기반 업데이트 (현재 Authorization 토큰이 reset 링크로 발급된 세션이어야 함)
            supabase.auth.update_user({"password": body.new_password})
    except Exception as e:
        raise HTTPException(HTTP_400_BAD_REQUEST, f"Reset confirm failed: {e}")

    return {"ok": True}