from fastapi import APIRouter, Depends, HTTPException

from auth.dependencies import require_roles
from services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(_: dict = Depends(require_roles("admin"))):
    return user_service.list_users()


@router.post("")
def create_user(payload: dict, _: dict = Depends(require_roles("admin"))):
    try:
        return user_service.create_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{username}")
def update_user(username: str, payload: dict, current: dict = Depends(require_roles("admin"))):
    try:
        return user_service.update_user(username, payload, actor=current["username"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{username}")
def deactivate_user(username: str, current: dict = Depends(require_roles("admin"))):
    try:
        user = user_service.delete_user(username, current["username"])
        return {"ok": True, "user": user, "deactivated": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc