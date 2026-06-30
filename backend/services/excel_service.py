import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import EXCEL_PATH, PURCHASE_EDITABLE, SHEETS, STORAGE_BACKEND
from services import local_storage

_cache: Dict[str, tuple] = {}

_FLOW_STATUS_RANK = {"در انتظار": 0, "ثبت استعلام": 1, "دستور شده": 2, "تحویل شده": 3}

PURCHASE_LIST_COLS = [
    "شماره", "شماره مبنا", "تاریخ درخواست کالا", "عنوان قلم خریدنی",
    "کد قلم خریدنی", "نوع قلم خریدنی", "تاریخ", "تاریخ نیاز", "وضعیت",
    "رمز فوریت", "کارشناس خرید", "نوع خرید", "شماره استعلام",
    "درخواست کننده", "توضیحات", "مهلت استعلام",
]

INQUIRY_SEARCH_COLS = ["شماره استعلام", "وضعیت", "صادر کننده سند", "توضیحات", "شماره درخواست خرید"]


def _mtime() -> float:
    return EXCEL_PATH.stat().st_mtime if EXCEL_PATH.exists() else 0.0


def _local_mtime() -> float:
    if STORAGE_BACKEND == "sqlite":
        from config import DB_CURRENT_PATH
        return DB_CURRENT_PATH.stat().st_mtime if DB_CURRENT_PATH.exists() else 0.0
    return local_storage.LOCAL_EXCEL_PATH.stat().st_mtime if local_storage.LOCAL_EXCEL_PATH.exists() else 0.0


def _db_mtime() -> float:
    from config import DB_CURRENT_PATH
    return DB_CURRENT_PATH.stat().st_mtime if DB_CURRENT_PATH.exists() else 0.0


def _get_import_signature() -> str:
    """Reliable cache key based on last successful import (better than mtime after swaps/copies)."""
    try:
        from db.connection import get_db_manager
        mgr = get_db_manager()
        if not mgr.db_path.exists():
            return "no-db"
        with mgr.connect(write=False) as conn:
            sha = mgr.get_meta(conn, "last_import_sha256") or ""
            ver = mgr.get_meta(conn, "db_version") or ""
            at = mgr.get_meta(conn, "last_import_at") or ""
            return f"{sha}:{ver}:{at}"[:128]
    except Exception:
        return f"fallback:{_db_mtime()}"


def _current_excel_signature(path: Path = None) -> str:
    p = path or EXCEL_PATH
    if not p or not p.exists():
        return "no-excel"
    try:
        import hashlib
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        mtime = p.stat().st_mtime
        return f"{h.hexdigest()}:{mtime}"
    except Exception:
        return f"err:{p.stat().st_mtime if p.exists() else 0}"


def needs_excel_refresh() -> bool:
    """True if the Excel on disk differs from the last imported version (sha based)."""
    try:
        from db.connection import get_db_manager
        mgr = get_db_manager()
        if not mgr.db_path.exists():
            return True
        with mgr.connect(write=False) as conn:
            last_sha = mgr.get_meta(conn, "last_import_sha256")
        if not last_sha:
            return True
        curr_sig = _current_excel_signature()
        return last_sha not in curr_sig   # if last sha not in current signature, it changed
    except Exception:
        return True



def _read_purchases_from_db() -> pd.DataFrame:
    import json
    from db.connection import get_db_manager

    mgr = get_db_manager()
    if not mgr.db_path.exists():
        return pd.DataFrame()
    with mgr.connect(write=False) as conn:
        rows = conn.execute("SELECT row_json FROM purchases ORDER BY id").fetchall()
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        try:
            records.append(json.loads(r["row_json"]))
        except json.JSONDecodeError:
            continue
    df = pd.DataFrame(records)
    if not df.empty:
        df.columns = [_normalize_col_name(c) for c in df.columns]
    df = _canonicalize_columns(df)
    return df


def warm_cache() -> None:
    local_storage.ensure_local_workbook()
    try:
        if STORAGE_BACKEND == "sqlite":
            _get_merged_purchases()
        else:
            _read_source_sheet("purchases")
            _get_merged_purchases()
    except Exception:
        pass


def _normalize_col_name(name: str) -> str:
    return " ".join(str(name).replace("\n", " ").replace("\r", " ").split()).strip()

