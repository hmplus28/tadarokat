#!/usr/bin/env python3
"""One-click local test setup: install, DB, users, optional Excel import, verify."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent.parent
TEST_SEED = ROOT / "share_users.test.seed.json"

VERIFY_USERS = [
    ("admin", "admin123"),
    ("manager", "manager123"),
    ("mostafa", "mostafa123"),
    ("anbar", "anbar123"),
]

# Bypass HTTP_PROXY for localhost (common in dev environments)
_HTTP = build_opener(ProxyHandler({}))


def log(msg: str) -> None:
    print(msg, flush=True)


def fail(msg: str, code: int = 1) -> None:
    log(f"[ERROR] {msg}")
    raise SystemExit(code)


def run_cmd(
    cmd: list[str],
    *,
    label: str,
    cwd: Path | None = None,
    timeout: int = 600,
    env: dict | None = None,
) -> None:
    """Run a command with live output, no stdin, and a timeout."""
    log(f"-> {label}  [CMD: {' '.join(cmd)}]")

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd or ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=run_env,
        )

        for line in proc.stdout:
            print(line, end="", flush=True)

        retcode = proc.wait(timeout=timeout)
        if retcode != 0:
            fail(f"{label} failed (exit {retcode})")

    except subprocess.TimeoutExpired:
        proc.kill()
        fail(f"{label} timed out after {timeout} seconds")
    except Exception as e:
        fail(f"{label} error: {e}")


def venv_python() -> Path:
    if platform.system() == "Windows":
        py = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        py = ROOT / ".venv" / "bin" / "python"
    if not py.exists():
        fail("Virtual env missing - install step failed")
    return py


def ensure_share_config() -> Path:
    """Test mode: project root is the share folder; input.xlsx lives in root."""
    cfg_path = ROOT / "share.config.json"
    backup = ROOT / "share.config.json.bak"
    test_cfg = {
        "shared_data_dir": ".",
        "local_data_dir": "",
        "port": 8000,
        "mode": "full",
        "host": "127.0.0.1",
    }

    if cfg_path.exists():
        try:
            current = json.loads(cfg_path.read_text(encoding="utf-8"))
            if current.get("shared_data_dir") != ".":
                if not backup.exists():
                    shutil.copy2(cfg_path, backup)
                    log("[OK] Backed up share.config.json -> share.config.json.bak")
        except (json.JSONDecodeError, OSError):
            pass
    else:
        log("[OK] Creating share.config.json for test")

    cfg_path.write_text(json.dumps(test_cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("[OK] Test share: project root (.)")

    share = ROOT.resolve()
    os.environ["TADAROKAT_SHARED_DATA"] = str(share)
    os.environ["TADAROKAT_MODE"] = "full"
    os.environ["TADAROKAT_HOST"] = "127.0.0.1"
    os.environ["TADAROKAT_PORT"] = "8000"
    return share


def run_install() -> None:
    """Install dependencies using official PyPI (no mirror)."""
    vpy = ROOT / ".venv" / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")
    if (ROOT / ".installed").exists() and vpy.exists():
        try:
            subprocess.run(
                [str(vpy), "-c", "import uvicorn, pandas, fastapi"],
                check=True,
                capture_output=True,
            )
            log("[OK] Install already done (skipped)")
            return
        except subprocess.CalledProcessError:
            pass

    # Force official PyPI and enable verbose output
    pip_env = {
        "PIP_DEFAULT_TIMEOUT": "120",
        "PIP_RETRIES": "5",
        "PIP_VERBOSE": "1",                     # show full installation details
        "PIP_INDEX_URL": "https://pypi.org/simple",   # official PyPI
        "PIP_TRUSTED_HOST": "pypi.org",               # trust the host
    }

    if platform.system() == "Windows":
        script = ROOT / "scripts" / "install_windows.py"
        for base_python in (["py", "-3"], ["python"], ["python3"]):
            try:
                subprocess.run([*base_python, "--version"], capture_output=True, check=True)
                # Remove --quiet to show all output
                run_cmd(
                    [*base_python, str(script)],
                    label="Windows install (verbose)",
                    timeout=900,
                    env=pip_env,
                )
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        fail("Python not found for install")
    else:
        run_cmd(
            ["bash", str(ROOT / "install.sh")],
            label="Linux install (verbose)",
            timeout=900,
            env=pip_env,
        )


def reset_data(share: Path) -> None:
    log("-> Fresh reset (DB + seed staging)")
    for name in ("db_current.db", "db_new.db", "db_old.db", "lock.flag"):
        p = share / name
        if p.exists():
            p.unlink()
    staged = share / "share_users.seed.json"
    if staged.exists():
        staged.unlink()
    log("[OK] Data folder reset")


def stage_test_seed(share: Path) -> None:
    if not TEST_SEED.exists():
        fail(f"Missing {TEST_SEED.name}")
    dest = share / "share_users.seed.json"
    shutil.copy2(TEST_SEED, dest)
    log(f"[OK] Staged test users seed -> {dest}")


def find_excel_source() -> Path | None:
    candidate = ROOT / "input.xlsx"
    if candidate.exists() and candidate.stat().st_size > 1000:
        return candidate
    return None


def setup_excel(share: Path) -> Path | None:
    dest = share / "input.xlsx"
    src = find_excel_source()
    if not src:
        log("[WARN] No Excel file found - skip import (place input.xlsx in project root)")
        return None
    # Copy if not already there or if source is newer
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
        log(f"[OK] Excel copied to {dest}")
    else:
        log(f"[OK] Excel already present: {dest}")
    return dest


def verify_logins(host: str, port: int) -> None:
    base = f"http://{host}:{port}/api/auth/login"
    log("-> Verifying test logins...")
    ok = 0
    for username, password in VERIFY_USERS:
        body = json.dumps({"username": username, "password": password}).encode()
        req = urllib.request.Request(
            base,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _HTTP.open(req, timeout=15) as resp:
                if resp.status == 200:
                    log(f"    [OK] login {username}")
                    ok += 1
                else:
                    log(f"    [FAIL] login {username} HTTP {resp.status}")
        except urllib.error.HTTPError as exc:
            log(f"    [FAIL] login {username} HTTP {exc.code}")
        except urllib.error.URLError as exc:
            fail(f"Server not reachable at {host}:{port} - {exc}")
    if ok != len(VERIFY_USERS):
        fail(f"Login check failed ({ok}/{len(VERIFY_USERS)})")
    log(f"[OK] All {ok} test logins verified")


def start_server(host: str, port: int, open_browser: bool) -> None:
    py = venv_python()
    log("")
    log("==========================================")
    log("  TEST SETUP COMPLETE - STARTING SERVER")
    log("==========================================")
    log(f"  URL: http://{host}:{port}")
    log("  Users: admin/admin123  manager/manager123")
    log("         mostafa/mostafa123  anbar/anbar123")
    log("  Stop: Ctrl+C")
    log("")

    if open_browser and platform.system() == "Windows":
        subprocess.Popen(["cmd", "/c", "start", "", f"http://{host}:{port}/"])

    env = dict(**__import__("os").environ)
    cfg = json.loads((ROOT / "share.config.json").read_text(encoding="utf-8"))
    share = Path(str(cfg.get("shared_data_dir") or "./data"))
    if not share.is_absolute():
        share = (ROOT / share).resolve()
    env["TADAROKAT_SHARED_DATA"] = str(share)
    env["TADAROKAT_MODE"] = str(cfg.get("mode") or "full")
    env["TADAROKAT_HOST"] = host
    env["TADAROKAT_PORT"] = str(port)

    backend = ROOT / "backend"
    raise SystemExit(
        subprocess.run(
            [str(py), "-m", "uvicorn", "main:app", "--host", host, "--port", str(port)],
            cwd=str(backend),
            env=env,
        ).returncode
    )


def wait_for_server(host: str, port: int, timeout: float = 90.0) -> None:
    urls = (f"http://{host}:{port}/api/health", f"http://{host}:{port}/")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for url in urls:
            try:
                with _HTTP.open(url, timeout=3) as resp:
                    if resp.status == 200:
                        log("[OK] Server health check")
                        return
            except Exception:
                pass
        time.sleep(0.5)
    fail(f"Server did not start within {timeout}s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tadarokat one-click test setup")
    parser.add_argument("--fresh", action="store_true", help="Reset DB and re-seed users")
    parser.add_argument("--no-import", action="store_true", help="Skip Excel import")
    parser.add_argument("--no-server", action="store_true", help="Setup only, do not start server")
    parser.add_argument("--no-verify", action="store_true", help="Skip login verification")
    parser.add_argument("--open-browser", action="store_true", help="Open browser (Windows)")
    args = parser.parse_args()

    log("==========================================")
    log("  Tadarokat - TEST SETUP (VERBOSE)")
    log("==========================================")
    log("")

    share = ensure_share_config()
    share.mkdir(parents=True, exist_ok=True)
    (share / "logs").mkdir(exist_ok=True)

    # 1. Install dependencies (with full pip logs, no mirror)
    log("--- Starting installation (verbose output follows) ---")
    run_install()
    py = venv_python()
    log("--- Installation complete ---")

    # 2. Build DB template (runs in venv)
    log("-> Building DB template...")
    run_cmd([str(py), str(ROOT / "scripts" / "build_db_template.py")], label="DB template")

    # 3. Reset data if --fresh
    if args.fresh:
        reset_data(share)

    # 4. Always stage the test seed (will be used if no users exist)
    stage_test_seed(share)

    # 5. Initialize database and seed users (runs in venv)
    log("-> Initializing database and seeding users...")
    seed_script = """
