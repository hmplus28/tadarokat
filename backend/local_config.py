"""بارگذاری تنظیمات محلی از share.config.json — قبل از import سایر ماژول‌ها."""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "share.config.json"
EXAMPLE_CONFIG_FILE = BASE_DIR / "share.config.example.json"


def default_local_data_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return (base / "tadarokat").resolve()


def load_share_config() -> Dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _set_env_if_missing(key: str, value: str | None) -> None:
    if value and not os.getenv(key):
        os.environ[key] = value


def apply_share_config() -> Dict[str, Any]:
    """متغیرهای محیطی را از share.config.json پر می‌کند (env اولویت دارد)."""
    cfg = load_share_config()

    shared = (cfg.get("shared_data_dir") or "").strip()
    local = (cfg.get("local_data_dir") or "").strip()
    mode = (cfg.get("mode") or "client").strip().lower()
    port = cfg.get("port")
    host = (cfg.get("host") or "127.0.0.1").strip()

    if shared:
        _set_env_if_missing("TADAROKAT_SHARED_DATA", str(Path(shared).expanduser()))
    if local:
        _set_env_if_missing("TADAROKAT_LOCAL_DATA", str(Path(local).expanduser()))
    elif not os.getenv("TADAROKAT_LOCAL_DATA"):
        _set_env_if_missing("TADAROKAT_LOCAL_DATA", str(default_local_data_dir()))

    _set_env_if_missing("TADAROKAT_MODE", mode)
    if port is not None:
        _set_env_if_missing("TADAROKAT_PORT", str(int(port)))
    _set_env_if_missing("TADAROKAT_HOST", host)

    return cfg