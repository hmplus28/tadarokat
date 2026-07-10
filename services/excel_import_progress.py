"""ردیابی پیشرفت و لاگ آپلود اکسل — ذخیره در Django cache."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from django.core.cache import cache

CACHE_PREFIX = 'excel_import_job'
CACHE_TTL = 3600


class ExcelImportProgress:
    PHASES = (
        ('queued', 'در صف پردازش', 0),
        ('reading', 'خواندن فایل اکسل', 5),
        ('categories', 'ثبت گروه‌های کالایی', 8),
        ('importing', 'واردسازی ردیف‌ها', 10),
        ('syncing_inquiries', 'همگام‌سازی استعلام‌ها', 58),
        ('syncing_orders', 'همگام‌سازی دستورات', 65),
        ('syncing_deliveries', 'همگام‌سازی تحویل‌ها', 72),
        ('recalculating_status', 'محاسبه وضعیت‌ها', 80),
        ('refreshing_deadlines', 'به‌روزرسانی انحراف مهلت', 88),
        ('exporting', 'تولید اکسل خروجی', 94),
        ('done', 'پایان', 100),
        ('error', 'خطا', 0),
    )

    def __init__(self, job_id: str, user_id: int):
        self.job_id = job_id
        self.user_id = user_id
        self._cache_key = f'{CACHE_PREFIX}:{user_id}:{job_id}'

    @classmethod
    def create(cls, user_id: int, job_id: Optional[str] = None, token: str = '') -> ExcelImportProgress:
        job_id = job_id or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        progress = cls(job_id, user_id)
        progress._save({
            'job_id': job_id,
            'user_id': user_id,
            'status': 'queued',
            'phase': 'queued',
            'phase_label': 'در صف پردازش',
            'percent': 0,
            'message': '',
            'logs': [],
            'result': None,
            'error': None,
            'original_name': '',
            'token': token or job_id,
        })
        return progress

    @classmethod
    def load(cls, job_id: str, user_id: int) -> Optional[ExcelImportProgress]:
        key = f'{CACHE_PREFIX}:{user_id}:{job_id}'
        if not cache.get(key):
            return None
        return cls(job_id, user_id)

    def _load(self) -> dict:
        return cache.get(self._cache_key) or {}

    def _save(self, data: dict) -> None:
        cache.set(self._cache_key, data, CACHE_TTL)

    def _phase_bounds(self, phase: str) -> tuple[int, int, str]:
        ordered = [p[0] for p in self.PHASES]
        labels = {p[0]: p[1] for p in self.PHASES}
        percents = {p[0]: p[2] for p in self.PHASES}
        try:
            idx = ordered.index(phase)
        except ValueError:
            return 0, 100
        start = percents[phase]
        if idx + 1 < len(ordered):
            end = percents[ordered[idx + 1]]
        else:
            end = 100
        return start, end, labels.get(phase, phase)

    def set_meta(self, **kwargs: Any) -> None:
        data = self._load()
        data.update(kwargs)
        self._save(data)

    def set_phase(self, phase: str, message: str = '', sub_percent: float = 0.0) -> None:
        start, end, label = self._phase_bounds(phase)
        sub_percent = max(0.0, min(1.0, sub_percent))
        percent = int(start + (end - start) * sub_percent)
        data = self._load()
        data.update({
            'status': 'running' if phase not in ('done', 'error') else phase,
            'phase': phase,
            'phase_label': label,
            'percent': percent,
            'message': message,
        })
        self._save(data)
        if message:
            self.log('info', message)

    def log(self, level: str, message: str) -> None:
        data = self._load()
        logs = data.get('logs') or []
        logs.append({
            'level': level,
            'message': message,
            'time': datetime.now().strftime('%H:%M:%S'),
        })
        if len(logs) > 200:
            logs = logs[-200:]
        data['logs'] = logs
        self._save(data)

    def complete(self, result: dict) -> None:
        data = self._load()
        data.update({
            'status': 'done',
            'phase': 'done',
            'phase_label': 'پایان',
            'percent': 100,
            'message': 'پردازش با موفقیت انجام شد',
            'result': result,
            'error': None,
        })
        self._save(data)
        self.log('success', 'پردازش با موفقیت انجام شد')

    def fail(self, error: str, errors: Optional[list] = None) -> None:
        data = self._load()
        data.update({
            'status': 'error',
            'phase': 'error',
            'phase_label': 'خطا',
            'percent': data.get('percent', 0),
            'message': error,
            'error': error,
            'result': None,
        })
        if errors:
            data['import_errors'] = errors[:50]
        self._save(data)
        self.log('error', error)
        if errors:
            for err in errors[:20]:
                self.log('error', str(err))

    def to_dict(self) -> dict:
        return self._load()