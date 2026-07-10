"""اجرای پس‌زمینه آپلود اکسل با پیشرفت و rollback اتمیک."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections

from services.excel_import_progress import ExcelImportProgress
from services.excel_importer import ExcelImporter, ExcelImportError

User = get_user_model()

_running_jobs: set[str] = set()
_lock = threading.Lock()


def _serialize_result(stats: dict, token: str, original_name: str) -> dict:
    safe = {
        k: v for k, v in stats.items()
        if isinstance(v, (str, int, float, bool, list, dict, type(None)))
    }
    excel_export = safe.get('excel_export') or {}
    return {
        'token': token,
        'original_name': original_name,
        'stats': safe,
        'excel_export': excel_export,
        'panel_filename': Path(excel_export.get('output_path', '')).name if excel_export.get('output_path') else '',
        'download_url_name': 'purchases:download_uploaded_excel',
    }


def run_excel_upload_job(
    *,
    job_id: str,
    user_id: int,
    incoming_path: Path,
    panel_path: Path,
    token: str,
    original_name: str,
) -> None:
    """اجرای import در نخ جدا — برای نمایش پیشرفت real-time."""
    with _lock:
        if job_id in _running_jobs:
            return
        _running_jobs.add(job_id)

    close_old_connections()
    progress = ExcelImportProgress.load(job_id, user_id)
    if not progress:
        with _lock:
            _running_jobs.discard(job_id)
        return

    user = User.objects.filter(pk=user_id).first()
    progress.set_meta(original_name=original_name, token=token)

    try:
        from services.excel_file_utils import read_file_bytes

        incoming_bytes = read_file_bytes(incoming_path)
        progress.set_phase('reading', 'شروع پردازش فایل...')
        stats = ExcelImporter.import_from_excel(
            str(incoming_path),
            user=user,
            full_sync=False,
            fail_on_errors=True,
            export_path=str(panel_path),
            progress=progress,
        )

        from services.excel_file_utils import (
            get_input_excel_path,
            get_panel_excel_path,
            read_file_bytes,
            safe_copy_bytes,
        )

        input_path = get_input_excel_path()
        panel_root = get_panel_excel_path()

        try:
            safe_copy_bytes(incoming_bytes, input_path)
        except OSError as input_err:
            progress.log(
                'error',
                f'هشدار: فایل input.xlsx به‌روز نشد ({input_err}) — '
                'اگر در Excel باز است ببندید.',
            )

        export_output = (stats.get('excel_export') or {}).get('output_path')
        final_panel_path = Path(export_output) if export_output else panel_path
        if final_panel_path != panel_root and final_panel_path.exists():
            try:
                safe_copy_bytes(read_file_bytes(final_panel_path), panel_root)
            except OSError as panel_err:
                progress.log(
                    'error',
                    f'هشدار: فایل panel.xlsx به‌روز نشد ({panel_err}) — '
                    'اگر در Excel باز است ببندید.',
                )

        from audit.models import AuditLog
        AuditLog.log(
            user=user,
            action='update',
            entity_type='آپلود اکسل',
            entity_id=token,
            entity_repr=original_name,
            description=(
                f'آپلود اکسل: {stats.get("created", 0)} جدید، '
                f'{stats.get("updated", 0)} به‌روزرسانی'
            ),
            request=None,
        )

        progress.complete(_serialize_result(stats, token, original_name))

    except ExcelImportError as e:
        progress.fail(str(e), errors=e.errors)
    except Exception as e:
        err_msg = str(e)
        if 'WinError 32' in err_msg or 'cannot access the file' in err_msg.lower():
            err_msg += (
                ' — اگر input.xlsx یا فایل خروجی در Excel باز است ببندید، '
                'چند ثانیه صبر کنید و دوباره آپلود کنید.'
            )
        progress.fail(f'خطا در پردازش اکسل: {err_msg}')
    finally:
        if incoming_path.exists():
            incoming_path.unlink(missing_ok=True)
        if progress.to_dict().get('status') == 'error':
            from services.excel_file_utils import get_panel_excel_path

            canonical_panel = get_panel_excel_path()
            if panel_path != canonical_panel and panel_path.exists():
                panel_path.unlink(missing_ok=True)
            result = (progress.to_dict().get('result') or {})
            output_path = (result.get('excel_export') or {}).get('output_path')
            if output_path:
                out = Path(output_path)
                if out != canonical_panel and out.exists():
                    out.unlink(missing_ok=True)
        close_old_connections()
        with _lock:
            _running_jobs.discard(job_id)


def start_excel_upload_job(
    *,
    user_id: int,
    incoming_path: Path,
    panel_path: Path,
    token: str,
    original_name: str,
) -> ExcelImportProgress:
    job_id = f'{token}_{user_id}'
    progress = ExcelImportProgress.create(user_id=user_id, job_id=job_id, token=token)
    progress.set_meta(original_name=original_name, token=token)

    thread = threading.Thread(
        target=run_excel_upload_job,
        kwargs={
            'job_id': job_id,
            'user_id': user_id,
            'incoming_path': incoming_path,
            'panel_path': panel_path,
            'token': token,
            'original_name': original_name,
        },
        daemon=True,
    )
    thread.start()
    return progress