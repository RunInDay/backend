# backend-fastapi/app/routers/profile.py
from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_current_user, supabase_as_user, supabase_admin

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/me")
def get_my_profile(ctx=Depends(get_current_user)):
    user_id = ctx["claims"].get("sub")
    supa = supabase_as_user(ctx["token"])
    res = supa.table("profiles").select("*").eq("id", user_id).single().execute()
    return res.data

@router.put("/me")
def update_my_profile(nickname: str, ctx=Depends(get_current_user)):
    user_id = ctx["claims"].get("sub")
    supa = supabase_as_user(ctx["token"])
    res = supa.table("profiles").update({"nickname": nickname}).eq("id", user_id).execute()
    if res.data is None:
        raise HTTPException(400, "Update failed")
    return {"updated": True}

# 관리자용 예시 (권한 있는 내부 호출에서만 사용)
@router.get("/{user_id}")
def admin_get_profile(user_id: str):
    supa = supabase_admin()
    res = supa.table("profiles").select("*").eq("id", user_id).single().execute()
    return res.data
