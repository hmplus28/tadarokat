#!/usr/bin/env python3
"""One-time share setup - run once by IT."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from local_config import apply_share_config  # noqa: E402

apply_share_config()

from services.share_init_service import initialize_share  # noqa: E402


def main() -> None:
    try:
        result = initialize_share(require_seed=True)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1) from exc
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        raise SystemExit(1) from exc

    print("[OK] Share initialized")
    print(f"  DB: {result['database_path']}")
    print(f"  Users: {result['user_count']}")
    for msg in result.get("messages") or []:
        print(f"  - {msg}")
    print("  [NOTE] Seed file was removed. Keep passwords in a safe place.")


if __name__ == "__main__":
    main()