"""زمان‌بندی خودکار import اکسل — تنظیم از پنل admin، اجرا روی یک PC مشخص."""

from __future__ import annotations

import logging
import socket
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from config import DB_CURRENT_PATH, STORAGE_BACKEND

logger = logging.getLogger("tadarokat.import_scheduler")

TZ = ZoneInfo("Asia/Tehran")
META_ENABLED = "import_schedule_enabled"
META_HOUR = "import_schedule_hour"
META_MINUTE = "import_schedule_minute"
META_RUNNER = "import_scheduler_host"
META_LAST_DATE = "import_schedule_last_date"
META_LAST_AT = "import_schedule_last_at"
META_LAST_STATUS = "import_schedule_last_status"

_stop_event = threading.Event()
_thread: Optional[threading.Thread] = None
_running_lock = threading.Lock()
_is_running = False

DEFAULT_HOUR = 8
DEFAULT_MINUTE = 0


def local_hostname() -> str:
    return (socket.gethostname() or "").strip().lower()


def _db_ready() -> bool:
    return STORAGE_BACKEND == "sqlite" and DB_CURRENT_PATH.exists()


def _get_meta(key: str) -> Optional[str]:
    if not _db_ready():
        return None
    from db.connection import get_db_manager

    mgr = get_db_manager()
    with mgr.connect(write=False) as conn:
        return mgr.get_meta(conn, key)


def _set_meta(key: str, value: str) -> None:
    from db.connection import get_db_manager

    mgr = get_db_manager()
    with mgr.connect(write=True) as conn:
        mgr._set_meta(conn, key, value)


def _now_tehran() -> datetime:
    return datetime.now(TZ)


def get_schedule() -> Dict[str, Any]:
    enabled = (_get_meta(META_ENABLED) or "true").lower() in ("1", "true", "yes")
    hour = int(_get_meta(META_HOUR) or DEFAULT_HOUR)
    minute = int(_get_meta(META_MINUTE) or DEFAULT_MINUTE)
    runner = (_get_meta(META_RUNNER) or "").strip()
    host = local_hostname()
    this_runner = bool(runner) and runner.lower() == host

    return {
        "enabled": enabled,
        "hour": max(0, min(23, hour)),
        "minute": max(0, min(59, minute)),
        "runner_host": runner,
        "this_hostname": host,
        "this_machine_is_runner": this_runner,
        "last_run_at": _get_meta(META_LAST_AT),
        "last_run_date": _get_meta(META_LAST_DATE),
        "last_run_status": _get_meta(META_LAST_STATUS),
        "timezone": "Asia/Tehran",
    }


def save_schedule(
    *,
    enabled: Optional[bool] = None,
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    set_this_machine_runner: bool = False,
    username: str = "admin",
) -> Dict[str, Any]:
    if not _db_ready():
        raise RuntimeError("پایگاه share در دسترس نیست")

    if enabled is not None:
        _set_meta(META_ENABLED, "true" if enabled else "false")
    if hour is not None:
        _set_meta(META_HOUR, str(max(0, min(23, int(hour)))))
    if minute is not None:
        _set_meta(META_MINUTE, str(max(0, min(59, int(minute)))))
    if set_this_machine_runner:
        _set_meta(META_RUNNER, local_hostname())

    logger.info("import schedule updated by %s", username)
    return get_schedule()


def _already_ran_today(today: str) -> bool:
    return (_get_meta(META_LAST_DATE) or "") == today


def _mark_run(today: str, status: str) -> None:
    _set_meta(META_LAST_DATE, today)
    _set_meta(META_LAST_AT, datetime.utcnow().isoformat())
    _set_meta(META_LAST_STATUS, status[:500])


def run_import_job(*, triggered_by: str = "scheduler") -> Dict[str, Any]:
    """اجرای import — فقط یک‌بار در روز از scheduler؛ دستی محدودیت ندارد."""
    global _is_running
    with _running_lock:
        if _is_running:
            return {"skipped": True, "reason": "import_in_progress"}
        _is_running = True

    try:
        from db.import_service import run_import

        result = run_import()
        status = f"ok:{triggered_by}"
        today = _now_tehran().strftime("%Y-%m-%d")
        _mark_run(today, status)

        # Make sure cache is hot after daily scheduled import
        try:
            from services.excel_service import refresh_if_excel_changed, warm_cache
            refresh_if_excel_changed()
            warm_cache()
        except Exception:
            pass

        logger.info("scheduled import OK (%s)", triggered_by)
        return {"ok": True, "triggered_by": triggered_by, "result": result}
    except Exception as exc:
        today = _now_tehran().strftime("%Y-%m-%d")
        _mark_run(today, f"error:{exc}")
        logger.exception("scheduled import failed")
        raise
    finally:
        with _running_lock:
            _is_running = False


def _should_run_now() -> bool:
    sched = get_schedule()
    if not sched["enabled"]:
        return False
    if not sched["this_machine_is_runner"]:
        return False
    if not _db_ready():
        return False

    now = _now_tehran()
    today = now.strftime("%Y-%m-%d")
    if _already_ran_today(today):
        return False

    target_h = sched["hour"]
    target_m = sched["minute"]
    if (now.hour, now.minute) < (target_h, target_m):
        return False

    return True


def _tick() -> None:
    try:
        if _should_run_now():
            run_import_job(triggered_by="scheduler")
    except Exception:
        pass


def _loop() -> None:
    logger.info("import scheduler thread started (host=%s)", local_hostname())
    while not _stop_event.is_set():
        _tick()
        _stop_event.wait(60)


def start_scheduler() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="import-scheduler", daemon=True)
    _thread.start()


def stop_scheduler() -> None:
    _stop_event.set()
    if _thread:
        _thread.join(timeout=2)