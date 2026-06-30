"""سرویس import روزانه — اکسل → db_new → swap اتمیک → db_current."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from config import (
    DB_CURRENT_PATH,
    DB_NEW_PATH,
    DB_OLD_PATH,
    EXCEL_PATH,
    INPUT_EXCEL_PATH,
    LOCK_FLAG_PATH,
    LOGS_DIR,
    SHEETS,
    WORKFLOW_TABLES,
)
from db.connection import DatabaseManager, reset_db_manager, wait_until_unlocked
from db.schema import SCHEMA_VERSION

logger = logging.getLogger("tadarokat.import")


def _utc_now() -> str:
    return datetime.utcnow().isoformat()


def _normalize_col(name: str) -> str:
    return " ".join(str(name).replace("\n", " ").replace("\r", " ").split()).strip()


def _normalize_purchase_number(val: Any) -> str:
    s = str(val or "").strip()
    if s.endswith(".0") and s[:-2].replace("-", "").isdigit():
        return s[:-2]
    return s


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_input_excel() -> Path:
    if INPUT_EXCEL_PATH.exists():
        return INPUT_EXCEL_PATH
    if EXCEL_PATH.exists():
        return EXCEL_PATH
    raise FileNotFoundError(f"فایل ورودی یافت نشد: {INPUT_EXCEL_PATH} یا {EXCEL_PATH}")


class ImportService:
    def __init__(self) -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.current_mgr = DatabaseManager(DB_CURRENT_PATH)
        self.new_mgr = DatabaseManager(DB_NEW_PATH)

    def _log_import(
        self,
        conn: sqlite3.Connection,
        *,
        started_at: str,
        status: str,
        message: str = "",
        details: Optional[Dict] = None,
        **fields: Any,
    ) -> None:
        conn.execute(
            """
            INSERT INTO import_log(
                started_at, finished_at, status, source_file, source_mtime, source_sha256,
                row_count, previous_version, new_version, message, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at,
                _utc_now(),
                status,
                fields.get("source_file"),
                fields.get("source_mtime"),
                fields.get("source_sha256"),
                fields.get("row_count"),
                fields.get("previous_version"),
                fields.get("new_version"),
                message,
                json.dumps(details or {}, ensure_ascii=False),
            ),
        )

    def _read_purchases_excel(self, path: Path) -> pd.DataFrame:
        sheet = SHEETS["purchases"]
        xl = None
        df = pd.DataFrame()
        try:
            xl = pd.ExcelFile(path, engine="openpyxl")
            if sheet in xl.sheet_names:
                df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
            elif xl.sheet_names:
                # Try common purchase sheet names or first
                for candidate in xl.sheet_names:
                    if "خرید" in candidate or "request" in candidate.lower() or candidate == xl.sheet_names[0]:
                        df = pd.read_excel(path, sheet_name=candidate, engine="openpyxl")
                        break
                if df.empty and xl.sheet_names:
                    df = pd.read_excel(path, sheet_name=xl.sheet_names[0], engine="openpyxl")
        except Exception as e:
            logger.warning("Excel read issue: %s", e)
            if xl is None:
                try:
                    xl = pd.ExcelFile(path, engine="openpyxl")
                    df = pd.read_excel(path, sheet_name=xl.sheet_names[0], engine="openpyxl") if xl.sheet_names else pd.DataFrame()
                except Exception:
                    df = pd.DataFrame()
        if not df.empty:
            df.columns = [_normalize_col(c) for c in df.columns]
        return df

    def _import_purchases(self, conn: sqlite3.Connection, df: pd.DataFrame, imported_at: str) -> int:
        conn.execute("DELETE FROM purchases")
        if df.empty:
            return 0

        # Flexible purchase number column (support user's ERP export)
        possible_num_cols = ["شماره", "شماره درخواست خرید", "شماره درخواست کالا", "شماره خرید"]
        num_col = None
        for c in possible_num_cols:
            if c in df.columns:
                num_col = c
                break
        if not num_col:
            # fallback: first column that looks like id
            for c in df.columns:
                if "شماره" in c or "number" in c.lower():
                    num_col = c
                    break
        if not num_col:
            logger.warning("No purchase number column found. Columns: %s", list(df.columns)[:5])
            return 0

        rows = []
        for rec in df.to_dict(orient="records"):
            num = _normalize_purchase_number(rec.get(num_col))
            if not num:
                continue
            clean = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
            rows.append((num, json.dumps(clean, ensure_ascii=False, default=str), imported_at))
        if rows:
            conn.executemany(
                "INSERT INTO purchases(purchase_number, row_json, imported_at) VALUES (?, ?, ?)",
                rows,
            )
        return len(rows)

    def _validate_new_db(self, conn: sqlite3.Connection, expected_rows: int, prev_count: int) -> None:
        actual = conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"]
        if expected_rows > 0 and actual != expected_rows:
            raise ValueError(f"تعداد ردیف purchases نادرست: {actual} != {expected_rows}")
        # افت شدید داده — هشدار امنیتی (بیش از ۵۰٪ کاهش بدون تأیید)
        if prev_count > 100 and actual < prev_count * 0.5:
            raise ValueError(
                f"کاهش مشکوک تعداد خرید: {prev_count} → {actual}. import لغو شد."
            )
        ver = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if not ver or int(ver["value"]) != SCHEMA_VERSION:
            raise ValueError("نسخه schema نامعتبر")

    def build_db_new(self, input_path: Path) -> Dict[str, Any]:
        started = _utc_now()
        source_mtime = input_path.stat().st_mtime
        source_sha = _file_sha256(input_path)
        df = self._read_purchases_excel(input_path)
        row_count = len(df)

        if DB_NEW_PATH.exists():
            DB_NEW_PATH.unlink()

        prev_version = 0
        prev_purchase_count = 0

        with self.new_mgr.connect(write=True) as new_conn:
            self.new_mgr.initialize_schema(new_conn)

            if DB_CURRENT_PATH.exists():
                with self.current_mgr.connect(write=False) as cur_conn:
                    prev_version = int(self.current_mgr.get_meta(cur_conn, "db_version") or "0")
                    prev_purchase_count = cur_conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"]
                    self.new_mgr.copy_workflow_tables(cur_conn, new_conn, WORKFLOW_TABLES)

                    # Preserve seeded data (users + categories) across imports
                    # This is critical when first import happens on the db/ template
                    for table in ("users", "categories"):
                        try:
                            rows = cur_conn.execute(f'SELECT * FROM "{table}"').fetchall()
                            if rows:
                                new_conn.execute(f'DELETE FROM "{table}"')
                                cols = rows[0].keys()
                                col_list = ", ".join(f'"{c}"' for c in cols)
                                placeholders = ", ".join("?" for _ in cols)
                                new_conn.executemany(
                                    f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})',
                                    [tuple(r[c] for c in cols) for r in rows],
                                )
                        except Exception:
                            pass

                    for key in ("db_version", "last_import_at", "last_import_sha256", "template_version", "categories_seeded", "default_admin_seeded"):
                        val = self.current_mgr.get_meta(cur_conn, key)
                        if val:
                            self.new_mgr._set_meta(new_conn, key, val)

            imported_at = _utc_now()
            inserted = self._import_purchases(new_conn, df, imported_at)
            new_version = self.new_mgr.bump_version(new_conn)
            self.new_mgr._set_meta(new_conn, "last_import_at", imported_at)
            self.new_mgr._set_meta(new_conn, "last_import_sha256", source_sha)
            self.new_mgr._set_meta(new_conn, "last_import_rows", str(inserted))
            self.new_mgr._set_meta(new_conn, "schema_version", str(SCHEMA_VERSION))

            self._validate_new_db(new_conn, inserted, prev_purchase_count)
            self._log_import(
                new_conn,
                started_at=started,
                status="built",
                message="db_new ساخته شد",
                source_file=str(input_path),
                source_mtime=source_mtime,
                source_sha256=source_sha,
                row_count=inserted,
                previous_version=prev_version,
                new_version=new_version,
            )

        return {
            "ok": True,
            "row_count": inserted,
            "previous_version": prev_version,
            "new_version": new_version,
            "source_sha256": source_sha,
        }

    def atomic_swap(self) -> Dict[str, Any]:
        if not DB_NEW_PATH.exists():
            raise FileNotFoundError("db_new.db وجود ندارد — ابتدا build اجرا شود")

        LOCK_FLAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCK_FLAG_PATH, "w", encoding="utf-8") as lf:
            lf.write(f"locked_at={_utc_now()}\npid={os.getpid()}\n")

        try:
            # Strong reset before touching files (releases any cached connections)
            reset_db_manager()

            # بستن WAL برای همه فایل‌های درگیر (CURRENT, OLD, NEW) — خیلی مهم روی ویندوز
            for suffix in ("-wal", "-shm"):
                for base in (DB_CURRENT_PATH, DB_OLD_PATH, DB_NEW_PATH):
                    p = Path(str(base) + suffix)
                    if p.exists():
                        try:
                            p.unlink()
                        except OSError:
                            pass

            # Give Windows a moment to release file handles
            import time
            time.sleep(0.15)

            import shutil
            import time as _time

            # Reliable final placement on Windows: copy the freshly built new over current.
            # First try to move current aside as old (best effort).
            try:
                if DB_CURRENT_PATH.exists():
                    if DB_OLD_PATH.exists():
                        try: DB_OLD_PATH.unlink()
                        except: pass
                    os.replace(DB_CURRENT_PATH, DB_OLD_PATH)
            except OSError:
                pass

            # Now ensure current gets the content of new via copy (very reliable)
            # CRITICAL: force WAL checkpoint so all data is in the main .db file before we copy/rename
            if DB_NEW_PATH.exists():
                try:
                    c = sqlite3.connect(str(DB_NEW_PATH))
                    c.execute("PRAGMA wal_checkpoint(FULL);")
                    c.close()
                except Exception:
                    pass

            for attempt in range(3):
                for suffix in ("-wal", "-shm"):
                    for base in (DB_CURRENT_PATH, DB_NEW_PATH):
                        p = Path(str(base) + suffix)
                        if p.exists():
                            try: p.unlink()
                            except: pass
                _time.sleep(0.1)

                try:
                    if DB_NEW_PATH.exists():
                        shutil.copy2(DB_NEW_PATH, DB_CURRENT_PATH)
                        try:
                            DB_NEW_PATH.unlink()
                        except OSError:
                            pass
                    break
                except Exception as e:
                    if attempt == 2:
                        try:
                            os.replace(DB_NEW_PATH, DB_CURRENT_PATH)
                        except:
                            pass
                    else:
                        _time.sleep(0.2)

            # cleanup
            try:
                if DB_NEW_PATH.exists(): DB_NEW_PATH.unlink()
            except OSError:
                pass

            reset_db_manager()
            return {"ok": True, "swapped_at": _utc_now()}
        except Exception as exc:
            logger.exception("swap failed")
            # Best-effort rollback
            try:
                if DB_NEW_PATH.exists() and not DB_CURRENT_PATH.exists() and DB_OLD_PATH.exists():
                    os.replace(DB_OLD_PATH, DB_CURRENT_PATH)
            except OSError:
                pass
            raise exc
        finally:
            try:
                LOCK_FLAG_PATH.unlink(missing_ok=True)
            except TypeError:
                if LOCK_FLAG_PATH.exists():
                    LOCK_FLAG_PATH.unlink()

    def run_full_import(self, input_path: Optional[Path] = None) -> Dict[str, Any]:
        wait_until_unlocked()
        path = input_path or _resolve_input_excel()
        build_result = self.build_db_new(path)
        swap_result = self.atomic_swap()

        log_path = LOGS_DIR / f"import_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        result = {**build_result, **swap_result, "input": str(path)}
        log_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Import OK: %s", result)

        # Ensure cache is refreshed after successful import (daily + change requirement)
        try:
            from services.excel_service import invalidate_cache, warm_cache
            invalidate_cache()
            warm_cache()
        except Exception:
            pass

        # Mark as migrated so legacy ensure won't re-clear purchases on warm_cache
        try:
            with self.current_mgr.connect(write=True) as c:
                self.current_mgr._set_meta(c, "migrated_from_local_excel", "1")
        except Exception:
            pass

        return result


def run_import(input_path: Optional[str] = None) -> Dict[str, Any]:
    svc = ImportService()
    p = Path(input_path) if input_path else None
    return svc.run_full_import(p)