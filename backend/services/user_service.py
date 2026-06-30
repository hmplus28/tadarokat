import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from passlib.context import CryptContext

from config import DB_CURRENT_PATH, LOCAL_DATA_DIR, ROLES, STORAGE_BACKEND, USERS_PATH

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _ensure_data_dir() -> None:
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _db_users_enabled() -> bool:
    return STORAGE_BACKEND == "sqlite" and DB_CURRENT_PATH.exists()


def count_users_in_db(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _row_to_record(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "password_hash": row["password_hash"],
        "name": row["name"],
        "role": row["role"],
        "expert": row["expert"],
        "warehouse": row["warehouse"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _load_users_from_db() -> List[Dict[str, Any]]:
    from db.connection import get_db_manager
    from db.schema import USERS_DDL

    mgr = get_db_manager()
    with mgr.connect(write=False) as conn:
        conn.executescript(USERS_DDL)
        rows = conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    return [_row_to_record(r) for r in rows]


def _upsert_user_db(user: Dict[str, Any]) -> None:
    from db.connection import get_db_manager

    mgr = get_db_manager()
    with mgr.connect(write=True) as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, name, role, expert, warehouse, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash=excluded.password_hash,
                name=excluded.name,
                role=excluded.role,
                expert=excluded.expert,
                warehouse=excluded.warehouse,
                active=excluded.active,
                updated_at=excluded.updated_at
            """,
            (
                user["id"],
                user["username"],
                user["password_hash"],
                user["name"],
                user["role"],
                user.get("expert"),
                user.get("warehouse"),
                1 if user.get("active", True) else 0,
                user.get("created_at"),
                user.get("updated_at"),
            ),
        )


def _serialize_user(user: Dict[str, Any], include_dates: bool = False) -> Dict[str, Any]:
    data = {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
        "expert": user.get("expert"),
        "warehouse": user.get("warehouse"),
        "active": user.get("active", True),
    }
    if include_dates:
        data["created_at"] = user.get("created_at")
        data["updated_at"] = user.get("updated_at")
    return data


def init_users() -> None:
    """فقط fallback محلی — در حالت عادی کاربران از DB روی share خوانده می‌شوند."""
    if _db_users_enabled() and _load_users_from_db():
        return
    _ensure_data_dir()
    if USERS_PATH.exists():
        return
    legacy = Path(__file__).resolve().parent.parent.parent / "data" / "users.json"
    if legacy.exists() and legacy != USERS_PATH:
        USERS_PATH.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")


def _load_users() -> List[Dict[str, Any]]:
    if _db_users_enabled():
        users = _load_users_from_db()
        if users:
            return users
    init_users()
    if USERS_PATH.exists():
        return json.loads(USERS_PATH.read_text(encoding="utf-8"))
    return []


def _save_users(users: List[Dict[str, Any]]) -> None:
    if _db_users_enabled():
        for user in users:
            _upsert_user_db(user)
        return
    _ensure_data_dir()
    USERS_PATH.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def list_users(include_inactive: bool = True) -> List[Dict[str, Any]]:
    users = _load_users()
    if not include_inactive:
        users = [u for u in users if u.get("active", True)]
    return [_serialize_user(u, include_dates=True) for u in users]


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    username = username.strip().lower()
    for user in _load_users():
        if user["username"] == username:
            return _serialize_user(user)
    return None


def get_user_record(username: str) -> Optional[Dict[str, Any]]:
    username = username.strip().lower()
    for user in _load_users():
        if user["username"] == username:
            return user
    return None


def change_own_password(username: str, current_password: str, new_password: str) -> Dict[str, Any]:
    current_password = str(current_password or "").strip()
    new_password = str(new_password or "").strip()
    if not current_password or not new_password:
        raise ValueError("رمز فعلی و جدید الزامی است")
    if len(new_password) < 6:
        raise ValueError("رمز جدید باید حداقل ۶ کاراکتر باشد")

    users = _load_users()
    target = None
    for user in users:
        if user["username"] == username:
            target = user
            break
    if not target:
        raise ValueError("کاربر یافت نشد")
    if not verify_password(current_password, target["password_hash"]):
        raise ValueError("رمز عبور فعلی اشتباه است")

    target["password_hash"] = _hash_password(new_password)
    target["updated_at"] = datetime.utcnow().isoformat()
    _save_users(users)
    return {"ok": True, "message": "رمز عبور با موفقیت تغییر کرد"}


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    record = get_user_record(username)
    if not record or not record.get("active", True):
        return None
    if not verify_password(password, record["password_hash"]):
        return None
    return _serialize_user(record)


def create_user(payload: Dict[str, Any]) -> Dict[str, Any]:
    users = _load_users()
    username = str(payload.get("username", "")).strip().lower()
    password = str(payload.get("password", "")).strip()
    name = str(payload.get("name", "")).strip()
    role = str(payload.get("role", "expert")).strip()

    if not username or not password or not name:
        raise ValueError("نام کاربری، رمز عبور و نام الزامی است")
    if role not in ROLES:
        raise ValueError("نقش نامعتبر است")
    if role == "warehouse":
        warehouse_name = str(payload.get("warehouse") or "").strip()
        if not warehouse_name:
            raise ValueError("برای نقش انبار، نام انبار الزامی است")
    if any(u["username"] == username for u in users):
        raise ValueError("نام کاربری تکراری است")
    if len(password) < 6:
        raise ValueError("رمز عبور باید حداقل ۶ کاراکتر باشد")

    now = datetime.utcnow().isoformat()
    user = {
        "id": str(uuid.uuid4()),
        "username": username,
        "password_hash": _hash_password(password),
        "name": name,
        "role": role,
        "expert": payload.get("expert"),
        "warehouse": payload.get("warehouse"),
        "active": bool(payload.get("active", True)),
        "created_at": now,
        "updated_at": now,
    }
    users.append(user)
    _save_users(users)
    return _serialize_user(user, include_dates=True)


def update_user(username: str, payload: Dict[str, Any], actor: Optional[str] = None) -> Dict[str, Any]:
    users = _load_users()
    username = username.strip().lower()
    target = None
    for user in users:
        if user["username"] == username:
            target = user
            break
    if not target:
        raise ValueError("کاربر یافت نشد")

    from services import history_service
    before = _serialize_user(target)

    new_username = str(payload.get("new_username") or payload.get("username") or "").strip().lower()
    if new_username and new_username != username:
        if any(u["username"] == new_username and u.get("id") != target.get("id") for u in users):
            raise ValueError("نام کاربری تکراری است")
        target["username"] = new_username
        username = new_username

    if "name" in payload and payload["name"]:
        target["name"] = str(payload["name"]).strip()
    if "role" in payload and payload["role"]:
        role = str(payload["role"]).strip()
        if role not in ROLES:
            raise ValueError("نقش نامعتبر است")
        target["role"] = role
    if "expert" in payload:
        target["expert"] = payload["expert"] or None
    if "warehouse" in payload:
        target["warehouse"] = payload["warehouse"] or None
    if str(target.get("role") or "") == "warehouse" and not str(target.get("warehouse") or "").strip():
        raise ValueError("برای نقش انبار، نام انبار الزامی است")
    if "active" in payload:
        target["active"] = bool(payload["active"])
    if payload.get("password"):
        password = str(payload["password"]).strip()
        if len(password) < 6:
            raise ValueError("رمز عبور باید حداقل ۶ کاراکتر باشد")
        target["password_hash"] = _hash_password(password)

    target["updated_at"] = datetime.utcnow().isoformat()
    _save_users(users)
    after = _serialize_user(target)
    changes = {}
    for key in ("username", "name", "role", "expert", "warehouse", "active"):
        if key in after and before.get(key) != after.get(key):
            changes[key] = after.get(key)
    if payload.get("password"):
        changes["password"] = "••••••"
    if changes:
        history_service.log_field_changes(
            "کاربر", username, actor or username, changes, before, action="ویرایش کاربر"
        )
    return after


def delete_user(username: str, current_username: str) -> Dict[str, Any]:
    """غیرفعال‌سازی کاربر — داده‌های گردش کار حذف نمی‌شود."""
    from services import history_service

    username = username.strip().lower()
    if username == current_username:
        raise ValueError("نمی‌توانید حساب خود را غیرفعال کنید")
    users = _load_users()
    target = next((u for u in users if u["username"] == username), None)
    if not target:
        raise ValueError("کاربر یافت نشد")
    if not target.get("active", True):
        raise ValueError("این کاربر قبلاً غیرفعال شده است")

    before = _serialize_user(target)
    target["active"] = False
    target["updated_at"] = datetime.utcnow().isoformat()
    _save_users(users)
    after = _serialize_user(target)
    history_service.log_field_changes(
        "کاربر", username, current_username, {"active": False}, before, action="غیرفعال‌سازی کاربر"
    )
    return after