import sys
sys.path.insert(0, 'backend')
from local_config import apply_share_config
apply_share_config()
from services.share_init_service import initialize_share
result = initialize_share(require_seed=True)
print(f"Database: {result['database_path']}")
print(f"Users in DB: {result['user_count']}")
for msg in result.get('messages') or []:
    print(f"    - {msg}")
"""
    run_cmd([str(py), "-c", seed_script], label="Initialize database with seed", timeout=120)

    # 6. Import Excel if available and not skipped
    if not args.no_import:
        excel_path = setup_excel(share)
        if excel_path:
            log("-> Importing Excel data...")
            import_script = """
import sys
sys.path.insert(0, 'backend')
from local_config import apply_share_config
apply_share_config()
from db.import_service import run_import
result = run_import(None)
rows = result.get('row_count') or result.get('rows') or result.get('purchases')
print(f"Excel imported into DB (rows={rows})")
"""
            run_cmd([str(py), "-c", import_script], label="Import Excel", timeout=300)

    # 7. Read config for host/port
    cfg = json.loads((ROOT / "share.config.json").read_text(encoding="utf-8"))
    host = str(cfg.get("host") or "127.0.0.1")
    port = int(cfg.get("port") or 8000)

    # 8. Verify logins (requires server running)
    if not args.no_verify:
        log("-> Starting server for login verification...")
        proc = subprocess.Popen([str(py), str(ROOT / "scripts" / "launcher.py")], cwd=str(ROOT))
        try:
            wait_for_server(host, port)
            verify_logins(host, port)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    # 9. If --no-server, print summary and exit
    if args.no_server:
        log("")
        log("==========================================")
        log("  TEST SETUP COMPLETE")
        log("==========================================")
        log(f"  URL:   http://{host}:{port}")
        log("  Users: admin/admin123  manager/manager123")
        log("         mostafa/mostafa123  anbar/anbar123")
        log("         fabri/fabri123  behnaz/behnaz123")
        log("  Next:  run.bat  (Windows)  or  ./run.sh")
        return

    # 10. Start the server
    start_server(host, port, args.open_browser)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"Unexpected error: {exc}")
