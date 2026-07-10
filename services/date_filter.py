"""فیلتر تاریخ شمسی پرونده‌ها بر اساس purchase_date (ستون D)"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.stage_analytics import parse_jalali_date

SEASONS = (
    (1, 'بهار', (1, 2, 3)),
    (2, 'تابستان', (4, 5, 6)),
    (3, 'پاییز', (7, 8, 9)),
    (4, 'زمستان', (10, 11, 12)),
)


def get_season_name(season: int) -> str:
    for code, name, _ in SEASONS:
        if code == season:
            return name
    return '—'


def get_season_months(season: int) -> Tuple[int, ...]:
    for code, _name, months in SEASONS:
        if code == season:
            return months
    return tuple()


def parse_filter_params(request) -> Dict[str, Any]:
    """خواندن پارامترهای فیلتر از درخواست"""
    period = (request.GET.get('period') or 'all').strip()
    year = request.GET.get('year', '').strip()
    month = request.GET.get('month', '').strip()
    season = request.GET.get('season', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()
    search = (request.GET.get('q') or '').strip()

    try:
        year_int = int(year) if year else None
    except ValueError:
        year_int = None
    try:
        month_int = int(month) if month else None
    except ValueError:
        month_int = None
    try:
        season_int = int(season) if season else None
    except ValueError:
        season_int = None

    if period not in ('all', 'month', 'season', 'range'):
        period = 'all'

    return {
        'period': period,
        'year': year_int,
        'month': month_int,
        'season': season_int,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
    }


def _in_range(parsed, date_from: Optional[str], date_to: Optional[str]) -> bool:
    start = parse_jalali_date(date_from) if date_from else None
    end = parse_jalali_date(date_to) if date_to else None
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


def purchase_matches_filter(purchase_date: str, params: Dict[str, Any]) -> bool:
    if params.get('period') == 'all':
        return True

    parsed = parse_jalali_date(purchase_date)
    if not parsed:
        return False

    period = params['period']
    if period == 'month':
        if not params.get('year') or not params.get('month'):
            return True
        return parsed.year == params['year'] and parsed.month == params['month']

    if period == 'season':
        if not params.get('year') or not params.get('season'):
            return True
        months = get_season_months(params['season'])
        return parsed.year == params['year'] and parsed.month in months

    if period == 'range':
        date_from = params.get('date_from') or ''
        date_to = params.get('date_to') or ''
        if not date_from and not date_to:
            return True
        return _in_range(parsed, date_from, date_to)

    return True


def is_range_filter_ready(params: Dict[str, Any]) -> bool:
    if params.get('period') != 'range':
        return True
    return bool(params.get('date_from') or params.get('date_to'))


def get_filter_warning(params: Dict[str, Any]) -> str:
    if params.get('period') == 'range' and not is_range_filter_ready(params):
        return 'بازه دلخواه: حداقل یک تاریخ «از» یا «تا» را وارد کنید و اعمال فیلتر را بزنید.'
    if params.get('period') == 'range':
        date_from = params.get('date_from') or ''
        date_to = params.get('date_to') or ''
        if date_from and not parse_jalali_date(date_from):
            return f'تاریخ «از» نامعتبر است: {date_from}'
        if date_to and not parse_jalali_date(date_to):
            return f'تاریخ «تا» نامعتبر است: {date_to}'
    return ''


def filter_queryset_by_purchase_date(queryset, params: Dict[str, Any]):
    """فیلتر queryset بر اساس تاریخ درخواست (ستون D)"""
    if params.get('period') == 'all':
        return queryset

    if params.get('period') == 'range' and not is_range_filter_ready(params):
        return queryset

    matched_ids = []
    for purchase in queryset.only('pk', 'purchase_date').iterator(chunk_size=500):
        if purchase_matches_filter(purchase.purchase_date, params):
            matched_ids.append(purchase.pk)

    if not matched_ids:
        return queryset.none()
    return queryset.filter(pk__in=matched_ids)


def filter_queryset_by_search(queryset, params: Dict[str, Any]):
    """جستجو در شماره خرید، شماره سفارش، کارشناس، گروه کالایی، کد و عنوان"""
    from services.search_service import SearchService
    return SearchService.filter_purchases(queryset, params.get('search'))


def apply_report_filters(queryset, params: Dict[str, Any]):
    queryset = filter_queryset_by_purchase_date(queryset, params)
    return filter_queryset_by_search(queryset, params)


def describe_active_filter(params: Dict[str, Any]) -> str:
    if params.get('period') == 'all':
        return 'همه دوره‌ها'

    if params['period'] == 'month' and params.get('year') and params.get('month'):
        return f"ماه {params['month']} سال {params['year']}"

    if params['period'] == 'season' and params.get('year') and params.get('season'):
        return f"{get_season_name(params['season'])} سال {params['year']}"

    if params['period'] == 'range':
        parts = []
        if params.get('date_from'):
            parts.append(f"از {params['date_from']}")
        if params.get('date_to'):
            parts.append(f"تا {params['date_to']}")
        return ' '.join(parts) if parts else 'بازه دلخواه (در انتظار تاریخ)'

    return 'فیلتر فعال'