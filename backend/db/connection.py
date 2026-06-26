"""مدیریت اتصال SQLite — WAL، busy_timeout، قفل swap، حالت فقط‌خواندنی."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from config import (
    CLIENT_READ_ONLY,
    DB_CURRENT_PATH,
    LOCK_FLAG_PATH,
    LOGS_DIR,
)
from db.schema import SCHEMA_VERSION, all_ddl

logger = logging.getLogger("tadarokat.db")

_manager: Optional["DatabaseManager"] = None
_manager_lock = threading.Lock()


class SystemLockedError(RuntimeError):
    """سیستم در حال swap پایگاه داده است."""


class ReadOnlyClientError(PermissionError):
    """کلاینت اجازه نوشتن مستقیم به DB مشترک را ندارد."""


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def is_system_locked() -> bool:
    return LOCK_FLAG_PATH.exists()


def wait_until_unlocked(timeout_sec: float = 15.0, poll: float = 0.1) -> bool:
    """فقط برای تراکنش‌های نوشتن — خواندن منتظر نمی‌ماند."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not is_system_locked():
            return True
        time.sleep(poll)
    return not is_system_locked()


def read_db_path(primary: Optional[Path] = None) -> Path:
    """هنگام swap کوتاه، از نسخه قبلی بخوان تا دسترسی قطع نشود."""
    from config import DB_CURRENT_PATH, DB_OLD_PATH

    main = Path(primary or DB_CURRENT_PATH)
    if is_system_locked() and DB_OLD_PATH.exists():
        return DB_OLD_PATH
    return main


class DatabaseManager:
    def __init__(
        self,
        db_path: Path = DB_CURRENT_PATH,
        *,
        read_only: bool = False,
        allow_write: bool = True,
    ) -> None:
        self.db_path = Path(db_path)
        self.read_only = read_only
        self.allow_write = allow_write
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _active_path(self, write: bool) -> Path:
        if write:
            return self.db_path
        return read_db_path(self.db_path)

    def _uri(self, write: bool) -> str:
        path = self._active_path(write).resolve().as_posix()
        if self.read_only or (not write and CLIENT_READ_ONLY):
            return f"file:{path}?mode=ro"
        return f"file:{path}?mode=rwc"

    @contextmanager
    def connect(self, *, write: bool = False) -> Generator[sqlite3.Connection, None, None]:
        if write:
            if self.read_only or CLIENT_READ_ONLY:
                raise ReadOnlyClientError(
                    "نوشتن مستقیم به پایگاه مشترک غیرفعال است (TADAROKAT_CLIENT_READ_ONLY=1)"
                )
            # قفل فقط مانع نوشتن می‌شود — با انتظار کوتاه (swap چند ثانیه)
            if is_system_locked() and not wait_until_unlocked(timeout_sec=15.0):
                raise SystemLockedError("import در حال swap — لطفاً چند ثانیه بعد تلاش کنید")

        uri = self._uri(write=write)
        conn = sqlite3.connect(uri, uri=True, timeout=60.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            if write:
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=60000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA temp_store=MEMORY")
            yield conn
            if write:
                conn.commit()
        except Exception:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self, conn: sqlite3.Connection) -> None:
        for ddl in all_ddl():
            conn.executescript(ddl)
        self._set_meta(conn, "schema_version", str(SCHEMA_VERSION))
        if self.get_meta(conn, "db_version") is None:
            self._set_meta(conn, "db_version", "1")

    def _set_meta(self, conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            """
            INSERT INTO meta(key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, _utc_now()),
        )

    def get_meta(self, conn: sqlite3.Connection, key: str) -> Optional[str]:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def bump_version(self, conn: sqlite3.Connection) -> int:
        cur = int(self.get_meta(conn, "db_version") or "0")
        nxt = cur + 1
        self._set_meta(conn, "db_version", str(nxt))
        self._set_meta(conn, "last_updated_at", _utc_now())
        return nxt

    def db_info(self) -> dict:
        info = {
            "path": str(self.db_path),
            "exists": self.db_path.exists(),
            "locked": is_system_locked(),
            "read_only_client": CLIENT_READ_ONLY,
            "size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
        }
        if not self.db_path.exists():
            return {**info, "db_version": None, "schema_version": None}

        try:
            with self.connect(write=False) as conn:
                info["db_version"] = self.get_meta(conn, "db_version")
                info["schema_version"] = self.get_meta(conn, "schema_version")
                info["last_import_at"] = self.get_meta(conn, "last_import_at")
                info["last_export_at"] = self.get_meta(conn, "last_export_at")
                info["purchase_count"] = conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"]
        except Exception as exc:
            info["error"] = str(exc)
        return info

    def copy_workflow_tables(self, src_conn: sqlite3.Connection, dst_conn: sqlite3.Connection, tables: tuple) -> None:
        from config import WORKFLOW_TABLES

        for table in tables or WORKFLOW_TABLES:
            dst_conn.execute(f'DELETE FROM "{table}"')
            try:
                rows = src_conn.execute(f'SELECT * FROM "{table}"').fetchall()
            except sqlite3.OperationalError:
                continue
            if not rows:
                continue
            cols = rows[0].keys()
            col_list = ", ".join(f'"{c}"' for c in cols)
            placeholders = ", ".join("?" for _ in cols)
            dst_conn.executemany(
                f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
                [tuple(r[c] for c in cols) for r in rows],
            )

    def backup_file(self, dest: Path) -> None:
        if self.db_path.exists():
            shutil.copy2(self.db_path, dest)


def get_db_manager(
    *,
    db_path: Optional[Path] = None,
    read_only: bool = False,
) -> DatabaseManager:
    global _manager
    with _manager_lock:
        if _manager is None or (db_path and Path(db_path) != _manager.db_path):
            _manager = DatabaseManager(
                db_path or DB_CURRENT_PATH,
                read_only=read_only,
                allow_write=not CLIENT_READ_ONLY,
            )
        return _manager


def reset_db_manager() -> None:
    """پس از swap اتمیک — اتصال cache را پاک کن."""
    global _manager
    with _manager_lock:
        _manager = None