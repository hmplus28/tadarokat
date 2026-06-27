#!/usr/bin/env python3
"""نصب اولیه ویندوز — منطق اصلی install.bat"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUIET = "--quiet" in sys.argv or "/quiet" in sys.argv

if sys.platform != "win32":
    print("[خطا] install_windows.py فقط برای ویندوز است — از install.sh استفاده کنید.", file=sys.stderr)
    raise SystemExit(1)


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1) -> None:
    log("")
    log(f"[خطا] {msg}")
    raise SystemExit(code)


def run(cmd: list[str], *, label: str) -> None:
    log(f"→ {label}")
    try:
        subprocess.run(cmd, cwd=str(ROOT), check=True)
    except subprocess.CalledProcessError as exc:
        fail(f"{label} ناموفق (کد {exc.returncode})")


def ensure_share_config() -> None:
    cfg_path = ROOT / "share.config.json"
    example = ROOT / "share.config.example.json"
    if cfg_path.exists():
        log("[OK] share.config.json موجود است")
        return
    if not example.exists():
        fail("فایل share.config.example.json یافت نشد")
    data = json.loads(example.read_text(encoding="utf-8"))
    data["shared_data_dir"] = "./data"
    data["mode"] = "full"
    data["host"] = "127.0.0.1"
    data["port"] = 8000
    cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("[OK] share.config.json ساخته شد (مسیر لوکال: ./data)")


def venv_python() -> Path:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        fail("محیط مجازی .venv ساخته نشد — install را دوباره اجرا کنید")
    return py


def create_venv() -> Path:
    vpy = ROOT / ".venv" / "Scripts" / "python.exe"
    if vpy.exists():
        log("[OK] محیط مجازی .venv")
        return vpy

    log("→ ایجاد محیط مجازی Python (.venv)")
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
        log("[OK] وابستگی‌های Python از قبل نصب‌اند")
        return
    pip_flags = ["--disable-pip-version-check"]
    if QUIET:
        pip_flags.append("-q")
    run([str(py), "-m", "pip", "install", *pip_flags, "pip"], label="به‌روزرسانی pip")
    run(
        [str(py), "-m", "pip", "install", *pip_flags, "-r", str(ROOT / "backend" / "requirements.txt")],
        label="نصب requirements.txt",
    )
    log("[OK] وابستگی‌های Python")


def build_db_template(py: Path) -> None:
    template = ROOT / "templates" / "db_current.db"
    if template.exists():
        log("[OK] قالب پایگاه db_current.db")
        return
    run([str(py), str(ROOT / "scripts" / "build_db_template.py")], label="ساخت قالب DB")


def ensure_data_dirs() -> None:
    cfg = json.loads((ROOT / "share.config.json").read_text(encoding="utf-8"))
    share = Path(str(cfg.get("shared_data_dir") or "./data"))
    if not share.is_absolute():
        share = (ROOT / share).resolve()
    share.mkdir(parents=True, exist_ok=True)
    (share / "logs").mkdir(exist_ok=True)
    log(f"[OK] پوشه داده: {share}")


def mark_installed() -> None:
    (ROOT / ".installed").write_text(datetime.now().isoformat() + "\n", encoding="utf-8")


def main() -> None:
    log("══════════════════════════════════════════")
    log("  سامانه تدارکات — نصب اولیه (ویندوز)")
    log("══════════════════════════════════════════")
    log(f"  Python: {sys.version.split()[0]} — {sys.executable}")
    log("")

    ensure_share_config()
    py = create_venv()
    install_deps(py)
    build_db_template(py)
    ensure_data_dirs()
    mark_installed()

    log("")
    log("══════════════════════════════════════════")
    log("  نصب کامل شد")
    log("══════════════════════════════════════════")
    log("  اجرا:           run.bat")
    log("  ساخت کاربران:   scripts\\init_share.bat")
    log("  مرورگر:         http://127.0.0.1:8000")
    log("")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"خطای غیرمنتظره: {exc}")