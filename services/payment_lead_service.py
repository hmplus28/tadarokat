"""گزارش لید تایم پرداخت — ثبت واریزی (AP) تا انجام واریزی (AQ)"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from purchases.models import Purchase, is_real_date
from services.stage_analytics import days_between, parse_jalali_date

DEFAULT_LEAD_DAYS = 7

DAY_BUCKETS = (
    ('on_time', 'تا مهلت (در لید تایم)', lambda d, limit: d <= limit),
    ('8_14', '۸ تا ۱۴ روز', lambda d, limit: limit < d <= 14),
    ('15_21', '۱۵ تا ۲۱ روز', lambda d, limit: 14 < d <= 21),
    ('22_plus', '۲۲ روز به بالا', lambda d, limit: d > 21),
)


class PaymentLeadService:
    @classmethod
    def get_lead_days_for_category(cls, category_name: str) -> int:
        if not category_name:
            return DEFAULT_LEAD_DAYS
        from accounts.models import ProductCategory

        cat = ProductCategory.objects.filter(name=category_name, is_active=True).first()
        if cat and cat.payment_lead_days:
            return int(cat.payment_lead_days)
        return DEFAULT_LEAD_DAYS

    @classmethod
    def can_evaluate(cls, purchase) -> bool:
        reg = getattr(purchase, 'payment_registration_date', '') or ''
        done = getattr(purchase, 'payment_completion_date', '') or ''
        if not is_real_date(reg) or not is_real_date(done):
            return False
        return days_between(reg, done) is not None

    @classmethod
    def get_actual_days(cls, purchase) -> Optional[int]:
        if not cls.can_evaluate(purchase):
            return None
        return days_between(
            purchase.payment_registration_date,
            purchase.payment_completion_date,
        )

    @classmethod
    def evaluate_purchase(cls, purchase) -> bool:
        actual = cls.get_actual_days(purchase)
        if actual is None:
            return False
        limit = cls.get_lead_days_for_category(purchase.product_category)
        return actual > limit

    @classmethod
    def get_evaluation_detail(cls, purchase) -> Dict[str, Any]:
        reg = getattr(purchase, 'payment_registration_date', '') or ''
        done = getattr(purchase, 'payment_completion_date', '') or ''
        limit = cls.get_lead_days_for_category(purchase.product_category)

        if not is_real_date(reg):
            return {'status': 'no_registration', 'label': 'بدون تاریخ ثبت واریزی'}
        if not is_real_date(done):
            return {'status': 'no_completion', 'label': 'بدون تاریخ انجام واریزی'}

        actual = cls.get_actual_days(purchase)
        if actual is None:
            return {'status': 'bad_date', 'label': 'تاریخ نامعتبر'}

        on_time = actual <= limit
        over = max(actual - limit, 0)
        return {
            'status': 'on_time' if on_time else 'deviated',
            'label': 'در مهلت' if on_time else 'انحراف لید تایم',
            'registration_date': reg,
            'completion_date': done,
            'actual_days': actual,
            'lead_days': limit,
            'over_days': over,
        }

    @classmethod
    def recalculate_all(cls) -> int:
        to_update = []
        for purchase in Purchase.objects.only(
            'pk',
            'product_category',
            'payment_registration_date',
            'payment_completion_date',
            'payment_lead_deviated',
        ).iterator(chunk_size=500):
            deviated = cls.evaluate_purchase(purchase)
            if purchase.payment_lead_deviated != deviated:
                purchase.payment_lead_deviated = deviated
                to_update.append(purchase)

        if to_update:
            Purchase.objects.bulk_update(
                to_update, ['payment_lead_deviated'], batch_size=500
            )
        return len(to_update)

    @classmethod
    def _aggregate_values(cls, days_list: List[int]) -> Dict[str, Optional[float]]:
        if not days_list:
            return {'avg_days': None, 'median_days': None, 'max_days': None}
        days_list = sorted(days_list)
        avg = round(sum(days_list) / len(days_list), 1)
        mid = len(days_list) // 2
        if len(days_list) % 2:
            median = float(days_list[mid])
        else:
            median = round((days_list[mid - 1] + days_list[mid]) / 2, 1)
        return {
            'avg_days': avg,
            'median_days': median,
            'max_days': float(days_list[-1]),
        }

    @classmethod
    def _bucket_counts(cls, days_list: List[int], lead_days: int) -> Dict[str, int]:
        counts = {key: 0 for key, *_ in DAY_BUCKETS}
        for day in days_list:
            for key, _label, matcher in DAY_BUCKETS:
                if matcher(day, lead_days):
                    counts[key] += 1
                    break
        return counts

    @classmethod
    def get_summary_by_category(cls, base_queryset=None) -> List[Dict[str, Any]]:
        from accounts.models import ProductCategory

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        category_days: Dict[str, List[int]] = {}
        category_meta: Dict[str, Dict[str, Any]] = {}

        for purchase in base_queryset.iterator(chunk_size=500):
            actual = cls.get_actual_days(purchase)
            if actual is None:
                continue
            name = (purchase.product_category or '').strip() or 'بدون گروه کالایی'
            category_days.setdefault(name, []).append(actual)
            if name not in category_meta:
                category_meta[name] = {
                    'evaluated': 0,
                    'on_time': 0,
                    'deviated': 0,
                }
            category_meta[name]['evaluated'] += 1
            limit = cls.get_lead_days_for_category(purchase.product_category)
            if actual <= limit:
                category_meta[name]['on_time'] += 1
            else:
                category_meta[name]['deviated'] += 1

        results = []
        seen = set()

        for cat in ProductCategory.objects.filter(is_active=True).order_by('sort_order', 'name'):
            days_list = category_days.get(cat.name, [])
            stats = cls._build_category_row(cat.name, days_list, cat.payment_lead_days)
            results.append(stats)
            seen.add(cat.name)

        for name, days_list in category_days.items():
            if name in seen:
                continue
            limit = cls.get_lead_days_for_category(
                '' if name == 'بدون گروه کالایی' else name
            )
            results.append(cls._build_category_row(name, days_list, limit))

        results.sort(key=lambda row: (-row['deviated'], -row['evaluated'], row['name']))
        return results

    @classmethod
    def _build_category_row(cls, name: str, days_list: List[int], lead_days: int) -> Dict[str, Any]:
        evaluated = len(days_list)
        on_time = sum(1 for d in days_list if d <= lead_days)
        deviated = evaluated - on_time
        agg = cls._aggregate_values(days_list)
        buckets = cls._bucket_counts(days_list, lead_days)
        return {
            'name': name,
            'lead_days': lead_days,
            'evaluated': evaluated,
            'on_time': on_time,
            'deviated': deviated,
            'rate': round(deviated / evaluated * 100, 1) if evaluated else 0,
            'avg_days': agg['avg_days'],
            'median_days': agg['median_days'],
            'max_days': agg['max_days'],
            'buckets': buckets,
        }

    @classmethod
    def get_overall_summary(cls, base_queryset=None) -> Dict[str, Any]:
        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        days_list = []
        for purchase in base_queryset.iterator(chunk_size=500):
            actual = cls.get_actual_days(purchase)
            if actual is not None:
                days_list.append(actual)

        evaluated = len(days_list)
        if not evaluated:
            return {
                'evaluated': 0,
                'on_time': 0,
                'deviated': 0,
                'rate': 0,
                'avg_days': None,
                'median_days': None,
                'default_lead_days': DEFAULT_LEAD_DAYS,
            }

        on_time = 0
        for purchase in base_queryset.iterator(chunk_size=500):
            actual = cls.get_actual_days(purchase)
            if actual is None:
                continue
            if actual <= cls.get_lead_days_for_category(purchase.product_category):
                on_time += 1
        deviated = evaluated - on_time
        agg = cls._aggregate_values(days_list)
        return {
            'evaluated': evaluated,
            'on_time': on_time,
            'deviated': deviated,
            'rate': round(deviated / evaluated * 100, 1),
            'avg_days': agg['avg_days'],
            'median_days': agg['median_days'],
            'default_lead_days': DEFAULT_LEAD_DAYS,
        }

    @classmethod
    def get_deviated_cases_page(
        cls,
        base_queryset=None,
        category_name: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list, int]:
        """پرونده‌های انحراف لید تایم — فیلتر گروه کالایی + صفحه‌بندی"""
        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        queryset = (
            base_queryset
            .filter(payment_lead_deviated=True)
            .order_by('-pk')
        )
        if category_name:
            queryset = queryset.filter(product_category=category_name)

        total = queryset.count()
        page_qs = queryset[offset:offset + limit]

        rows = []
        for purchase in page_qs:
            detail = cls.get_evaluation_detail(purchase)
            rows.append({
                'pk': purchase.pk,
                'purchase_number': purchase.purchase_number,
                'product_title': (purchase.product_title or '')[:80],
                'product_category': purchase.product_category,
                'expert_name': purchase.expert_name,
                'registration_date': detail.get('registration_date', '—'),
                'completion_date': detail.get('completion_date', '—'),
                'actual_days': detail.get('actual_days', 0),
                'lead_days': detail.get('lead_days', DEFAULT_LEAD_DAYS),
                'over_days': detail.get('over_days', 0),
            })
        return rows, total

    @classmethod
    def get_recent_deviated(
        cls,
        base_queryset=None,
        limit: Optional[int] = 30,
    ) -> List[Dict[str, Any]]:
        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        queryset = base_queryset.filter(payment_lead_deviated=True).order_by('-pk')
        if limit is not None:
            queryset = queryset[:limit]

        rows = []
        for purchase in queryset:
            detail = cls.get_evaluation_detail(purchase)
            rows.append({
                'pk': purchase.pk,
                'purchase_number': purchase.purchase_number,
                'product_category': purchase.product_category,
                'expert_name': purchase.expert_name,
                'registration_date': detail.get('registration_date', '—'),
                'completion_date': detail.get('completion_date', '—'),
                'actual_days': detail.get('actual_days', 0),
                'lead_days': detail.get('lead_days', DEFAULT_LEAD_DAYS),
                'over_days': detail.get('over_days', 0),
            })
        return rows