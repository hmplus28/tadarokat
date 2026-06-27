#!/usr/bin/env python3
"""اجراکننده یکپارچه — ویندوز و لینوکس."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _venv_python() -> Path:
    if platform.system() == "Windows":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.exists() else Path(sys.executable)


def _load_config() -> dict:
    cfg_path = ROOT / "share.config.json"
    if not cfg_path.exists():
        print("❌ share.config.json یافت نشد.")
        print("   cp share.config.example.json share.config.json")
        raise SystemExit(1)
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def _apply_env(cfg: dict) -> None:
    shared = str(cfg.get("shared_data_dir") or "").strip()
    local = str(cfg.get("local_data_dir") or "").strip()
    mode = str(cfg.get("mode") or "client").strip().lower()
    host = str(cfg.get("host") or "127.0.0.1").strip()
    port = str(int(cfg.get("port") or 8000))

    if shared:
        os.environ.setdefault("TADAROKAT_SHARED_DATA", str(Path(shared).expanduser()))
    if local:
        os.environ.setdefault("TADAROKAT_LOCAL_DATA", str(Path(local).expanduser()))
    os.environ.setdefault("TADAROKAT_MODE", mode)
    os.environ.setdefault("TADAROKAT_HOST", host)
    os.environ.setdefault("TADAROKAT_PORT", port)
    os.environ.setdefault("TADAROKAT_STORAGE", os.environ.get("TADAROKAT_STORAGE", "sqlite"))


def _needs_install() -> bool:
    return not (ROOT / ".installed").exists() or not (ROOT / ".venv").exists()


def _run_install() -> None:
    print("→ نصب اولیه ...")
    if platform.system() == "Windows":
        script = str(ROOT / "scripts" / "install_windows.py")
        for cmd in (["py", "-3"], ["python"], ["python3"]):
            try:
                subprocess.run([*cmd, "--version"], capture_output=True, check=True)
                subprocess.run([*cmd, script, "--quiet"], cwd=str(ROOT), check=True)
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        print("❌ Python یافت نشد — install.bat را اجرا کنید")
        raise SystemExit(1)
    subprocess.run(["bash", str(ROOT / "install.sh"), "--quiet"], cwd=str(ROOT), check=True)


def main() -> None:
    if _needs_install():
        _run_install()

    cfg = _load_config()
    _apply_env(cfg)
    py = _venv_python()
    host = os.environ["TADAROKAT_HOST"]
    port = os.environ["TADAROKAT_PORT"]
    shared = os.environ.get("TADAROKAT_SHARED_DATA", "")

    print("")
    print("🚀 سامانه تدارکات")
    print(f"   آدرس:  http://{host}:{port}")
    print(f"   share: {shared}")
    print("   راه‌اندازی اول share: scripts/init_share")
    print("")

    os.chdir(ROOT / "backend")
    raise SystemExit(
        subprocess.run(
            [str(py), "-m", "uvicorn", "main:app", "--host", host, "--port", port],
            check=False,
        ).returncode
    )


if __name__ == "__main__":
    main()