def _canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map variant column names from user's Excel to the canonical names used in the app logic.
    Prevents duplicate columns (e.g. both 'شماره' and 'شماره درخواست خرید' mapping to same).
    """
    if df.empty:
        return df
    col_map = {}
    seen = set()
    for col in list(df.columns):
        c = str(col).strip()
        target = None
        
        # شماره درخواست (فقط شماره اصلی، نه شماره مبنا)
        if c in ("شماره", "شماره درخواست خرید", "شماره خرید"):
            target = "شماره"
        elif c == "شماره درخواست کالا":
            target = "شماره مبنا"
        
        # وضعیت
        elif c in ("وضعیت", "وضعیت درخواست خرید"):
            target = "وضعیت"
        elif c == "وضعیت سفارش":
            target = "وضعیت سفارش"
        elif c == "شماره تحویل":
            target = "شماره تحویل"
        
        # کارشناس
        elif c in ("کارشناس خرید", "نام کارشناس خرید"):
            target = "کارشناس خرید"
        
        # نوع خرید
        elif c == "نوع خرید":
            target = "نوع خرید"
        elif c == "نوع قلم خریدنی":
            target = "نوع قلم خریدنی"
        elif c == "روند خرید":
            target = "نوع خرید"
        
        # فوریت
        elif c in ("رمز فوریت", "فوریت"):
            target = "رمز فوریت"
        
        # تاریخ
        elif c in ("تاریخ", "تاریخ درخواست"):
            target = "تاریخ"
        elif c == "تاریخ درخواست کالا":
            target = "تاریخ درخواست کالا"
        elif c in ("تاریخ نیاز درخواست خرید", "تاریخ نیاز"):
            target = "تاریخ نیاز"
        elif c == "تاریخ تحویل":
            target = "تاریخ تحویل"
        
        # کد قلم خریدنی
        elif c == "کد قلم خریدنی":
            target = "کد قلم خریدنی"
        
        # عنوان قلم خریدنی
        elif c in ("عنوان قلم خریدنی", "نام قلم خریدنی", "عنوان کالا"):
            target = "عنوان قلم خریدنی"
        
        # درخواست کننده
        elif c in ("درخواست کننده", "درخواست‌کننده"):
            target = "درخواست کننده"
        
        # توضیحات
        elif c in ("توضیحات", "توضیحات درخواست خرید", "شرح"):
            target = "توضیحات"
        
        # مقدار درخواست
        elif c in ("مقدار درخواست", "تعداد"):
            target = "مقدار درخواست"
        
        # واحد سنجش
        elif c in ("واحد سنجش", "واحد"):
            target = "واحد سنجش"
        
        # واحد تامین
        elif c in ("واحد تامین", "انبار"):
            target = "واحد تامین"
        
        # استعلام
        elif c == "شماره استعلام":
            target = "شماره استعلام"
        elif c == "مهلت استعلام":
            target = "مهلت استعلام"
        
        if target and target not in seen:
            col_map[col] = target
            seen.add(target)
    
    if col_map:
        df = df.rename(columns=col_map)
    
    # ✅ FIX: Convert "شماره" column to clean string (remove .0 suffix)
    if "شماره" in df.columns:
        def clean_purchase_number(x):
            if pd.isna(x):
                return x
            s = str(x).strip()
            # Remove .0 suffix for float numbers (e.g., "13.0" -> "13")
            if s.endswith(".0") and s[:-2].replace("-", "").isdigit():
                s = s[:-2]
            return s
        df["شماره"] = df["شماره"].apply(clean_purchase_number)
    
    # Drop any duplicate columns that may have slipped through (keep first)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    return df


def _read_source_sheet(sheet_key: str) -> pd.DataFrame:
    sheet_name = SHEETS[sheet_key]
    cache_key = f"src_{sheet_key}"
    mtime = _mtime()
    cached = _cache.get(cache_key)
    if cached and cached[0] == mtime:
        return cached[1]

    if not EXCEL_PATH.exists():
        df = pd.DataFrame()
        _cache[cache_key] = (mtime, df)
        return df

    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        try:
            xl = pd.ExcelFile(EXCEL_PATH, engine="openpyxl")
            if sheet_name not in xl.sheet_names and xl.sheet_names:
                df = pd.read_excel(EXCEL_PATH, sheet_name=xl.sheet_names[0], engine="openpyxl")
            else:
                df = pd.DataFrame()
        except Exception:
            df = pd.DataFrame()

    df.columns = [_normalize_col_name(c) for c in df.columns]
    _cache[cache_key] = (mtime, df)
    return df


def invalidate_cache() -> None:
    _cache.clear()
    try:
        from services.kpi_service import invalidate_kpi_cache
        invalidate_kpi_cache()
    except ImportError:
        pass


def refresh_if_excel_changed() -> bool:
    """Bust cache if the Excel file on disk is different from what was last imported into DB.
    Call this on startup or before heavy reads for 'daily + change' refresh behavior.
    Full import is still required to update the underlying purchases table.
    """
    if needs_excel_refresh():
        invalidate_cache()
        try:
            warm_cache()
        except Exception:
            pass
        return True
    return False


def _workflow_cache_key() -> tuple:
    return (_db_mtime(), _local_mtime())


def _get_workflow_snapshot() -> dict:
    """یک‌بار خواندن استعلام/دستور و ساخت نگاشت‌های سریع."""
    key = _workflow_cache_key()
    cached = _cache.get("workflow_snapshot")
    if cached and cached[0] == key:
        return cached[1]

    from services.order_stages import normalize_stage, order_is_delivered

    issued = local_storage.get_issued_inquiries()
    orders_df = local_storage.get_orders()

    ordered_inq_nums: set = set()
    if not orders_df.empty and "شماره استعلام" in orders_df.columns:
        ordered_inq_nums = set(orders_df["شماره استعلام"].astype(str).tolist())

    purchase_inquiries: Dict[str, list] = {}
    if not issued.empty and "شماره درخواست خرید" in issued.columns:
        for _, row in issued.iterrows():
            pn = _normalize_id(row.get("شماره درخواست خرید", ""))
            if pn:
                purchase_inquiries.setdefault(pn, []).append(row)

    flow_by_key: Dict[tuple, str] = {}
    if not orders_df.empty:
        for _, o in orders_df.iterrows():
            pn = _normalize_id(o.get("شماره خرید"))
            if not pn:
                continue
            title = str(o.get("عنوان کالا") or "").strip()
            st = "تحویل شده" if order_is_delivered(o.to_dict()) else "دستور شده"
            for fk in ((pn, title), (pn, "")):
                cur = flow_by_key.get(fk, "در انتظار")
                if _FLOW_STATUS_RANK[st] > _FLOW_STATUS_RANK.get(cur, 0):
                    flow_by_key[fk] = st

    for pn in purchase_inquiries:
        fk = (pn, "")
        cur = flow_by_key.get(fk, "در انتظار")
        if _FLOW_STATUS_RANK["ثبت استعلام"] > _FLOW_STATUS_RANK.get(cur, 0):
            flow_by_key[fk] = "ثبت استعلام"

    snap = {
        "issued": issued,
        "orders": orders_df,
        "ordered_inq_nums": ordered_inq_nums,
        "purchase_inquiries": purchase_inquiries,
        "flow_by_key": flow_by_key,
    }
    _cache["workflow_snapshot"] = (key, snap)
    return snap


def _expert_inquiry_purchase_set(expert: Optional[str], snap: dict) -> set:
    if not expert:
        return set(snap["purchase_inquiries"].keys())
    out: set = set()
    for pn, rows in snap["purchase_inquiries"].items():
        if any(_expert_matches_inquiry(expert, r) for r in rows):
            out.add(pn)
    return out


def _enrich_purchase_inquiry_flags(df: pd.DataFrame, expert: Optional[str] = None) -> pd.DataFrame:
    df = _canonicalize_columns(df)
    if df.empty or "شماره" not in df.columns:
        df = df.copy()
        df["has_local_inquiry"] = False
        df["local_inquiry_number"] = None
        df["inquiry_approved"] = False
        return df

    snap = _get_workflow_snapshot()
    expert_pns = _expert_inquiry_purchase_set(expert, snap)
    ordered_inq_nums = snap["ordered_inq_nums"]
    purchase_inquiries = snap["purchase_inquiries"]

    pn_has: Dict[str, bool] = {}
    pn_inq: Dict[str, str] = {}
    pn_approved: Dict[str, bool] = {}

    for pn, rows in purchase_inquiries.items():
        if expert and pn not in expert_pns:
            continue
        pn_has[pn] = True
        for row in rows:
            inq = str(row.get("شماره استعلام", "")).strip()
            if inq:
                pn_inq.setdefault(pn, inq)
                if inq in ordered_inq_nums:
                    pn_approved[pn] = True

    df = df.copy()
    keys = df["شماره"] if "شماره" in df.columns else pd.Series([""] * len(df), index=df.index)
    if isinstance(keys, pd.DataFrame):
        keys = keys.iloc[:, 0]
    keys = keys.map(_normalize_id)
    if expert:
        df["has_local_inquiry"] = keys.map(lambda k: k in expert_pns)
        df["local_inquiry_number"] = keys.map(lambda k: pn_inq.get(k) if k in expert_pns else None)
        df["inquiry_approved"] = keys.map(lambda k: pn_approved.get(k, False) if k in expert_pns else False)
    else:
        df["has_local_inquiry"] = keys.map(lambda k: pn_has.get(k, False))
        df["local_inquiry_number"] = keys.map(lambda k: pn_inq.get(k))
        df["inquiry_approved"] = keys.map(lambda k: pn_approved.get(k, False))
    return df


def _vectorized_flow_status(df: pd.DataFrame, expert: Optional[str] = None) -> pd.Series:
    df = _canonicalize_columns(df)
    snap = _get_workflow_snapshot()
    flow = snap["flow_by_key"]
    expert_pns = _expert_inquiry_purchase_set(expert, snap) if expert else None
    pns = df["شماره"].map(_normalize_id) if "شماره" in df.columns else pd.Series([""] * len(df), index=df.index)
    titles = (
        df["عنوان قلم خریدنی"].astype(str).str.strip()
        if "عنوان قلم خریدنی" in df.columns
        else pd.Series([""] * len(df), index=df.index)
    )

    def _one(pn: str, title: str) -> str:
        if expert and pn not in expert_pns:
            for fk in ((pn, title), (pn, "")):
                st = flow.get(fk)
                if st and st != "در انتظار":
                    return st
            return "در انتظار"
        for fk in ((pn, title), (pn, "")):
            if fk in flow:
                return flow[fk]
        return "در انتظار"

    return pd.Series([_one(pn, t) for pn, t in zip(pns, titles)], index=df.index)


def _enrich_purchase_current_status(df: pd.DataFrame, expert: Optional[str] = None) -> pd.DataFrame:
    df = _canonicalize_columns(df.copy())
    df["وضعیت فعلی خرید"] = _vectorized_flow_status(df, expert=expert)
    return df


def _enrich_purchase_page(df: pd.DataFrame, expert: Optional[str] = None) -> pd.DataFrame:
    if df.empty:
        return df
    df = _enrich_purchase_inquiry_flags(df, expert=expert)
    return _enrich_purchase_current_status(df, expert=expert)


def _apply_inquiry_panel_fields(df: pd.DataFrame) -> pd.DataFrame:
    """نوع خرید و اولویت از استعلام‌های صادرشده در پنل — اولویت بر داده اکسل."""
    issued = local_storage.get_issued_inquiries()
    if issued.empty or "شماره درخواست خرید" not in issued.columns:
        return df
    if df.empty or "شماره" not in df.columns:
        return df

    work = issued.copy()
    if "created_at" in work.columns:
        work = work.sort_values(by="created_at", ascending=False, na_position="last")
    elif "شماره استعلام" in work.columns:
        work = work.sort_values(by="شماره استعلام", ascending=False, na_position="last")

    latest: Dict[str, dict] = {}
    for _, row in work.iterrows():
        pn = _normalize_id(row.get("شماره درخواست خرید", ""))
        if pn and pn not in latest:
            latest[pn] = row.to_dict()

    if not latest:
        return df

    df = df.copy()
    keys = df["شماره"].map(_normalize_id)
    for col in ("نوع خرید", "رمز فوریت"):
        if col not in df.columns:
            continue
        for pn, inq in latest.items():
            val = inq.get(col)
            if val is None or not str(val).strip():
                continue
            mask = keys == pn
            if mask.any():
                df.loc[mask, col] = val
    return df

def _apply_purchase_current_status(df: pd.DataFrame) -> pd.DataFrame:
    """محاسبه خودکار 'وضعیت فعلی خرید' بر اساس ستون‌های پر شده در اکسل.
    ترتیب مراحل: درخواست → استعلام → دستور خرید → سفارش → پرداخت → تحویل
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    def determine_status(row):
        # 1. تحویل شده (اولویت بالاترین)
        if _has_value(row.get("تاریخ تحویل")) or _has_value(row.get("شماره تحویل")) or _has_value(row.get("مقدار تحویل")):
            return "تحویل شده"
        
        # 2. پرداخت شده
        if _has_value(row.get("تاریخ ثبت واریزی")) or _has_value(row.get("تاریخ انجام واریزی")):
            return "پرداخت شده"
        if _has_value(row.get("شماره درخواست پرداخت")):
            return "در انتظار پرداخت"
        
        # 3. سفارش صادر شده
        if _has_value(row.get("شماره سفارش")):
            return "سفارش صادر شده"
        
        # 4. دستور خرید صادر شده
        if _has_value(row.get("شماره دستور خرید")):
            return "دستور خرید صادر شده"
        
        # 5. استعلام صادر شده
        if _has_value(row.get("شماره استعلام")):
            return "استعلام صادر شده"
        
        # 6. در انتظار استعلام (پیش‌فرض)
        return "در انتظار استعلام"
    
    df["وضعیت فعلی خرید"] = df.apply(determine_status, axis=1)
    return df

