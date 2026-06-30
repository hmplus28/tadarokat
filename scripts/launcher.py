#!/usr/bin/env python3
"""Unified launcher for Windows and Linux."""

from __future__ import annotations

import io
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

# Force UTF-8 console output on Windows (fixes Persian/garbled characters in PowerShell/CMD)
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
        except Exception:
            pass

ROOT = Path(__file__).resolve().parent.parent


def _venv_python() -> Path:
    if platform.system() == "Windows":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    if candidate.exists():
        return candidate
    # Fallback to current python (useful in some dev setups)
    print("[WARN] .venv python not found, using system Python. Run install.bat first for best results.")
    return Path(sys.executable)


def _load_config() -> dict:
    cfg_path = ROOT / "share.config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # New model: share.config is optional. Use defaults.
    print("[INFO] No share.config.json (or invalid) - using simplified db/ model + admin configured paths")
    return {
        "shared_data_dir": str(ROOT / "db"),
        "local_data_dir": "",
        "port": 8000,
        "mode": "full",
        "host": "127.0.0.1",
    }


def _resolve_share_path(path_str: str) -> str:
    p = Path(path_str).expanduser()
    if not p.is_absolute():
        p = (ROOT / p).resolve()
    else:
        p = p.resolve()
    return str(p)


def _apply_env(cfg: dict) -> None:
    shared = str(cfg.get("shared_data_dir") or "").strip()
    local = str(cfg.get("local_data_dir") or "").strip()
    mode = str(cfg.get("mode") or "client").strip().lower()
    host = str(cfg.get("host") or "127.0.0.1").strip()
    port = str(int(cfg.get("port") or 8000))

    if shared:
        os.environ.setdefault("TADAROKAT_SHARED_DATA", _resolve_share_path(shared))
    if local:
        os.environ.setdefault("TADAROKAT_LOCAL_DATA", _resolve_share_path(local))
    os.environ.setdefault("TADAROKAT_MODE", mode)
    os.environ.setdefault("TADAROKAT_HOST", host)
    os.environ.setdefault("TADAROKAT_PORT", port)
    os.environ.setdefault("TADAROKAT_STORAGE", os.environ.get("TADAROKAT_STORAGE", "sqlite"))


def _needs_install() -> bool:
    return not (ROOT / ".installed").exists() or not (ROOT / ".venv").exists()


def _run_install() -> None:
    print("-> Running first-time install...")
    if platform.system() == "Windows":
        script = str(ROOT / "scripts" / "install_windows.py")
        python_candidates = (["py", "-3"], ["python"], ["python3"])
        for cmd in python_candidates:
            try:
                subprocess.run([*cmd, "--version"], capture_output=True, check=True)
                result = subprocess.run([*cmd, script, "--quiet"], cwd=str(ROOT), check=False)
                if result.returncode == 0:
                    return
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        print("[ERROR] Could not run install. Please run 'install.bat' manually first.")
        raise SystemExit(1)
    else:
        try:
            subprocess.run(["bash", str(ROOT / "install.sh"), "--quiet"], cwd=str(ROOT), check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[ERROR] Linux install failed. Run ./install.sh manually.")
            raise SystemExit(1)


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
    print("Tadarokat server starting (simplified model)")
    print(f"  URL:   http://{host}:{port}")
    print(f"  Data dir: {shared or str(ROOT / 'db')}")
    print("  First login: admin / admin123 (or users from DB)")
    print("  Configure paths in Admin -> System Panel (primary data dir + excel)")
    print("  Stop with: Ctrl+C")
    print("")

    os.chdir(ROOT / "backend")
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(
        subprocess.run(
            [str(py), "-m", "uvicorn", "main:app", "--host", host, "--port", port],
            env=env,
            check=False,
        ).returncode
    )


if __name__ == "__main__":
    main()