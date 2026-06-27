#!/usr/bin/env python3
"""Windows install logic for install.bat"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUIET = "--quiet" in sys.argv or "/quiet" in sys.argv

if sys.platform != "win32":
    print("[ERROR] install_windows.py is Windows-only. Use install.sh on Linux.", file=sys.stderr)
    raise SystemExit(1)


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1) -> None:
    log("")
    log(f"[ERROR] {msg}")
    raise SystemExit(code)


def run(cmd: list[str], *, label: str) -> None:
    log(f"-> {label}")
    try:
        subprocess.run(cmd, cwd=str(ROOT), check=True)
    except subprocess.CalledProcessError as exc:
        fail(f"{label} failed (exit code {exc.returncode})")


def ensure_share_config() -> None:
    cfg_path = ROOT / "share.config.json"
    example = ROOT / "share.config.example.json"
    if cfg_path.exists():
        log("[OK] share.config.json exists")
        return
    if not example.exists():
        fail("share.config.example.json not found")
    data = json.loads(example.read_text(encoding="utf-8"))
    data["shared_data_dir"] = "./data"
    data["mode"] = "full"
    data["host"] = "127.0.0.1"
    data["port"] = 8000
    cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("[OK] Created share.config.json (local data dir: ./data)")


def venv_python() -> Path:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        fail(".venv was not created - run install.bat again")
    return py


def create_venv() -> Path:
    vpy = ROOT / ".venv" / "Scripts" / "python.exe"
    if vpy.exists():
        log("[OK] Virtual environment .venv")
        return vpy

    log("-> Creating Python virtual environment (.venv)")
    run([sys.executable, "-m", "venv", str(ROOT / ".venv")], label="venv")
    return venv_python()


def deps_installed(py: Path) -> bool:
    try:
        subprocess.run(
            [str(py), "-c", "import uvicorn, pandas, fastapi"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def install_deps(py: Path) -> None:
    if deps_installed(py):
        log("[OK] Python dependencies already installed")
        return
    pip_flags = ["--disable-pip-version-check"]
    if QUIET:
        pip_flags.append("-q")
    run([str(py), "-m", "pip", "install", *pip_flags, "pip"], label="Upgrade pip")
    run(
        [str(py), "-m", "pip", "install", *pip_flags, "-r", str(ROOT / "backend" / "requirements.txt")],
        label="Install requirements.txt",
    )
    log("[OK] Python dependencies installed")


def build_db_template(py: Path) -> None:
    template = ROOT / "templates" / "db_current.db"
    if template.exists():
        log("[OK] DB template db_current.db")
        return
    run([str(py), str(ROOT / "scripts" / "build_db_template.py")], label="Build DB template")


def ensure_data_dirs() -> None:
    cfg = json.loads((ROOT / "share.config.json").read_text(encoding="utf-8"))
    share = Path(str(cfg.get("shared_data_dir") or "./data"))
    if not share.is_absolute():
        share = (ROOT / share).resolve()
    share.mkdir(parents=True, exist_ok=True)
    (share / "logs").mkdir(exist_ok=True)
    log(f"[OK] Data directory: {share}")


def mark_installed() -> None:
    (ROOT / ".installed").write_text(datetime.now().isoformat() + "\n", encoding="utf-8")


def main() -> None:
    log("==========================================")
    log("  Tadarokat - Windows install")
    log("==========================================")
    log(f"  Python: {sys.version.split()[0]} - {sys.executable}")
    log("")

    ensure_share_config()
    py = create_venv()
    install_deps(py)
    build_db_template(py)
    ensure_data_dirs()
    mark_installed()

    log("")
    log("==========================================")
    log("  INSTALL COMPLETE")
    log("==========================================")
    log("  Run app:        run.bat")
    log("  Setup users:    scripts\\init_share.bat")
    log("  Browser:        http://127.0.0.1:8000")
    log("")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"Unexpected error: {exc}")