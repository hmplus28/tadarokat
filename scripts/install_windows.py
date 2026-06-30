#!/usr/bin/env python3
"""Windows install logic for install.bat"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from datetime import datetime
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
    if cfg_path.exists():
        log("[OK] share.config.json exists (optional in new model)")
        return
    # In the new simplified model, share.config is OPTIONAL.
    # We still create a minimal one pointing at db/ for compatibility with old tools.
    data = {
        "_comment": "Optional in new simplified model. Admin sets primary_data_dir inside the app.",
        "shared_data_dir": "./db",
        "local_data_dir": "",
        "mode": "full",
        "host": "127.0.0.1",
        "port": 8000,
    }
    cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("[OK] Created minimal share.config.json (pointing to ./db - new model)")


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
    run([str(py), "-m", "pip", "install", *pip_flags, "pip", "setuptools", "wheel"], label="Upgrade pip tools")

    # Special handling for pandas on newer Python (incl. 3.14)
    try:
        run([str(py), "-m", "pip", "install", *pip_flags, "--only-binary", "pandas", "pandas>=2.2.0"], label="Install pandas (binary)")
    except Exception:
        log("[WARN] pandas binary wheel may have issues on this Python, trying without restriction")
        run([str(py), "-m", "pip", "install", *pip_flags, "pandas>=2.2.0"], label="Install pandas")

    # Force exact bcrypt 4.0.1 for passlib compatibility (fixes __about__ and 72 byte errors)
    run([str(py), "-m", "pip", "uninstall", "-y", "bcrypt"], label="Uninstall old bcrypt")
    run([str(py), "-m", "pip", "install", *pip_flags, "bcrypt==4.0.1"], label="Force bcrypt==4.0.1")

    run(
        [str(py), "-m", "pip", "install", *pip_flags, "-r", str(ROOT / "backend" / "requirements.txt")],
        label="Install remaining requirements.txt",
    )
    log("[OK] Python dependencies installed")


def build_db_template(py: Path) -> None:
    # New location: db/db_current.db (with categories + default admin)
    db_dir = ROOT / "db"
    template = db_dir / "db_current.db"
    if template.exists():
        log("[OK] DB template db/db_current.db (with default admin + categories)")
        return
    run([str(py), str(ROOT / "scripts" / "build_db_template.py")], label="Build DB template (db/)")
    if not template.exists():
        fail("Failed to create db/db_current.db template")


def _do_initial_excel_import() -> None:
    """On first install, import root Excel data into db/db_current.db so first run is fast (cached)."""
    # Use venv python to ensure pandas is available
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        log("[WARN] Virtual environment not found, skipping initial import.")
        return
    
    excel_cands = [
        ROOT / "input.xlsx",
        ROOT / "رضوانی نهایی.xlsx",
        ROOT / "purchases.xlsx",
    ]
    excel_path = None
    for cand in excel_cands:
        if cand.exists():
            excel_path = cand
            break
    if not excel_path:
        log("[INFO] No root Excel found, skipping initial import.")
        return

    db_path = ROOT / "db" / "db_current.db"
    if not db_path.exists():
        log("[WARN] Template DB not found for initial import.")
        return

    log(f"-> Initial import of Excel into template DB: {excel_path.name}")
    
    # Create a temporary script to run with venv python
    import_script = ROOT / ".venv" / "_temp_import.py"
    script_content = f'''
import sys
import json
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

excel_path = r"{excel_path}"
db_path = r"{db_path}"

try:
    df = pd.read_excel(excel_path, sheet_name=0, engine="openpyxl")
    df.columns = [" ".join(str(c).replace("\\n", " ").split()).strip() for c in df.columns]

    # Find number column
    num_col = None
    for c in ["شماره", "شماره درخواست خرید", "شماره درخواست کالا", "شماره خرید"]:
        if c in df.columns:
            num_col = c
            break
    if not num_col:
        for c in df.columns:
            if "شماره" in c or "number" in c.lower():
                num_col = c
                break
    if not num_col:
        print("[WARN] Could not find purchase number column in Excel.")
        sys.exit(0)

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM purchases")
    imported_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for rec in df.to_dict(orient="records"):
        num = str(rec.get(num_col) or "").strip()
        if num.endswith(".0") and num[:-2].replace("-", "").isdigit():
            num = num[:-2]
        if not num:
            continue
        clean = {{k: (None if pd.isna(v) else v) for k, v in rec.items()}}
        rows.append((num, json.dumps(clean, ensure_ascii=False, default=str), imported_at))
    if rows:
        conn.executemany(
            "INSERT INTO purchases(purchase_number, row_json, imported_at) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
        print(f"[OK] Initial cached {{len(rows)}} purchase rows into DB.")
    conn.close()
except Exception as e:
    print(f"[WARN] Initial Excel import failed: {{e}}")
    sys.exit(1)
'''
    
    import_script.write_text(script_content, encoding="utf-8")
    
    try:
        result = subprocess.run(
            [str(venv_py), str(import_script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.stdout:
            log(result.stdout.strip())
        if result.returncode != 0:
            log(f"[WARN] Import script failed: {result.stderr}")
    finally:
        # Clean up temp script
        if import_script.exists():
            import_script.unlink()


            
def ensure_data_dirs() -> None:
    # In new model we use db/ for template + primary_data_dir set later in UI
    # Just ensure a default data folder exists for compatibility
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    log(f"[OK] Default data directory ensured: {data_dir}")


def mark_installed() -> None:
    (ROOT / ".installed").write_text(datetime.now().isoformat() + "\n", encoding="utf-8")


def main() -> None:
    log("==========================================")
    log("  Tadarokat - Windows install")
    log("==========================================")
    log(f"  Python: {sys.version.split()[0]} - {sys.executable}")
    log("")

    py = create_venv()
    install_deps(py)
    build_db_template(py)

    # Initial import of root Excel into the db/ template DB for fast first load
    _do_initial_excel_import()

    ensure_data_dirs()
    mark_installed()

    log("")
    log("==========================================")
    log("  INSTALL COMPLETE")
    log("==========================================")
    log("  Run:            run.ps1  or  run.bat")
    log("  Login (users baked in):")
    log("    admin / admin123")
    log("    mostafa / mostafa123")
    log("    fabri / fabri123")
    log("    behnaz / behnaz123")
    log("    manager / manager123")
    log("    anbar / anbar123")
    log("  Root Excel was imported+ cached on first setup.")
    log("  After login: set primary_data_dir in System Panel.")
    log("  After setting: DB+Excel move to that path permanently.")
    log("  Browser:        http://127.0.0.1:8000")
    log("")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"Unexpected error: {exc}")