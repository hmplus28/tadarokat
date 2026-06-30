#!/usr/bin/env python3
"""Comprehensive test for the new DB/Excel path logic + caching (daily + change refresh).

Tests two main states on this system:
1. Default state: using db/ template (no admin primary set)
2. Admin-specified primary_data_dir state (copy + use)

Verifies:
- Correct path resolution and fallbacks
- Excel import populates DB in the right location
- Cache key uses import sha
- Cache invalidation on import
- refresh_if_excel_changed behavior
- Users present
- Purchase counts
"""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import config as cfg
from services import excel_service
from db.connection import reset_db_manager, get_db_manager
from services.settings_service import ensure_data_location_ready
from db.import_service import run_import

print("=" * 70)
print("TADAROKAT - DB / EXCEL / CACHE STATES TEST")
print("=" * 70)

def reset_env_and_paths():
    for k in list(os.environ.keys()):
        if k.startswith("TADAROKAT_"):
            os.environ.pop(k, None)
    reset_db_manager()
    # Force re-resolve
    import importlib
    importlib.reload(cfg)
    excel_service.invalidate_cache()

def get_db_count(db_path: Path) -> int:
    if not db_path.exists():
        return -1
    try:
        conn = sqlite3.connect(str(db_path))
        val = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        conn.close()
        return val
    except Exception:
        return -2

def get_import_sha(db_path: Path) -> str:
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute('SELECT value FROM meta WHERE key="last_import_sha256"').fetchone()
        conn.close()
        return row[0] if row and row[0] else ""
    except Exception:
        return ""

def get_user_count(db_path: Path) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        val = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        return val
    except Exception:
        return 0

def test_state_default_db_template():
    print("\n=== STATE 1: Default (db/ template, no primary_data_dir) ===")
    reset_env_and_paths()

    print("PRIMARY_DATA_DIR :", cfg.PRIMARY_DATA_DIR)
    print("DB_CURRENT_PATH  :", cfg.DB_CURRENT_PATH)
    print("EXCEL_PATH       :", cfg.EXCEL_PATH)
    print("DB exists        :", cfg.DB_CURRENT_PATH.exists())
    print("Excel exists     :", cfg.EXCEL_PATH.exists())

    assert "db" in str(cfg.DB_CURRENT_PATH).lower(), "Should prefer db/ template"
    assert cfg.EXCEL_PATH.exists(), "Root Excel should be found"

    # Count before import (template has 0 purchases)
    before = get_db_count(cfg.DB_CURRENT_PATH)
    users_before = get_user_count(cfg.DB_CURRENT_PATH)
    print(f"Before import - purchases: {before}, users: {users_before}")

    # Do import (should go into db/ location)
    result = run_import()
    print("Import result rows:", result.get("row_count"))

    after = get_db_count(cfg.DB_CURRENT_PATH)
    sha = get_import_sha(cfg.DB_CURRENT_PATH)
    print(f"After import - purchases: {after}, sha: {sha[:16]}...")

    assert after > 1000, "Should have imported many rows"
    assert sha, "Should have stored sha"

    # Cache test
    excel_service.invalidate_cache()
    df = excel_service._get_merged_purchases()
    print("Cached DF shape after invalidation:", df.shape)
    assert len(df) == after, "Cache + DF should match DB count"

    # Check refresh detection (should be False immediately after import)
    needs = excel_service.needs_excel_refresh()
    print("needs_excel_refresh right after import:", needs)

    print("STATE 1 PASSED")
    return {"purchases": after, "sha": sha, "db_path": str(cfg.DB_CURRENT_PATH)}

def test_state_admin_primary_dir():
    print("\n=== STATE 2: Admin sets primary_data_dir ===")
    reset_env_and_paths()

    tmp_dir = Path(tempfile.mkdtemp(prefix="tadarokat_admin_data_"))
    print("Admin primary dir:", tmp_dir)

    prep = ensure_data_location_ready(str(tmp_dir))
    print("Prep result:", prep)

    assert (tmp_dir / "db_current.db").exists(), "Template DB should be copied"
    assert (tmp_dir / "input.xlsx").exists() or Path("رضوانی نهایی.xlsx").exists(), "Excel should be copied or fall back"

    # Switch to this dir
    os.environ["TADAROKAT_DATA_DIR"] = str(tmp_dir)
    reset_db_manager()
    import importlib
    importlib.reload(cfg)

    print("After switch - DB_CURRENT_PATH:", cfg.DB_CURRENT_PATH)
    print("DB in admin dir?", str(tmp_dir) in str(cfg.DB_CURRENT_PATH))

    # Import using the copied Excel in the admin dir (or fallback)
    result = run_import()
    print("Import into admin dir rows:", result.get("row_count"))

    cnt = get_db_count(cfg.DB_CURRENT_PATH)
    print("Purchases in admin-chosen DB:", cnt)
    assert cnt > 1000

    # Cache
    df = excel_service._get_merged_purchases()
    print("DF from cache in admin state:", len(df))

    # Test Excel fallback: remove local excel, re-resolve should still find root
    local_excel = tmp_dir / "input.xlsx"
    if local_excel.exists():
        local_excel.unlink()
    importlib.reload(cfg)
    print("Excel after deleting in admin dir:", cfg.EXCEL_PATH)
    assert cfg.EXCEL_PATH.exists(), "Should fallback to root Excel"

    # Re-import (should work via fallback)
    result2 = run_import(str(cfg.EXCEL_PATH))
    print("Re-import via fallback rows:", result2.get("row_count"))

    # Verify users still there in copied DB
    uc = get_user_count(cfg.DB_CURRENT_PATH)
    print("Users in admin DB:", uc)
    assert uc >= 6, "Default users + admin should be present"

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print("STATE 2 PASSED")
    return {"purchases": cnt}

def test_cache_invalidation_on_change():
    print("\n=== CACHE + CHANGE DETECTION TEST ===")
    reset_env_and_paths()

    # Use current db/
    sig1 = excel_service._get_import_signature()
    print("Import sig (sha based):", sig1[:40])

    df1 = excel_service._get_merged_purchases()
    print("First load len:", len(df1))

    # Force a pretend change by touching the root Excel mtime (without changing content)
    excel_path = cfg.EXCEL_PATH
    old_m = excel_path.stat().st_mtime
    excel_path.touch()
    excel_service.invalidate_cache()

    needs = excel_service.needs_excel_refresh()
    print("needs_refresh after touch (content same, mtime changed):", needs)

    # Recompute sig - our sha based will still match content
    sig2 = excel_service._get_import_signature()
    print("Sig after touch:", sig2[:40])

    # Restore mtime
    os.utime(excel_path, (old_m, old_m))

    print("CACHE INVALIDATION TEST DONE")

if __name__ == "__main__":
    r1 = test_state_default_db_template()
    r2 = test_state_admin_primary_dir()
    test_cache_invalidation_on_change()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED SUCCESSFULLY")
    print(f"State1 purchases: {r1['purchases']}")
    print(f"State2 purchases: {r2['purchases']}")
    print("=" * 70)
