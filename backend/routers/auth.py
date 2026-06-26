from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import get_current_user
from auth.jwt_handler import create_access_token
from services import user_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: dict):
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="نام کاربری و رمز عبور الزامی است")

    user = user_service.authenticate(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور اشتباه است")

    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.patch("/change-password")
def change_password(payload: dict, user: dict = Depends(get_current_user)):
    try:
        return user_service.change_own_password(
            user["username"],
            payload.get("current_password") or payload.get("رمز_فعلی"),
            payload.get("new_password") or payload.get("رمز_جدید"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc