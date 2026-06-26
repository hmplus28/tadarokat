#!/usr/bin/env python3
"""انتقال کاربران موجود (فقط hash) از data/users.json به DB روی share."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from local_config import apply_share_config  # noqa: E402

apply_share_config()

from db.connection import get_db_manager  # noqa: E402
from db.schema import USERS_DDL  # noqa: E402
from services.user_service import count_users_in_db  # noqa: E402


def main() -> None:
    src = ROOT / "data" / "users.json"
    if not src.exists():
        print("users.json یافت نشد")
        raise SystemExit(1)

    users = json.loads(src.read_text(encoding="utf-8"))
    now = datetime.utcnow().isoformat()
    mgr = get_db_manager()

    with mgr.connect(write=True) as conn:
        conn.executescript(USERS_DDL)
        if count_users_in_db(conn) > 0:
            print("کاربران از قبل در DB هستند — رد شد")
            return
        for u in users:
            conn.execute(
                """
                INSERT INTO users (id, username, password_hash, name, role, expert, warehouse, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    u.get("id") or str(uuid.uuid4()),
                    u["username"],
                    u["password_hash"],
                    u["name"],
                    u["role"],
                    u.get("expert"),
                    u.get("warehouse"),
                    1 if u.get("active", True) else 0,
                    u.get("created_at") or now,
                    u.get("updated_at") or now,
                ),
            )
        mgr._set_meta(conn, "users_migrated_from_json", now)
        mgr.bump_version(conn)

    print(f"✓ {len(users)} کاربر (hash) به DB منتقل شد")


if __name__ == "__main__":
    main()