def sync_deliveries_from_excel(username: str = "system") -> int:
    """Sync delivery data from main Excel to local_storage - optimized."""
    from services import local_storage
    
    print("[INFO] Starting sync_deliveries_from_excel...")
    df = _get_merged_purchases()
    if df.empty:
        return 0
    
    # Check if delivery columns exist
    if "شماره تحویل" not in df.columns and "تاریخ تحویل" not in df.columns:
        return 0
    
    # Find rows with delivery data (optimized)
    has_delivery = pd.Series(False, index=df.index)
    
    if "شماره تحویل" in df.columns:
        mask = df["شماره تحویل"].notna() & (df["شماره تحویل"].astype(str).str.strip() != "") & (df["شماره تحویل"].astype(str).str.lower() != "nan")
        has_delivery |= mask
    
    if "تاریخ تحویل" in df.columns:
        mask = df["تاریخ تحویل"].notna() & (df["تاریخ تحویل"].astype(str).str.strip() != "") & (df["تاریخ تحویل"].astype(str).str.lower() != "nan")
        has_delivery |= mask
    
    if not has_delivery.any():
        return 0
    
    delivery_rows = df[has_delivery].copy()
    count = 0
    
    # ✅ OPTIMIZATION: Get all existing delivery numbers once
    existing_deliveries_df = local_storage.get_deliveries()
    existing_numbers = set()
    if not existing_deliveries_df.empty and "شماره تحویل" in existing_deliveries_df.columns:
        existing_numbers = set(existing_deliveries_df["شماره تحویل"].astype(str).str.strip())
    
    print(f"[INFO] Processing {len(delivery_rows)} delivery rows...")
    
    for idx, row in delivery_rows.iterrows():
        purchase_number = str(row.get("شماره") or "").strip()
        delivery_number = str(row.get("شماره تحویل") or "").strip()
        
        # Normalize delivery number (remove .0 suffix)
        if delivery_number.endswith(".0") and delivery_number[:-2].replace("-", "").isdigit():
            delivery_number = delivery_number[:-2]
        
        delivery_date = str(row.get("تاریخ تحویل") or "").strip()
        quantity = row.get("مقدار تحویل")
        
        if not delivery_number and not delivery_date:
            continue
        
        # ✅ OPTIMIZATION: Fast check using set
        if delivery_number and delivery_number in existing_numbers:
            continue
        
        # Normalize purchase number
        if purchase_number.endswith(".0") and purchase_number[:-2].replace("-", "").isdigit():
            purchase_number = purchase_number[:-2]
        
        # Create delivery record
        payload = {
            "شماره تحویل": delivery_number or f"DL-{purchase_number}",
            "شماره دستور": "",
            "شماره خرید": purchase_number,
            "عنوان کالا": str(row.get("عنوان قلم خریدنی") or ""),
            "انبار": str(row.get("واحد تامین") or ""),
            "مقدار": quantity,
            "واحد": str(row.get("واحد سنجش") or ""),
            "تاریخ تحویل": delivery_date,
            "تحویل گیرنده": "",
            "وضعیت": "تحویل شده",
            "توضیحات": f"Sync از اکسل - خرید {purchase_number}",
        }
        
        try:
            local_storage.append_delivery(payload, username)
            existing_numbers.add(delivery_number)  # Add to set to avoid duplicates
            count += 1
            if count % 50 == 0:
                print(f"[INFO] Synced {count} deliveries...")
        except Exception as e:
            print(f"[WARN] Failed to sync delivery for purchase {purchase_number}: {e}")
    
    if count:
        invalidate_cache()
        print(f"[OK] Synced {count} deliveries from Excel")
    
    return count

def sync_orders_from_excel(username: str = "system") -> int:
    """Sync order data from main Excel to local_storage."""
    from services import local_storage
    
    print("[INFO] Starting sync_orders_from_excel...")
    df = _get_merged_purchases()
    if df.empty:
        return 0
    
    # Check if order columns exist
    if "شماره دستور خرید" not in df.columns:
        return 0
    
    # Find rows with order data
    has_order = pd.Series(False, index=df.index)
    
    if "شماره دستور خرید" in df.columns:
        mask = df["شماره دستور خرید"].notna() & (df["شماره دستور خرید"].astype(str).str.strip() != "") & (df["شماره دستور خرید"].astype(str).str.lower() != "nan")
        has_order |= mask
    
    if not has_order.any():
        return 0
    
    order_rows = df[has_order].copy()
    count = 0
    
    # ✅ OPTIMIZATION: Get all existing order numbers once
    existing_orders_df = local_storage.get_orders()
    existing_numbers = set()
    if not existing_orders_df.empty and "شماره دستور" in existing_orders_df.columns:
        existing_numbers = set(existing_orders_df["شماره دستور"].astype(str).str.strip())
    
    print(f"[INFO] Processing {len(order_rows)} order rows...")
    
    for idx, row in order_rows.iterrows():
        purchase_number = str(row.get("شماره") or "").strip()
        order_number = str(row.get("شماره دستور خرید") or "").strip()
        
        # Normalize order number (remove .0 suffix)
        if order_number.endswith(".0") and order_number[:-2].replace("-", "").isdigit():
            order_number = order_number[:-2]
        
        order_date = str(row.get("تاریخ دستور خرید") or "").strip()
        
        if not order_number:
            continue
        
        # ✅ OPTIMIZATION: Fast check using set
        if order_number in existing_numbers:
            continue
        
        # Normalize purchase number
        if purchase_number.endswith(".0") and purchase_number[:-2].replace("-", "").isdigit():
            purchase_number = purchase_number[:-2]
        
        # Determine current stage
        delivery_number = str(row.get("شماره تحویل") or "").strip()
        if delivery_number.endswith(".0") and delivery_number[:-2].replace("-", "").isdigit():
            delivery_number = delivery_number[:-2]
        
        delivery_date = str(row.get("تاریخ تحویل") or "").strip()
        payment_date = str(row.get("تاریخ ثبت واریزی") or "").strip()
        
        if delivery_date or delivery_number:
            stage = "تحویل"
            status = "تحویل شده"
        elif payment_date:
            stage = "پرداخت"
            status = "پرداخت شده"
        else:
            stage = "دستور خرید"
            status = "در جریان"
        
        # Create order record
        payload = {
            "شماره دستور": order_number,
            "شماره استعلام": str(row.get("شماره استعلام") or ""),
            "شماره خرید": purchase_number,
            "عنوان کالا": str(row.get("عنوان قلم خریدنی") or ""),
            "انبار": str(row.get("واحد تامین") or ""),
            "تعداد": row.get("مقدار درخواست"),
            "واحد": str(row.get("واحد سنجش") or ""),
            "کارشناس": str(row.get("کارشناس خرید") or ""),
            "نام پیمانکار": str(row.get("تامین کننده") or ""),
            "وضعیت": status,
            "مرحله فعلی": stage,
            "تاریخ دستور": order_date,
            "تاریخ سفارش": str(row.get("تاریخ سفارش") or ""),
            "شماره سفارش": str(row.get("شماره سفارش") or ""),
            "تاریخ تحویل": delivery_date,
            "شماره تحویل": delivery_number,
            "توضیحات": f"Sync از اکسل - خرید {purchase_number}",
            "صادر کننده": "system",
        }
        
        try:
            local_storage.append_order(payload, username)
            existing_numbers.add(order_number)  # Add to set to avoid duplicates
            count += 1
            if count % 50 == 0:
                print(f"[INFO] Synced {count} orders...")
        except Exception as e:
            print(f"[WARN] Failed to sync order for purchase {purchase_number}: {e}")
    
    if count:
        invalidate_cache()
        print(f"[OK] Synced {count} orders from Excel")
    
    return count

