"""ابزارهای امن خواندن/نوشتن اکسل در ویندوز — جلوگیری از WinError 32."""

from __future__ import annotations

import gc
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Union

FileLike = Union[str, Path]


def read_file_bytes(path: FileLike) -> bytes:
    return Path(path).read_bytes()


def load_workbook_from_bytes(file_bytes: bytes):
    import openpyxl
    return openpyxl.load_workbook(
        io.BytesIO(file_bytes),
        read_only=False,
        data_only=False,
    )


def workbook_to_bytes(wb) -> bytes:
    """ذخیره workbook فقط در حافظه — بدون دسترسی به دیسک."""
    buffer = io.BytesIO()
    try:
        wb.save(buffer)
    finally:
        try:
            wb.close()
        except Exception:
            pass
    return buffer.getvalue()


def is_file_lock_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError):
        return True
    if isinstance(exc, OSError) and getattr(exc, 'winerror', None) == 32:
        return True
    return False


def _write_temp_bytes(data: bytes) -> Path:
    """نوشتن بایت‌ها در پوشه موقت سیستم (نه media — کمتر درگیر آنتی‌ویروس)."""
    tmp_fd, tmp_name = tempfile.mkstemp(suffix='.xlsx', prefix='tadarokat_xl_')
    tmp_path = Path(tmp_name)
    try:
        os.write(tmp_fd, data)
    finally:
        os.close(tmp_fd)
    return tmp_path


def get_input_excel_path() -> Path:
    from django.conf import settings
    return Path(settings.BASE_DIR) / 'input.xlsx'


def get_panel_excel_path() -> Path:
    from django.conf import settings
    return Path(settings.BASE_DIR) / 'panel.xlsx'


def safe_write_bytes(data: bytes, target: FileLike, *, max_retries: int = 12) -> Path:
    """
    نوشتن بایت‌ها در مقصد با retry.
    اگر فایل قفل باشد خطا می‌دهد — فایل جایگزین در ریشه پروژه ساخته نمی‌شود.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _write_temp_bytes(data)

    last_error: BaseException | None = None
    try:
        for attempt in range(max_retries):
            try:
                if target.exists():
                    target.unlink()
                os.replace(str(tmp_path), str(target))
                return target
            except (PermissionError, OSError) as exc:
                last_error = exc
                if is_file_lock_error(exc) and attempt < max_retries - 1:
                    gc.collect()
                    time.sleep(0.4 * (attempt + 1))
                    continue
                break
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    if last_error:
        raise last_error
    raise OSError(f'Could not write Excel file: {target}')


def safe_save_workbook(wb, target: FileLike, *, max_retries: int = 12) -> Path:
    """ذخیره workbook: حافظه → فایل موقت سیستم → مقصد با retry."""
    data = workbook_to_bytes(wb)
    return safe_write_bytes(data, target, max_retries=max_retries)


def safe_copy_bytes(data: bytes, target: FileLike, *, max_retries: int = 12) -> Path:
    return safe_write_bytes(data, target, max_retries=max_retries)


def resolve_panel_export_path(token: str) -> Path | None:
    """یافتن فایل خروجی — اول panel.xlsx در ریشه پروژه."""
    panel_root = get_panel_excel_path()
    if panel_root.exists():
        return panel_root

    from django.conf import settings

    upload_dir = Path(settings.MEDIA_ROOT) / 'excel_uploads'
    if not upload_dir.exists():
        return None

    exact = upload_dir / f'panel_{token}.xlsx'
    if exact.exists():
        return exact

    matches = sorted(
        upload_dir.glob(f'panel_{token}_*.xlsx'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None