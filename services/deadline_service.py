"""بررسی انحراف از مهلت ثبت درخواست بر اساس گروه کالایی"""
from typing import Optional, List, Tuple, Dict, Any


class DeadlineService:
    """
    مهلت مجاز بر اساس تاریخ ثبت درخواست.

    ملاک تاریخ (به ترتیب اولویت):
    1. تاریخ درخواست کالا (request_date) — درخواست از انبار
    2. تاریخ درخواست (purchase_date) — اگر ستون کالا خالی باشد (درخواست مستقیم انبار)

    - روزهای مشخص ماه: مثلاً ۵ و ۲۵ — درخواست باید تا آن روز ثبت شده باشد
    - شنبه هر هفته: مهلت هر هفته = شنبه همان هفته در تقویم شمسی
    """

    DATE_SOURCE_LABELS = {
        'request_date': 'تاریخ درخواست کالا',
        'purchase_date': 'تاریخ درخواست',
    }

    @staticmethod
    def parse_jalali_date(date_str: str) -> Optional[Tuple[int, int, int]]:
        if not date_str:
            return None
        parts = str(date_str).strip().replace('-', '/').split('/')
        if len(parts) < 3:
            return None
        try:
            year = int(parts[0].strip())
            month = int(parts[1].strip())
            day = int(parts[2].strip().split()[0])
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return None
            return year, month, day
        except (ValueError, IndexError):
            return None

    @staticmethod
    def parse_jalali_day(date_str: str) -> Optional[int]:
        parsed = DeadlineService.parse_jalali_date(date_str)
        return parsed[2] if parsed else None

    @staticmethod
    def is_on_time(day: int, allowed_days: List[int]) -> bool:
        """آیا روز درخواست تا یکی از مهلت‌های مجاز همان ماه ثبت شده؟"""
        if not allowed_days:
            return True
        for deadline in sorted(allowed_days):
            if day <= deadline:
                return True
        return False

    @classmethod
    def get_allowed_days_for_rule(cls, rule, year: int, month: int) -> List[int]:
        return rule.compute_allowed_days_in_month(year, month)

    @classmethod
    def get_effective_request_date(cls, purchase) -> str:
        """تاریخ ملاک انحراف — اول درخواست کالا، در صورت خالی بودن تاریخ درخواست."""
        from purchases.models import is_real_date

        request_date = getattr(purchase, 'request_date', '') or ''
        if is_real_date(request_date):
            return str(request_date).strip()

        purchase_date = getattr(purchase, 'purchase_date', '') or ''
        if is_real_date(purchase_date):
            return str(purchase_date).strip()

        return ''

    @classmethod
    def get_effective_date_source(cls, purchase) -> str:
        from purchases.models import is_real_date

        request_date = getattr(purchase, 'request_date', '') or ''
        if is_real_date(request_date):
            return 'request_date'

        purchase_date = getattr(purchase, 'purchase_date', '') or ''
        if is_real_date(purchase_date):
            return 'purchase_date'

        return ''

    @classmethod
    def _evaluable_date_q(cls):
        """پرونده‌هایی که حداقل یکی از دو تاریخ برای محاسبه دارند."""
        from django.db.models import Q

        return (
            (~Q(request_date='') & ~Q(request_date__isnull=True))
            | (
                (Q(request_date='') | Q(request_date__isnull=True))
                & ~Q(purchase_date='')
                & ~Q(purchase_date__isnull=True)
            )
        )

    @classmethod
    def filter_queryset_for_report(cls, queryset, filter_params):
        """فیلتر گزارش انحراف بر اساس تاریخ ملاک (نه فقط purchase_date)."""
        from services.date_filter import (
            filter_queryset_by_search,
            purchase_matches_filter,
            is_range_filter_ready,
        )

        if filter_params.get('period') == 'all':
            filtered = queryset
        elif filter_params.get('period') == 'range' and not is_range_filter_ready(filter_params):
            filtered = queryset
        else:
            matched_ids = []
            for purchase in queryset.only('pk', 'request_date', 'purchase_date').iterator(chunk_size=500):
                effective_date = cls.get_effective_request_date(purchase)
                if purchase_matches_filter(effective_date, filter_params):
                    matched_ids.append(purchase.pk)
            filtered = queryset.filter(pk__in=matched_ids) if matched_ids else queryset.none()

        return filter_queryset_by_search(filtered, filter_params)

    @classmethod
    def get_rule_for_category(cls, category_name: str):
        if not category_name:
            return None
        from accounts.models import CategoryDeadlineRule
        return (
            CategoryDeadlineRule.objects
            .select_related('category')
            .filter(category__name=category_name, is_active=True)
            .first()
        )

    @classmethod
    def evaluate_purchase(cls, purchase) -> bool:
        """آیا پرونده انحراف از مهلت دارد؟"""
        effective_date = cls.get_effective_request_date(purchase)
        if not purchase.product_category or not effective_date:
            return False

        parsed = cls.parse_jalali_date(effective_date)
        if not parsed:
            return False

        year, month, day = parsed
        rule = cls.get_rule_for_category(purchase.product_category)
        if not rule:
            return False

        allowed = cls.get_allowed_days_for_rule(rule, year, month)
        if not allowed:
            return False

        return not cls.is_on_time(day, allowed)

    @classmethod
    def get_evaluation_detail(cls, purchase) -> Dict[str, Any]:
        """جزئیات بررسی مهلت برای نمایش در گزارش"""
        if not purchase.product_category:
            return {'status': 'no_category', 'label': 'بدون گروه کالایی'}

        effective_date = cls.get_effective_request_date(purchase)
        date_source = cls.get_effective_date_source(purchase)
        if not effective_date:
            return {'status': 'no_date', 'label': 'بدون تاریخ درخواست کالا یا درخواست'}

        parsed = cls.parse_jalali_date(effective_date)
        if not parsed:
            return {'status': 'bad_date', 'label': 'تاریخ نامعتبر'}

        year, month, day = parsed
        rule = cls.get_rule_for_category(purchase.product_category)
        if not rule:
            return {'status': 'no_rule', 'label': 'قانون مهلت تعریف نشده'}

        allowed = cls.get_allowed_days_for_rule(rule, year, month)
        on_time = cls.is_on_time(day, allowed)
        nearest = next((d for d in sorted(allowed) if day <= d), None)

        return {
            'status': 'on_time' if on_time else 'deviated',
            'label': 'به‌موقع' if on_time else 'انحراف از مهلت',
            'rule_description': rule.describe_rule(),
            'request_day': day,
            'allowed_days': allowed,
            'nearest_deadline': nearest,
            'effective_date': effective_date,
            'date_source': date_source,
            'date_source_label': cls.DATE_SOURCE_LABELS.get(date_source, '—'),
            'purchase_date': purchase.purchase_date,
            'request_date': getattr(purchase, 'request_date', '') or '',
        }

    @classmethod
    def sync_category_from_inquiries(cls) -> int:
        """کپی گروه کالایی از استعلام‌های صادرشده به پرونده خرید"""
        from purchases.models import Purchase
        from inquiries.models import Inquiry

        updated = 0
        for inquiry in Inquiry.objects.exclude(product_category='').select_related('purchase'):
            if not inquiry.purchase_id:
                continue
            purchase = inquiry.purchase
            if purchase.product_category != inquiry.product_category:
                purchase.product_category = inquiry.product_category
                purchase.save(update_fields=['product_category'])
                updated += 1
        return updated

    @classmethod
    def auto_assign_product_categories(cls) -> int:
        """تخصیص گروه کالایی بر اساس پیشوند کد کالا (برای داده‌های قدیمی اکسل)"""
        from accounts.models import ProductCategory
        from purchases.models import Purchase

        prefix_map = []
        for cat in ProductCategory.objects.filter(is_active=True).exclude(code_prefixes=''):
            for part in cat.code_prefixes.split(','):
                prefix = part.strip()
                if prefix:
                    prefix_map.append((prefix, cat.name))
        if not prefix_map:
            return 0

        prefix_map.sort(key=lambda item: -len(item[0]))
        updated = 0
        for purchase in Purchase.objects.filter(product_category='').exclude(product_code=''):
            code = (purchase.product_code or '').strip()
            if not code:
                continue
            for prefix, category_name in prefix_map:
                if code.startswith(prefix):
                    purchase.product_category = category_name
                    purchase.save(update_fields=['product_category'])
                    updated += 1
                    break
        return updated

    @classmethod
    def refresh_all_categories_and_deadlines(cls) -> dict:
        """همگام‌سازی گروه + بازمحاسبه انحراف"""
        stats = {
            'from_inquiries': cls.sync_category_from_inquiries(),
            'from_code_prefix': cls.auto_assign_product_categories(),
            'deadline_updated': cls.recalculate_all(),
        }
        return stats

    @classmethod
    def recalculate_all(cls) -> int:
        from purchases.models import Purchase

        to_update = []
        for purchase in Purchase.objects.only(
            'pk', 'product_category', 'request_date', 'purchase_date', 'deadline_deviated'
        ).iterator(chunk_size=500):
            deviated = cls.evaluate_purchase(purchase)
            if purchase.deadline_deviated != deviated:
                purchase.deadline_deviated = deviated
                to_update.append(purchase)

        if to_update:
            Purchase.objects.bulk_update(to_update, ['deadline_deviated'], batch_size=500)
        return len(to_update)

    @classmethod
    def describe_status(cls, purchase) -> str:
        detail = cls.get_evaluation_detail(purchase)
        if detail['status'] in ('on_time', 'deviated'):
            if detail['status'] == 'deviated':
                return f"انحراف ({detail['rule_description']})"
            return 'به‌موقع'
        return detail.get('label', '—')

    @classmethod
    def get_summary_by_category(cls, base_queryset=None) -> List[Dict[str, Any]]:
        from accounts.models import ProductCategory
        from purchases.models import Purchase
        from django.db.models import Count, Q

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        results = []
        for cat in ProductCategory.objects.filter(is_active=True).order_by('sort_order', 'name'):
            qs = base_queryset.filter(product_category=cat.name)
            agg = qs.aggregate(
                total=Count('id'),
                evaluated=Count('id', filter=cls._evaluable_date_q()),
                deviated=Count('id', filter=Q(deadline_deviated=True)),
            )
            evaluated = agg['evaluated'] or 0
            deviated = agg['deviated'] or 0
            on_time = max(evaluated - deviated, 0)
            rule = cls.get_rule_for_category(cat.name)

            no_rule = not (rule and rule.is_active)
            results.append({
                'name': cat.name,
                'rule': rule.describe_rule() if rule else 'قانون تعریف نشده',
                'rule_active': bool(rule and rule.is_active),
                'has_rule': bool(rule),
                'no_rule': no_rule,
                'total': agg['total'] or 0,
                'evaluated': evaluated,
                'on_time': on_time,
                'deviated': deviated,
                'rate': round(deviated / evaluated * 100, 1) if evaluated else 0,
                'code_prefixes': cat.code_prefixes or '',
            })
        return results

    @classmethod
    def get_unassigned_summary(cls, base_queryset=None) -> Dict[str, Any]:
        from purchases.models import Purchase
        from django.db.models import Count, Q

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        qs = base_queryset.filter(product_category='')
        agg = qs.aggregate(
            total=Count('id'),
            with_date=Count('id', filter=cls._evaluable_date_q()),
            with_code=Count('id', filter=~Q(product_code='')),
        )
        return {
            'total': agg['total'] or 0,
            'with_date': agg['with_date'] or 0,
            'with_code': agg['with_code'] or 0,
        }

    @classmethod
    def get_summary_by_warehouse(cls, base_queryset=None) -> List[Dict[str, Any]]:
        from purchases.models import Purchase
        from inquiries.models import Inquiry
        from django.db.models import Count, Q, OuterRef, Subquery

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        warehouse_subq = Inquiry.objects.filter(
            purchase_id=OuterRef('pk')
        ).order_by('-pk').values('warehouse')[:1]

        rows = (
            base_queryset
            .filter(cls._evaluable_date_q())
            .annotate(dest_warehouse=Subquery(warehouse_subq))
            .values('dest_warehouse')
            .annotate(
                total=Count('id'),
                deviated=Count('id', filter=Q(deadline_deviated=True)),
            )
            .order_by('-deviated', '-total')
        )

        results = []
        for row in rows:
            wh = (row['dest_warehouse'] or '').strip() or 'در انتظار تعیین انبار'
            total = row['total'] or 0
            deviated = row['deviated'] or 0
            on_time = max(total - deviated, 0)
            results.append({
                'name': wh,
                'total': total,
                'evaluated': total,
                'on_time': on_time,
                'deviated': deviated,
                'rate': round(deviated / total * 100, 1) if total else 0,
            })
        return results

    @classmethod
    def get_overall_summary(cls, base_queryset=None) -> Dict[str, Any]:
        from purchases.models import Purchase
        from django.db.models import Count, Q

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        evaluable = cls._evaluable_date_q() & ~Q(product_category='')
        no_date_q = ~cls._evaluable_date_q()
        agg = base_queryset.aggregate(
            total=Count('id'),
            evaluated=Count('id', filter=evaluable),
            deviated=Count('id', filter=Q(deadline_deviated=True)),
            no_category=Count('id', filter=Q(product_category='')),
            no_date=Count('id', filter=no_date_q),
        )
        evaluated = agg['evaluated'] or 0
        deviated = agg['deviated'] or 0
        return {
            'total': agg['total'] or 0,
            'evaluated': evaluated,
            'on_time': max(evaluated - deviated, 0),
            'deviated': deviated,
            'no_category': agg['no_category'] or 0,
            'no_date': agg['no_date'] or 0,
            'rate': round(deviated / evaluated * 100, 1) if evaluated else 0,
        }

    @classmethod
    def get_deviated_cases_page(
        cls,
        base_queryset=None,
        category_name: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Tuple[list, int]:
        """پرونده‌های انحراف مهلت درخواست — اختیاری فیلتر گروه کالایی + صفحه‌بندی"""
        from inquiries.models import Inquiry
        from django.db.models import OuterRef, Subquery

        if base_queryset is None:
            from purchases.models import Purchase
            base_queryset = Purchase.objects.all()

        wh_subq = (
            Inquiry.objects
            .filter(purchase_id=OuterRef('pk'))
            .order_by('-pk')
            .values('warehouse')[:1]
        )
        queryset = (
            base_queryset
            .filter(deadline_deviated=True)
            .annotate(warehouse=Subquery(wh_subq))
            .order_by('-pk')
        )
        if category_name:
            queryset = queryset.filter(product_category=category_name)

        total = queryset.count()
        page_qs = queryset[offset:offset + limit]

        results = []
        for purchase in page_qs:
            detail = cls.get_evaluation_detail(purchase)
            allowed = detail.get('allowed_days') or []
            allowed_str = '، '.join(str(d) for d in allowed) if allowed else '—'
            results.append(cls._format_deviated_case_row(purchase, detail, allowed_str))
        return results, total

    @classmethod
    def _format_deviated_case_row(cls, purchase, detail: Dict[str, Any], allowed_str: str) -> Dict[str, Any]:
        return {
            'pk': purchase.pk,
            'purchase_number': purchase.purchase_number,
            'product_title': (purchase.product_title or '')[:80],
            'product_category': purchase.product_category,
            'request_date': getattr(purchase, 'request_date', '') or '',
            'purchase_date': purchase.purchase_date,
            'effective_date': detail.get('effective_date', ''),
            'date_source_label': detail.get('date_source_label', '—'),
            'warehouse': purchase.warehouse,
            'deadline_info': (
                f"روز {detail.get('request_day', '—')} ({detail.get('date_source_label', '—')}) — مهلت‌ها: {allowed_str}"
                if detail.get('status') == 'deviated'
                else detail.get('label', '—')
            ),
        }

    @classmethod
    def get_deviated_cases(cls, base_queryset=None, limit=None) -> list:
        """لیست پرونده‌های دارای انحراف مهلت درخواست"""
        from inquiries.models import Inquiry
        from django.db.models import OuterRef, Subquery

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        wh_subq = (
            Inquiry.objects
            .filter(purchase_id=OuterRef('pk'))
            .order_by('-pk')
            .values('warehouse')[:1]
        )
        queryset = (
            base_queryset
            .filter(deadline_deviated=True)
            .annotate(warehouse=Subquery(wh_subq))
            .order_by('-pk')
        )
        if limit is not None:
            queryset = queryset[:limit]

        results = []
        for purchase in queryset:
            detail = cls.get_evaluation_detail(purchase)
            allowed = detail.get('allowed_days') or []
            allowed_str = '، '.join(str(d) for d in allowed) if allowed else '—'
            results.append(cls._format_deviated_case_row(purchase, detail, allowed_str))
        return results