def _has_value(val) -> bool:
    """بررسی اینکه یک مقدار واقعاً پر شده است (نه خالی، None، NaN، یا رشته خالی)."""
    if val is None:
        return False
    if pd.isna(val):
        return False
    s = str(val).strip()
    if not s:
        return False
    # مقادیری مثل "—" یا "None" یا "nan" را خالی در نظر بگیر
    if s.lower() in ("—", "-", "none", "nan", "null", ""):
        return False
    return True


def _apply_purchase_edits(df: pd.DataFrame) -> pd.DataFrame:
    edits = local_storage.get_purchase_edits()
    if edits.empty or "شماره" not in df.columns:
        return df

    df = df.copy()
    df["_key"] = df["شماره"].astype(str)
    edits = edits.copy()
    edits["_key"] = edits["شماره"].astype(str)
    edits = edits.set_index("_key")

    for key in edits.index:
        mask = df["_key"] == key
        if not mask.any():
            continue
        for col in PURCHASE_EDITABLE:
            if col in edits.columns and col in df.columns:
                val = edits.at[key, col]
                if pd.notna(val) and str(val).strip() != "":
                    if pd.api.types.is_numeric_dtype(df[col]):
                        val = pd.to_numeric(val, errors="coerce")
                    df.loc[mask, col] = val
        if "overrides_json" in edits.columns:
            import json
            raw = edits.at[key, "overrides_json"]
            if pd.notna(raw) and str(raw).strip():
                try:
                    extra = json.loads(raw) if isinstance(raw, str) else dict(raw)
                    for col, val in extra.items():
                        if col in df.columns and val is not None and str(val).strip() != "":
                            if pd.api.types.is_numeric_dtype(df[col]):
                                val = pd.to_numeric(val, errors="coerce")
                            df.loc[mask, col] = val
                except Exception:
                    pass
    return df.drop(columns=["_key"])


def _get_merged_purchases() -> pd.DataFrame:
    cache_key = "merged_purchases"
    if STORAGE_BACKEND == "sqlite":
        sig = _get_import_signature()
        cached = _cache.get(cache_key)
        if cached and cached[0] == ("sqlite", sig):
            return cached[1]
        df = _read_purchases_from_db()
        df = _canonicalize_columns(df)
        df = _apply_purchase_current_status(df)
        df = _apply_inquiry_panel_fields(df)
        df = _apply_purchase_edits(df)
        _cache[cache_key] = (("sqlite", sig), df)
        return df

    src_mtime = _mtime()
    loc_mtime = _local_mtime()
    cached = _cache.get(cache_key)
    if cached and cached[0] == (src_mtime, loc_mtime):
        return cached[1]

    df = _read_source_sheet("purchases")
    df = _canonicalize_columns(df)
    df = _apply_purchase_current_status(df)
    df = _apply_inquiry_panel_fields(df)
    df = _apply_purchase_edits(df)
    _cache[cache_key] = ((src_mtime, loc_mtime), df)
    return df


def _issued_to_inquiry_df() -> pd.DataFrame:
    issued = local_storage.get_issued_inquiries()
    if issued.empty:
        return pd.DataFrame(columns=[
            "شماره استعلام", "تاریخ استعلام", "وضعیت", "مهلت استعلام",
            "واحد/رمز تامین", "توضیحات", "صادر کننده سند", "شماره درخواست خرید",
        ])
    df = issued.copy()
    df["_source"] = "local"
    return df


def _get_merged_inquiries() -> pd.DataFrame:
    """استعلام‌ها فقط از داده محلی — اکسل منبع فقط درخواست خرید دارد."""
    return _issued_to_inquiry_df()


def _normalize_id(val: Any) -> str:
    s = str(val).strip()
    if s.endswith(".0") and s[:-2].replace("-", "").isdigit():
        return s[:-2]
    return s


def _json_safe(val: Any) -> Any:
    if isinstance(val, dict):
        return {k: _json_safe(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_json_safe(v) for v in val]
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(val, "item"):
        try:
            return _json_safe(val.item())
        except (ValueError, AttributeError):
            pass
    return val


def _clean(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if pd.isna(val):
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime("%Y/%m/%d")
    if isinstance(val, float) and val == int(val):
        return int(val)
    if isinstance(val, bool):
        return val
    return val


def _value_counts_dict(series: pd.Series, dropna: bool = True) -> Dict[str, int]:
    counts = series.value_counts(dropna=dropna)
    result: Dict[str, int] = {}
    for key, count in counts.items():
        cleaned = _clean(key)
        label = "نامشخص" if cleaned is None else str(cleaned)
        result[label] = result.get(label, 0) + int(count)
    return result


def _is_filled(val: Any) -> bool:
    cleaned = _clean(val)
    if cleaned is None:
        return False
    s = str(cleaned).strip()
    return s not in ("", "—", "nan", "None", "NaT")


def _records(df: pd.DataFrame, only_filled: bool = False) -> List[Dict]:
    if df.empty:
        return []
    rows = df.to_dict(orient="records")
    out = []
    for row in rows:
        cleaned = {k: _clean(v) for k, v in row.items() if not str(k).startswith("_")}
        if only_filled:
            cleaned = {k: v for k, v in cleaned.items() if _is_filled(v)}
        if cleaned:
            out.append(cleaned)
    return out


def _paginate(df: pd.DataFrame, page: int, page_size: int, *, cap: int = 200) -> Tuple[pd.DataFrame, int]:
    total = len(df)
    if total == 0:
        return df, 0
    page = max(1, page)
    page_size = max(1, min(page_size, cap))
    start = (page - 1) * page_size
    return df.iloc[start : start + page_size], total


def _paginated(df: pd.DataFrame, page: int, page_size: int, columns: Optional[List[str]] = None) -> Dict:
    if columns:
        cols = [c for c in columns if c in df.columns]
        df = df[cols] if cols else df
    chunk, total = _paginate(df, page, page_size)
    pages = math.ceil(total / page_size) if total else 0
    return {
        "items": _records(chunk),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": pages,
    }


def _search_df(df: pd.DataFrame, search: str, columns: List[str]) -> pd.DataFrame:
    q = search.strip().lower()
    if not q:
        return df
    mask = pd.Series(False, index=df.index)
    for col in columns:
        if col in df.columns:
            mask |= df[col].astype(str).str.lower().str.contains(q, na=False)
    return df[mask]


def _filter_expert_purchases(df: pd.DataFrame, expert: Optional[str]) -> pd.DataFrame:
    if expert and "کارشناس خرید" in df.columns:
        return df[df["کارشناس خرید"].astype(str).str.contains(expert, na=False)]
    return df


def _purchase_level_df(df: pd.DataFrame) -> pd.DataFrame:
    """تجمیع به سطح درخواست خرید — یک ردیف به ازای هر «شماره»."""
    df = _canonicalize_columns(df)
    if df.empty or "شماره" not in df.columns:
        return df
    return df.drop_duplicates(subset=["شماره"], keep="first").copy()


def _filter_purchases(df: pd.DataFrame, filter_type: str) -> pd.DataFrame:
    """Filter purchases based on filter_type."""
    if filter_type == "no_inquiry":
        # ✅ فقط مواردی که استعلام ندارند و در مراحل اولیه هستند
        mask = pd.Series(True, index=df.index)
        
        # شماره استعلام خالی باشد
        if "شماره استعلام" in df.columns:
            mask &= df["شماره استعلام"].isna() | (df["شماره استعلام"].astype(str).str.strip() == "") | (df["شماره استعلام"].astype(str).str.lower() == "nan")
        
        # در مراحل بعدی نباشد (دستور خرید، سفارش، تحویل، پرداخت)
        if "شماره دستور خرید" in df.columns:
            mask &= df["شماره دستور خرید"].isna() | (df["شماره دستور خرید"].astype(str).str.strip() == "")
        
        if "شماره سفارش" in df.columns:
            mask &= df["شماره سفارش"].isna() | (df["شماره سفارش"].astype(str).str.strip() == "")
        
        if "شماره تحویل" in df.columns:
            mask &= df["شماره تحویل"].isna() | (df["شماره تحویل"].astype(str).str.strip() == "")
        
        if "تاریخ تحویل" in df.columns:
            mask &= df["تاریخ تحویل"].isna() | (df["تاریخ تحویل"].astype(str).str.strip() == "")
        
        return df[mask]
    
    elif filter_type == "inquiry":
        # مواردی که استعلام دارند
        if "شماره استعلام" in df.columns:
            mask = df["شماره استعلام"].notna() & (df["شماره استعلام"].astype(str).str.strip() != "") & (df["شماره استعلام"].astype(str).str.lower() != "nan")
            return df[mask]
    
    return df

def _stats_from_df(df: pd.DataFrame) -> dict:
    lines_total = int(len(df))
    if "has_local_inquiry" in df.columns:
        has_inquiry = df["has_local_inquiry"].fillna(False).astype(bool)
    else:
        has_inquiry = pd.Series([False] * len(df), index=df.index)
    status_col = "وضعیت" if "وضعیت" in df.columns else None
    order_status_col = "وضعیت سفارش" if "وضعیت سفارش" in df.columns else None
    delivery_col = "شماره تحویل" if "شماره تحویل" in df.columns else None
    expert_col = "کارشناس خرید" if "کارشناس خرید" in df.columns else None
    type_col = "نوع خرید" if "نوع خرید" in df.columns else None
    purchase_count = int(df[status_col].isin(["در جریان", "تایید شده", "ثبت شده"]).sum()) if status_col else 0
    returned_count = int((df[status_col] == "معلق").sum()) if status_col else 0
    in_progress_count = int((df[status_col] == "در جریان").sum()) if status_col else 0
    # Closed: order status closed AND has delivery number (for correct closed stats per expert)
    if order_status_col and delivery_col:
        closed_mask = (df[order_status_col] == "بسته شده") & df[delivery_col].notna() & (df[delivery_col].astype(str).str.strip() != "")
        closed_count = int(closed_mask.sum())
    else:
        closed_count = int((df[status_col] == "بسته شده").sum()) if status_col else 0
    return {
        "total": lines_total,
        "total_lines": lines_total,
        "purchase": purchase_count,
        "inquiry": int(has_inquiry.sum()),
        "returned": returned_count,
        "closed": closed_count,
        "in_progress": in_progress_count,
        "by_status": _value_counts_dict(df[status_col]) if status_col else {},
        "by_expert": _value_counts_dict(df[expert_col], dropna=False) if expert_col else {},
        "by_type": _value_counts_dict(df[type_col], dropna=False) if type_col else {},
    }


def _summary_from_df(df: pd.DataFrame) -> dict:
    status_col = "وضعیت" if "وضعیت" in df.columns else None
    type_col = "نوع خرید" if "نوع خرید" in df.columns else None
    urgency_col = "رمز فوریت" if "رمز فوریت" in df.columns else None
    date_col = "تاریخ" if "تاریخ" in df.columns else None
    return {
        "total_amount_items": int(len(df)),
        "total_lines": int(len(df)),
        "status_breakdown": _value_counts_dict(df[status_col]) if status_col else {},
        "purchase_type_breakdown": _value_counts_dict(df[type_col], dropna=False) if type_col else {},
        "urgency_breakdown": _value_counts_dict(df[urgency_col], dropna=False) if urgency_col else {},
        "monthly_trend": _value_counts_dict(df[date_col].astype(str).str[:7], dropna=False) if date_col else {},
    }


def _experts_from_df(df: pd.DataFrame) -> List[Dict]:
    df = _purchase_level_df(df)
    grouped = (
        df.groupby("کارشناس خرید", dropna=False)
        .agg(
            total=("شماره", "count"),
            in_progress=("وضعیت", lambda s: int((s == "در جریان").sum())),
            closed=("وضعیت", lambda s: int((s == "بسته شده").sum())),
            suspended=("وضعیت", lambda s: int((s == "معلق").sum())),
        )
        .reset_index()
    )
    return _records(grouped)


def _next_inquiry_number() -> int:
    local = local_storage.get_issued_inquiries()
    numbers: List[int] = []
    if not local.empty and "شماره استعلام" in local.columns:
        numbers.extend(pd.to_numeric(local["شماره استعلام"], errors="coerce").dropna().astype(int).tolist())
    return max(numbers, default=9000) + 1


def _today_jalali() -> str:
    try:
        import jdatetime
        return jdatetime.date.today().strftime("%Y/%m/%d")
    except ImportError:
        return datetime.now().strftime("%Y/%m/%d")


def _expert_matches_inquiry(expert: str, inq_row: pd.Series) -> bool:
    if not expert:
        return True
    expert = str(expert).strip()
    for col in ("کارشناس خرید", "صادر کننده سند"):
        if expert in str(inq_row.get(col) or ""):
            return True
    return False


def _orders_for_purchase_row(orders_df: pd.DataFrame, purchase_number: str, title: str = "") -> pd.DataFrame:
    if orders_df.empty or "شماره خرید" not in orders_df.columns:
        return orders_df.iloc[0:0]
    pn = _normalize_id(purchase_number)
    matches = orders_df[orders_df["شماره خرید"].astype(str).map(_normalize_id) == pn]
    if title and not matches.empty and "عنوان کالا" in matches.columns:
        by_title = matches[matches["عنوان کالا"].astype(str).str.strip() == title]
        if not by_title.empty:
            matches = by_title
    return matches


def _inquiries_for_purchase_row(
    issued: pd.DataFrame,
    purchase_number: str,
    expert: Optional[str] = None,
) -> pd.DataFrame:
    if issued.empty or "شماره درخواست خرید" not in issued.columns:
        return issued.iloc[0:0]
    pn = _normalize_id(purchase_number)
    matches = issued[issued["شماره درخواست خرید"].map(_normalize_id) == pn]
    if expert:
        matches = matches[matches.apply(lambda r: _expert_matches_inquiry(expert, r), axis=1)]
    return matches


def purchase_flow_status(
    purchase_number: str,
    title: str = "",
    expert: Optional[str] = None,
) -> str:
    """وضعیت جریان خرید — از نگاشت کش‌شده."""
    snap = _get_workflow_snapshot()
    pn = _normalize_id(purchase_number)
    title = str(title or "").strip()
    flow = snap["flow_by_key"]
    for fk in ((pn, title), (pn, "")):
        if fk in flow:
            return flow[fk]
    if expert:
        expert_pns = _expert_inquiry_purchase_set(expert, snap)
        if pn in expert_pns:
            return "ثبت استعلام"
    elif pn in snap["purchase_inquiries"]:
        return "ثبت استعلام"
    return "در انتظار"


def get_purchase_requests(
    search: str = "",
    filter_type: str = "",
    expert: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    urgency: str = "",
    purchase_type: str = "",
    export_all: bool = False,
) -> Dict:
    df = _canonicalize_columns(_get_merged_purchases())
    df = _filter_expert_purchases(df, expert)
    if urgency and "رمز فوریت" in df.columns:
        df = df[df["رمز فوریت"].astype(str).str.contains(urgency.strip(), na=False)]
    if purchase_type and "نوع خرید" in df.columns:
        df = df[df["نوع خرید"].astype(str) == purchase_type.strip()]
    if filter_type in ("inquiry", "no_inquiry"):
        df = _enrich_purchase_inquiry_flags(df, expert=expert)
    if filter_type:
        df = _filter_purchases(df, filter_type)
    search_cols = [
        "شماره", "شماره مبنا", "عنوان قلم خریدنی", "کد قلم خریدنی",
        "درخواست کننده", "کارشناس خرید", "وضعیت",
    ]
    if search.strip():
        df = _enrich_purchase_current_status(df, expert=expert)
        search_cols.append("وضعیت فعلی خرید")
    df = _search_df(df, search, search_cols)
    eff_page = 1 if export_all else page
    eff_size = 50000 if export_all else page_size
    chunk, total = _paginate(df, eff_page, eff_size, cap=50000 if export_all else 200)
    if not chunk.empty:
        chunk = _enrich_purchase_page(chunk, expert=expert)
    out_cols = [
        *PURCHASE_LIST_COLS,
        "has_local_inquiry", "local_inquiry_number", "inquiry_approved", "وضعیت فعلی خرید",
    ]
    out_cols = [c for c in out_cols if c in chunk.columns]
    pages = math.ceil(total / page_size) if total and not export_all else (1 if total else 0)
    return {
        "items": _records(chunk[out_cols] if out_cols else chunk),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": pages,
    }


def get_purchase_request_detail(request_number: str) -> Optional[Dict]:
    rows = get_purchase_sibling_lines(request_number)
    if not rows:
        return None
    row = rows[0]
    result = {
        k: v for k, v in row.items()
        if not str(k).startswith("_")
    }
    result["شماره خرید"] = result.get("شماره")
    if not result.get("عنوان کالا"):
        result["عنوان کالا"] = result.get("عنوان قلم خریدنی")
    if not result.get("واحد"):
        result["واحد"] = result.get("واحد سنجش قلم خریدنی")
    result["line_count"] = len(rows)
    result["purchase_lines"] = rows
    return result


def get_purchase_sibling_lines(request_number: str) -> List[Dict]:
    df = _get_merged_purchases()
    if "شماره" not in df.columns:
        return []
    match = df[df["شماره"].astype(str) == str(request_number)]
    if match.empty:
        return []
    return _records(match)


def get_purchase_stats(expert: Optional[str] = None) -> dict:
    cache_key = (_workflow_cache_key(), expert or "")
    cached = _cache.get(f"stats_{expert or ''}")
    if cached and cached[0] == cache_key:
        return cached[1]

    df = _canonicalize_columns(_filter_expert_purchases(_get_merged_purchases(), expert))
    df = _enrich_purchase_inquiry_flags(df, expert=expert)
    stats = _stats_from_df(df)
    df = _enrich_purchase_current_status(df, expert=expert)
    stats["by_flow_status"] = _value_counts_dict(df["وضعیت فعلی خرید"])
    result = _json_safe(stats)
    _cache[f"stats_{expert or ''}"] = (cache_key, result)
    return result


def get_inquiries(
    search: str = "",
    expert: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict:
    df = _get_merged_inquiries()
    df = _search_df(df, search, INQUIRY_SEARCH_COLS)
    if expert and "صادر کننده سند" in df.columns:
        df = df[df["صادر کننده سند"].astype(str).str.contains(expert, na=False)]
    display_cols = [c for c in df.columns if not str(c).startswith("_")]
    return _paginated(df[display_cols], page, page_size)


def _safe_float(val: Any) -> float:
    try:
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0.0
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _round_amount(val: float) -> float:
    return round(float(val or 0), 0)


def _is_selected_line_flag(val: Any) -> bool:
    text = str(val or "").strip().lower()
    return text in ("true", "1", "yes", "بله", "منتخب")


def _unit_price_from_inquiry(purchase_number: str, title: str = "") -> float:
    """فی واحد از ردیف منتخب استعلام."""
    issued = local_storage.get_issued_inquiries()
    pn = _normalize_id(purchase_number)
    if issued.empty or "شماره درخواست خرید" not in issued.columns:
        return 0.0
    inq_match = issued[issued["شماره درخواست خرید"].map(_normalize_id) == pn]
    if inq_match.empty:
        return 0.0

    lines_df = local_storage.get_pre_invoice_lines()
    pres_df = local_storage.get_pre_invoices()
    if lines_df.empty or pres_df.empty:
        return 0.0

    title_key = str(title or "").strip()
    for _, inq_row in inq_match.iterrows():
        inq_num = str(inq_row.get("شماره استعلام") or "")
        if not inq_num or "شماره استعلام" not in pres_df.columns:
            continue
        pi_match = pres_df[pres_df["شماره استعلام"].astype(str) == inq_num]
        if pi_match.empty:
            continue
        pi_ids = set(pi_match["id"].astype(str).tolist())
        line_rows = lines_df[lines_df["preinvoice_id"].astype(str).isin(pi_ids)]
        if title_key and "عنوان کالا" in line_rows.columns:
            by_title = line_rows[line_rows["عنوان کالا"].astype(str).str.strip() == title_key]
            if not by_title.empty:
                line_rows = by_title
        for _, line in line_rows.iterrows():
            if not _is_selected_line_flag(line.get("منتخب مدیر")):
                continue
            price = _safe_float(line.get("فی"))
            if price > 0:
                return price
        for _, line in line_rows.iterrows():
            price = _safe_float(line.get("فی"))
            if price > 0:
                return price
    return 0.0


def _purchase_financial_metrics(
    purchase_number: str,
    title: str,
    row: Dict,
    orders_df: pd.DataFrame,
    deliveries_df: pd.DataFrame,
    workflow_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    metrics = workflow_metrics or _purchase_workflow_metrics(
        purchase_number, title, orders_df, deliveries_df
    )
    ord_match = _orders_for_purchase_row(orders_df, purchase_number, title)

    ordered_amount = 0.0
    unit_price = 0.0
    if not ord_match.empty:
        for _, order in ord_match.iterrows():
            price = _safe_float(order.get("فی"))
            qty = _safe_float(order.get("تعداد"))
            line_total = price * qty
            ordered_amount += line_total
            if price > 0 and unit_price <= 0:
                unit_price = price

    requested_qty = _safe_float(row.get("مقدار") or row.get("تعداد"))
    invoice_amount = _safe_float(row.get("مبلغ فاکتور"))
    if unit_price <= 0:
        unit_price = _unit_price_from_inquiry(purchase_number, title)
    if unit_price <= 0 and requested_qty > 0 and invoice_amount > 0:
        unit_price = invoice_amount / requested_qty

    requested_amount = invoice_amount if invoice_amount > 0 else unit_price * requested_qty
    if requested_amount <= 0 and ordered_amount > 0:
        requested_amount = ordered_amount

    del_match = deliveries_df.iloc[0:0]
    pn = _normalize_id(purchase_number)
    if not deliveries_df.empty and "شماره خرید" in deliveries_df.columns:
        del_match = deliveries_df[deliveries_df["شماره خرید"].astype(str).map(_normalize_id) == pn]
        if title and not del_match.empty and "عنوان کالا" in del_match.columns:
            by_title = del_match[del_match["عنوان کالا"].astype(str).str.strip() == title]
            if not by_title.empty:
                del_match = by_title

    delivered_amount = 0.0
    if not del_match.empty:
        for _, delivery in del_match.iterrows():
            dq = _safe_float(delivery.get("مقدار"))
            price = unit_price
            order_num = str(delivery.get("شماره دستور") or "").strip()
            if order_num and not ord_match.empty and "شماره دستور" in ord_match.columns:
                om = ord_match[ord_match["شماره دستور"].astype(str) == order_num]
                if not om.empty:
                    op = _safe_float(om.iloc[0].get("فی"))
                    if op > 0:
                        price = op
            delivered_amount += price * dq
    elif unit_price > 0 and metrics.get("delivered_qty", 0) > 0:
        delivered_amount = unit_price * _safe_float(metrics.get("delivered_qty"))

    pending_amount = max(requested_amount - delivered_amount, 0.0)

    return {
        "unit_price": _round_amount(unit_price),
        "requested_amount": _round_amount(requested_amount),
        "ordered_amount": _round_amount(ordered_amount),
        "delivered_amount": _round_amount(delivered_amount),
        "pending_amount": _round_amount(pending_amount),
    }


def _purchase_workflow_metrics(
    purchase_number: str,
    title: str = "",
    orders_df: Optional[pd.DataFrame] = None,
    deliveries_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    pn = _normalize_id(purchase_number)
    orders_df = orders_df if orders_df is not None else _get_workflow_snapshot()["orders"]
    deliveries_df = deliveries_df if deliveries_df is not None else local_storage.get_deliveries()

    ord_match = _orders_for_purchase_row(orders_df, pn, title)
    order_count = int(len(ord_match))
    order_qty = sum(_safe_float(r.get("تعداد")) for _, r in ord_match.iterrows()) if not ord_match.empty else 0.0

    del_match = deliveries_df.iloc[0:0]
    if not deliveries_df.empty and "شماره خرید" in deliveries_df.columns:
        del_match = deliveries_df[deliveries_df["شماره خرید"].astype(str).map(_normalize_id) == pn]
        if title and not del_match.empty and "عنوان کالا" in del_match.columns:
            by_title = del_match[del_match["عنوان کالا"].astype(str).str.strip() == title]
            if not by_title.empty:
                del_match = by_title

    delivery_count = int(len(del_match))
    delivered_qty = sum(_safe_float(r.get("مقدار")) for _, r in del_match.iterrows()) if not del_match.empty else 0.0

    return {
        "order_count": order_count,
        "order_qty": order_qty,
        "delivery_count": delivery_count,
        "delivered_qty": delivered_qty,
    }


def get_expert_report(expert: Optional[str] = None, *, include_items: bool = True) -> Dict[str, Any]:
    """گزارش کارشناس بر اساس داده پنل + ویرایش‌های محلی (نه فقط اکسل خام)."""
    df = _get_merged_purchases()
    df = _filter_expert_purchases(df, expert)
    df = _enrich_purchase_inquiry_flags(df)
    df = _enrich_purchase_current_status(df)
    pdf = _purchase_level_df(df)

    snap = _get_workflow_snapshot()
    orders_df = snap["orders"]
    deliveries_df = local_storage.get_deliveries()

    from collections import defaultdict

    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "کارشناس خرید": "",
        "total": 0,
        "in_progress": 0,
        "closed": 0,
        "suspended": 0,
        "inquiry_issued": 0,
        "orders": 0,
        "deliveries": 0,
        "delivered_qty": 0.0,
        "flow_inquiry": 0,
        "flow_ordered": 0,
        "flow_delivered": 0,
        "requested_amount": 0.0,
        "ordered_amount": 0.0,
        "delivered_amount": 0.0,
        "pending_amount": 0.0,
    })
    items: List[Dict] = []
    financial_totals = {
        "requested_amount": 0.0,
        "ordered_amount": 0.0,
        "delivered_amount": 0.0,
        "pending_amount": 0.0,
    }

    for _, row in pdf.iterrows():
        row_dict = row.to_dict()
        pn = _normalize_id(row.get("شماره"))
        title = str(row.get("عنوان قلم خریدنی") or row.get("عنوان کالا") or "").strip()
        exp = str(row.get("کارشناس خرید") or "").strip() or "—"
        flow = str(row.get("وضعیت فعلی خرید") or "در انتظار")
        excel_st = str(row.get("وضعیت") or "—")
        metrics = _purchase_workflow_metrics(pn, title, orders_df, deliveries_df)
        fin = _purchase_financial_metrics(pn, title, row_dict, orders_df, deliveries_df, metrics)

        requested_qty = _safe_float(row.get("مقدار") or row.get("تعداد"))
        delivered_qty = metrics["delivered_qty"]
        delivery_pct = round((delivered_qty / requested_qty) * 100, 1) if requested_qty > 0 else None
        amount_pct = (
            round((fin["delivered_amount"] / fin["requested_amount"]) * 100, 1)
            if fin["requested_amount"] > 0
            else None
        )

        has_inq = bool(row.get("has_local_inquiry"))
        if include_items:
            items.append({
                "کارشناس خرید": exp,
                "شماره خرید": pn,
                "عنوان کالا": title or "—",
                "وضعیت اکسل": excel_st,
                "وضعیت جریان": flow,
                "نوع خرید": row.get("نوع خرید") or "—",
                "اولویت": row.get("رمز فوریت") or "—",
                "شماره استعلام": row.get("local_inquiry_number") or "—",
                "استعلام صادر": "بله" if has_inq else "خیر",
                "تعداد دستور": metrics["order_count"],
                "تعداد تحویل": metrics["delivery_count"],
                "مقدار درخواست": requested_qty or None,
                "مقدار تحویل شده": delivered_qty or None,
                "درصد تحویل": delivery_pct,
                "فی واحد": fin["unit_price"] or None,
                "مبلغ درخواست": fin["requested_amount"] or None,
                "مبلغ دستور": fin["ordered_amount"] or None,
                "مبلغ تحویل‌شده": fin["delivered_amount"] or None,
                "مبلغ باقیمانده": fin["pending_amount"] or None,
                "درصد مبلغ تحویل": amount_pct,
                "تاریخ نیاز": row.get("تاریخ نیاز") or "—",
                "انبار": row.get("انبار") or "—",
            })

        bucket = agg[exp]
        bucket["کارشناس خرید"] = exp
        bucket["total"] += 1
        if excel_st == "در جریان":
            bucket["in_progress"] += 1
        elif excel_st == "بسته شده":
            bucket["closed"] += 1
        elif excel_st == "معلق":
            bucket["suspended"] += 1
        if has_inq:
            bucket["inquiry_issued"] += 1
        bucket["orders"] += metrics["order_count"]
        bucket["deliveries"] += metrics["delivery_count"]
        bucket["delivered_qty"] += delivered_qty
        bucket["requested_amount"] += fin["requested_amount"]
        bucket["ordered_amount"] += fin["ordered_amount"]
        bucket["delivered_amount"] += fin["delivered_amount"]
        bucket["pending_amount"] += fin["pending_amount"]
        if flow == "ثبت استعلام":
            bucket["flow_inquiry"] += 1
        elif flow == "دستور شده":
            bucket["flow_ordered"] += 1
        elif flow == "تحویل شده":
            bucket["flow_delivered"] += 1

        for key in financial_totals:
            financial_totals[key] += fin[key]

    for key in list(financial_totals.keys()):
        financial_totals[key] = _round_amount(financial_totals[key])
    for bucket in agg.values():
        for key in ("requested_amount", "ordered_amount", "delivered_amount", "pending_amount"):
            bucket[key] = _round_amount(bucket[key])

    summary = sorted(agg.values(), key=lambda x: (-x["total"], x["کارشناس خرید"]))
    result: Dict[str, Any] = {
        "summary": summary,
        "item_count": len(pdf),
        "financial_totals": financial_totals,
        "data_source_note": "بر اساس داده پنل، استعلام‌ها، دستورات و تحویل‌های ثبت‌شده — مبالغ از فاکتور/دستور/استعلام",
    }
    if include_items:
        result["items"] = items
    return result


def get_reorder_report(page: int = 1, page_size: int = 50, expert: Optional[str] = None) -> Dict:
    df = _canonicalize_columns(_get_merged_purchases())
    df = _filter_expert_purchases(df, expert)
    status = df.get("وضعیت")
    active = df[status.isin(["در جریان", "تایید شده", "معلق"])] if status is not None else df.iloc[0:0]
    active = active.sort_values(by="تاریخ نیاز", ascending=True, na_position="last")
    cols = [
        "شماره", "عنوان قلم خریدنی", "کد قلم خریدنی", "مقدار",
        "واحد سنجش قلم خریدنی", "تاریخ نیاز", "کارشناس خرید", "وضعیت", "رمز فوریت",
    ]
    return _paginated(active, page, page_size, cols)


def get_qty_vs_delivered_report(date_from: str = "", date_to: str = "", expert: Optional[str] = None) -> Dict:
    """Report for manager/super: requested vs delivered qty by item code (کد قلم), expert, date range (Jalali strings).
    Includes monthly breakdown if dates span months.
    """
    df = _canonicalize_columns(_get_merged_purchases())
    df = _filter_expert_purchases(df, expert)
    date_col = None
    for c in ["تاریخ", "تاریخ درخواست", "تاریخ درخواست کالا", "تاریخ تحویل"]:
        if c in df.columns:
            date_col = c
            break
    if date_from and date_col:
        df = df[df[date_col].astype(str) >= date_from]
    if date_to and date_col:
        df = df[df[date_col].astype(str) <= date_to]
    if df.empty:
        return {"items": [], "total": 0, "monthly": []}
    group_cols = ["کد قلم خریدنی", "کارشناس خرید"]
    group_cols = [c for c in group_cols if c in df.columns]
    if not group_cols:
        group_cols = ["کارشناس خرید"] if "کارشناس خرید" in df.columns else []
    if not group_cols:
        return {"items": [], "total": 0, "monthly": []}
    req_col = "مقدار درخواست" if "مقدار درخواست" in df.columns else None
    del_col = "مقدار تحویل" if "مقدار تحویل" in df.columns else None
    if not req_col:
        return {"items": [], "total": 0, "monthly": []}
    grouped = df.groupby(group_cols, dropna=False).agg(
        requested_qty=(req_col, "sum"),
        delivered_qty=(del_col, "sum") if del_col else (req_col, "size"),
        count=("شماره", "count") if "شماره" in df.columns else (req_col, "count"),
    ).reset_index()
    items = _records(grouped)
    # Monthly breakdown
    monthly = []
    if date_col:
        df = df.copy()
        df["_month"] = df[date_col].astype(str).str[:7]  # 1405/01
        mon_group = df.groupby(["_month"] + group_cols, dropna=False).agg(
            requested_qty=(req_col, "sum"),
            delivered_qty=(del_col, "sum") if del_col else (req_col, "size"),
        ).reset_index()
        monthly = _records(mon_group)
    return {"items": items, "total": len(items), "monthly": monthly}


def get_purchase_summary(
    expert: Optional[str] = None,
    urgency: str = "",
    purchase_type: str = "",
) -> dict:
    df = _get_merged_purchases()
    df = _filter_expert_purchases(df, expert)
    if urgency and "رمز فوریت" in df.columns:
        df = df[df["رمز فوریت"].astype(str).str.contains(urgency.strip(), na=False)]
    if purchase_type and "نوع خرید" in df.columns:
        df = df[df["نوع خرید"].astype(str) == purchase_type.strip()]
    result = _summary_from_df(df)

    snap = _get_workflow_snapshot()
    orders_df = snap["orders"]
    deliveries_df = local_storage.get_deliveries()
    pdf = _purchase_level_df(df)
    financial_totals = {
        "requested_amount": 0.0,
        "ordered_amount": 0.0,
        "delivered_amount": 0.0,
        "pending_amount": 0.0,
    }
    for _, row in pdf.iterrows():
        row_dict = row.to_dict()
        pn = _normalize_id(row.get("شماره"))
        title = str(row.get("عنوان قلم خریدنی") or row.get("عنوان کالا") or "").strip()
        fin = _purchase_financial_metrics(pn, title, row_dict, orders_df, deliveries_df)
        for key in financial_totals:
            financial_totals[key] += fin[key]
    result["financial_totals"] = {k: _round_amount(v) for k, v in financial_totals.items()}
    result["data_source_note"] = "اولویت و نوع خرید از تغییرات پنل — مبالغ از فاکتور/دستور/استعلام"
    return result


def _history_item_from_row(row: Dict) -> Dict:
    return {
        "عنوان کالا": _clean(row.get("عنوان کالا")),
        "کد قلم خریدنی": _clean(row.get("کد قلم خریدنی")),
        "فی": _clean(row.get("فی")),
        "تعداد": _clean(row.get("تعداد")),
        "واحد": _clean(row.get("واحد")),
        "تاریخ خرید": _clean(row.get("تاریخ خرید")) or (_clean(str(row.get("created_at", ""))[:10]) if row.get("created_at") else None),
        "تامین کننده": _clean(row.get("نام پیمانکار")),
        "شهر پیمانکار": _clean(row.get("شهر پیمانکار")),
        "شماره خرید": _clean(row.get("شماره خرید")),
        "شماره استعلام": _clean(row.get("شماره استعلام")),
    }


def get_last_purchase_for_product(
    product_code: str = "",
    product_title: str = "",
    exclude_purchase: str = "",
) -> Dict:
    result: Dict[str, Any] = {"found": False, "source": None, "item": None}
    code = str(product_code or "").strip()
    title = str(product_title or "").strip()
    if not code and not title:
        return result

    try:
        hist_df = local_storage.get_product_history()
        if not hist_df.empty:
            mask = pd.Series(False, index=hist_df.index)
            if code and "کد قلم خریدنی" in hist_df.columns:
                mask |= hist_df["کد قلم خریدنی"].astype(str).str.strip() == code
            if title and "عنوان کالا" in hist_df.columns:
                mask |= hist_df["عنوان کالا"].astype(str).str.strip() == title
            matched = hist_df[mask].copy()
            if exclude_purchase and "شماره خرید" in matched.columns:
                matched = matched[matched["شماره خرید"].astype(str) != str(exclude_purchase)]
            if "فی" in matched.columns:
                matched = matched[pd.to_numeric(matched["فی"], errors="coerce").fillna(0) > 0]
            if not matched.empty and "created_at" in matched.columns:
                matched = matched.sort_values("created_at", ascending=False, na_position="last")
                row = matched.iloc[0].to_dict()
                return {"found": True, "source": "history", "item": _history_item_from_row(row)}
    except Exception:
        pass

    try:
        lines_df = local_storage.get_pre_invoice_lines()
        pres_df = local_storage.get_pre_invoices()
        if not lines_df.empty and not pres_df.empty:
            mask = pd.Series(False, index=lines_df.index)
            if code and "کد قلم خریدنی" in lines_df.columns:
                mask |= lines_df["کد قلم خریدنی"].astype(str).str.strip() == code
            if title and "عنوان کالا" in lines_df.columns:
                mask |= lines_df["عنوان کالا"].astype(str).str.strip() == title
            hist = lines_df[mask].copy()
            if not hist.empty and "فی" in hist.columns:
                hist = hist[pd.to_numeric(hist["فی"], errors="coerce").fillna(0) > 0]
                if not hist.empty:
                    pi_cols = [c for c in ["id", "نام پیمانکار", "شهر پیمانکار", "شماره استعلام", "created_at"] if c in pres_df.columns]
                    if pi_cols:
                        hist = hist.merge(
                            pres_df[pi_cols],
                            left_on="preinvoice_id",
                            right_on="id",
                            how="left",
                        )
                    if "created_at" in hist.columns:
                        hist = hist.sort_values("created_at", ascending=False, na_position="last")
                    row = hist.iloc[0].to_dict()
                    return {
                        "found": True,
                        "source": "local",
                        "item": {
                            "عنوان کالا": _clean(row.get("عنوان کالا")),
                            "فی": _clean(row.get("فی")),
                            "تعداد": _clean(row.get("تعداد")),
                            "واحد": _clean(row.get("واحد")),
                            "تاریخ خرید": _clean(str(row.get("created_at", ""))[:10]) if row.get("created_at") else None,
                            "تامین کننده": _clean(row.get("نام پیمانکار")),
                            "شهر پیمانکار": _clean(row.get("شهر پیمانکار")),
                            "شماره استعلام": _clean(row.get("شماره استعلام")),
                        },
                    }
    except Exception:
        pass
    return result


def get_dashboard(
    expert: Optional[str] = None,
    include_experts: bool = True,
    expert_portal: bool = False,
) -> dict:
    from services import analytics_service, kpi_service

    if expert_portal and expert:
        return _json_safe(analytics_service.get_expert_dashboard(expert))

    stats = get_purchase_stats(expert=expert)
    df = _filter_expert_purchases(_get_merged_purchases(), expert)
    result = {
        "stats": stats,
        "summary": _summary_from_df(df),
        "kpis": kpi_service.get_kpis(expert=expert, include_experts=include_experts and not expert),
        "filtered_expert": expert or "",
        "duration_unit": analytics_service.DURATION_UNIT,
        "duration_unit_note": analytics_service.DURATION_UNIT_NOTE,
    }
    if include_experts and not expert:
        result["experts"] = _experts_from_df(_get_merged_purchases())
        result["experts_duration"] = analytics_service.get_all_experts_stage_summary()
    if expert:
        result["expert_timeline"] = analytics_service.get_expert_stage_timeline(expert)
    return _json_safe(result)


def update_purchase_request(
    request_number: Any,
    updates: dict,
    username: str,
    admin: bool = False,
) -> dict:
    from config import PURCHASE_EDIT_BLOCKED
    from services import history_service

    req_id = _normalize_id(request_number)
    detail = get_purchase_request_detail(req_id)
    if not detail:
        raise ValueError("درخواست یافت نشد")
    if admin:
        allowed = {k: v for k, v in updates.items() if k not in PURCHASE_EDIT_BLOCKED}
    else:
        allowed = {k: v for k, v in updates.items() if k in PURCHASE_EDITABLE}
    if not allowed:
        raise ValueError("فیلد مجاز برای ویرایش یافت نشد")
    history_service.log_field_changes("درخواست خرید", req_id, username, allowed, detail)
    result = local_storage.save_purchase_edit(req_id, allowed, username, admin=admin)
    invalidate_cache()
    return result


def preview_next_inquiry_number() -> dict:
    from services.inquiry_service import generate_inquiry_number
    return {"next_number": generate_inquiry_number()}


def excel_info() -> dict:
    from config import DB_CURRENT_PATH, INPUT_EXCEL_PATH, LOCK_FLAG_PATH, STORAGE_BACKEND
    from db.connection import get_db_manager, is_system_locked

    input_path = INPUT_EXCEL_PATH if INPUT_EXCEL_PATH.exists() else Path(EXCEL_PATH)
    info = {
        "storage_backend": STORAGE_BACKEND,
        "source_excel": {
            "path": str(input_path),
            "exists": input_path.exists(),
            "size_mb": round(input_path.stat().st_size / (1024 * 1024), 2) if input_path.exists() else 0,
            "last_modified": datetime.fromtimestamp(input_path.stat().st_mtime).isoformat() if input_path.exists() else None,
            "note": "فایل روزانه — فقط Import Service می‌خواند",
        },
        "database": get_db_manager().db_info() if STORAGE_BACKEND == "sqlite" else None,
        "locked": is_system_locked(),
        "lock_flag": str(LOCK_FLAG_PATH),
        "db_current": str(DB_CURRENT_PATH),
        "local_storage": local_storage.local_info(),
        "local_note": "گردش کار در SQLite مشترک — اکسل فقط برای import/export",
    }
    return info