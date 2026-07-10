"""بررسی انحراف از مهلت سفارش — مقایسه مهلت (ستون O) با تاریخ سفارش (ستون AB)"""
from typing import Any, Dict, List, Optional

from purchases.models import Purchase, is_real_date
from services.stage_analytics import parse_jalali_date


class OrderDeadlineService:
    """
    ملاک:
    - مهلت: inquiry_deadline (ستون O اکسل) یا در صورت خالی بودن inquiry_deadline_2 (ستون P)
    - تاریخ واقعی: order_request_date (ستون AB اکسل — «تاریخ سفارش»)

    سفارش به‌موقع است اگر تاریخ سفارش <= مهلت باشد.
    """

    @classmethod
    def get_effective_deadline(cls, purchase) -> str:
        for field in ('inquiry_deadline', 'inquiry_deadline_2'):
            val = getattr(purchase, field, '') or ''
            if is_real_date(val):
                return str(val).strip()
        return ''

    @classmethod
    def can_evaluate(cls, purchase) -> bool:
        deadline = cls.get_effective_deadline(purchase)
        order_date = getattr(purchase, 'order_request_date', '') or ''
        return bool(deadline and is_real_date(order_date))

    @classmethod
    def evaluate_purchase(cls, purchase) -> bool:
        """آیا پرونده از مهلت سفارش انحراف دارد؟"""
        if not cls.can_evaluate(purchase):
            return False

        deadline = parse_jalali_date(cls.get_effective_deadline(purchase))
        order_date = parse_jalali_date(purchase.order_request_date)
        if not deadline or not order_date:
            return False

        return order_date > deadline

    @classmethod
    def get_delay_days(cls, purchase) -> Optional[int]:
        if not cls.can_evaluate(purchase):
            return None
        deadline = parse_jalali_date(cls.get_effective_deadline(purchase))
        order_date = parse_jalali_date(purchase.order_request_date)
        if not deadline or not order_date:
            return None
        delta = (order_date - deadline).days
        return delta if delta > 0 else 0

    @classmethod
    def get_evaluation_detail(cls, purchase) -> Dict[str, Any]:
        deadline_str = cls.get_effective_deadline(purchase)
        order_date = getattr(purchase, 'order_request_date', '') or ''

        if not deadline_str:
            return {'status': 'no_deadline', 'label': 'بدون مهلت سفارش'}
        if not is_real_date(order_date):
            return {'status': 'no_order_date', 'label': 'بدون تاریخ سفارش'}

        deadline = parse_jalali_date(deadline_str)
        order_dt = parse_jalali_date(order_date)
        if not deadline or not order_dt:
            return {'status': 'bad_date', 'label': 'تاریخ نامعتبر'}

        on_time = order_dt <= deadline
        delay = max((order_dt - deadline).days, 0)
        return {
            'status': 'on_time' if on_time else 'deviated',
            'label': 'به‌موقع' if on_time else 'انحراف از مهلت سفارش',
            'deadline': deadline_str,
            'order_date': order_date,
            'delay_days': delay,
        }

    @classmethod
    def recalculate_all(cls) -> int:
        to_update = []
        for purchase in Purchase.objects.only(
            'pk',
            'inquiry_deadline',
            'inquiry_deadline_2',
            'order_request_date',
            'order_deadline_deviated',
        ).iterator(chunk_size=500):
            deviated = cls.evaluate_purchase(purchase)
            if purchase.order_deadline_deviated != deviated:
                purchase.order_deadline_deviated = deviated
                to_update.append(purchase)

        if to_update:
            Purchase.objects.bulk_update(
                to_update, ['order_deadline_deviated'], batch_size=500
            )
        return len(to_update)

    @classmethod
    def get_overall_summary(cls, base_queryset=None) -> Dict[str, Any]:
        from django.db.models import Count, Q

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        agg = base_queryset.aggregate(
            total=Count('id'),
            no_deadline=Count('id', filter=Q(inquiry_deadline='')),
            no_order_date=Count('id', filter=Q(order_request_date='')),
            deviated=Count('id', filter=Q(order_deadline_deviated=True)),
        )
        evaluated = 0
        on_time = 0
        deviated_evaluated = 0
        for purchase in base_queryset.only(
            'inquiry_deadline',
            'inquiry_deadline_2',
            'order_request_date',
            'order_deadline_deviated',
        ).iterator(chunk_size=500):
            if not cls.can_evaluate(purchase):
                continue
            evaluated += 1
            if purchase.order_deadline_deviated:
                deviated_evaluated += 1
            else:
                on_time += 1

        return {
            'total': agg['total'] or 0,
            'evaluated': evaluated,
            'on_time': on_time,
            'deviated': deviated_evaluated,
            'no_deadline': agg['no_deadline'] or 0,
            'no_order_date': agg['no_order_date'] or 0,
            'rate': round(deviated_evaluated / evaluated * 100, 1) if evaluated else 0,
        }

    @classmethod
    def get_summary_by_expert(cls, base_queryset=None) -> List[Dict[str, Any]]:
        from django.db.models import Count, Q

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        experts = (
            base_queryset
            .exclude(expert_name='')
            .values('expert_name')
            .annotate(total=Count('id'))
            .order_by('-total')
        )

        results = []
        for row in experts:
            name = row['expert_name']
            qs = base_queryset.filter(expert_name=name)
            evaluated = 0
            on_time = 0
            deviated = 0
            for purchase in qs.only(
                'inquiry_deadline', 'inquiry_deadline_2', 'order_request_date'
            ).iterator(chunk_size=200):
                if not cls.can_evaluate(purchase):
                    continue
                evaluated += 1
                if cls.evaluate_purchase(purchase):
                    deviated += 1
                else:
                    on_time += 1

            total = row['total'] or 0
            results.append({
                'name': name,
                'total': total,
                'evaluated': evaluated,
                'on_time': on_time,
                'deviated': deviated,
                'rate': round(deviated / evaluated * 100, 1) if evaluated else 0,
            })
        return results

    @classmethod
    def get_all_cases_by_expert(cls, base_queryset=None) -> List[Dict[str, Any]]:
        """تمام پرونده‌های قابل‌بررسی مهلت سفارش، گروه‌بندی‌شده بر اساس کارشناس"""
        experts_map: Dict[str, Dict[str, Any]] = {}

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        purchases = (
            base_queryset
            .exclude(expert_name='')
            .order_by('expert_name', '-pk')
            .only(
                'pk', 'expert_name', 'purchase_number', 'product_title',
                'inquiry_deadline', 'inquiry_deadline_2', 'order_request_date',
                'order_deadline_deviated',
            )
        )

        for purchase in purchases.iterator(chunk_size=500):
            if not cls.can_evaluate(purchase):
                continue

            name = (purchase.expert_name or '').strip()
            if not name:
                continue

            if name not in experts_map:
                experts_map[name] = {
                    'name': name,
                    'cases': [],
                    'evaluated': 0,
                    'on_time': 0,
                    'deviated': 0,
                }

            detail = cls.get_evaluation_detail(purchase)
            bucket = experts_map[name]
            bucket['evaluated'] += 1
            if detail.get('status') == 'deviated':
                bucket['deviated'] += 1
            else:
                bucket['on_time'] += 1

            bucket['cases'].append({
                'pk': purchase.pk,
                'purchase_number': purchase.purchase_number,
                'product_title': (purchase.product_title or '')[:80],
                'deadline': detail.get('deadline', '—'),
                'order_date': detail.get('order_date', '—'),
                'status': detail.get('label', '—'),
                'status_code': detail.get('status', ''),
                'delay_days': detail.get('delay_days', 0),
            })

        results = []
        for data in experts_map.values():
            ev = data['evaluated']
            data['rate'] = round(data['deviated'] / ev * 100, 1) if ev else 0
            data['total'] = ev
            results.append(data)

        results.sort(key=lambda row: (-row['deviated'], -row['evaluated'], row['name']))
        return results

    @classmethod
    def get_deviated_cases_page(
        cls,
        base_queryset=None,
        category_name: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list, int]:
        """پرونده‌های انحراف مهلت سفارش — فیلتر گروه کالایی + صفحه‌بندی"""
        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        queryset = (
            base_queryset
            .filter(order_deadline_deviated=True)
            .order_by('-pk')
        )
        if category_name:
            queryset = queryset.filter(product_category=category_name)

        total = queryset.count()
        page_qs = queryset[offset:offset + limit]

        results = []
        for purchase in page_qs.only(
            'pk', 'purchase_number', 'product_title', 'product_category',
            'expert_name', 'inquiry_deadline', 'inquiry_deadline_2', 'order_request_date',
        ):
            detail = cls.get_evaluation_detail(purchase)
            results.append({
                'pk': purchase.pk,
                'purchase_number': purchase.purchase_number,
                'product_title': (purchase.product_title or '')[:80],
                'product_category': purchase.product_category,
                'expert_name': purchase.expert_name or '—',
                'deadline': detail.get('deadline', '—'),
                'order_date': detail.get('order_date', '—'),
                'status': detail.get('label', '—'),
                'status_code': detail.get('status', ''),
                'delay_days': detail.get('delay_days', 0),
            })
        return results, total

    @classmethod
    def get_summary_by_category(cls, base_queryset=None) -> List[Dict[str, Any]]:
        from django.db.models import Count

        if base_queryset is None:
            base_queryset = Purchase.objects.all()

        categories = (
            base_queryset
            .exclude(product_category='')
            .values('product_category')
            .annotate(total=Count('id'))
            .order_by('-total')
        )

        results = []
        for row in categories:
            name = row['product_category']
            qs = base_queryset.filter(product_category=name)
            evaluated = 0
            on_time = 0
            deviated = 0
            for purchase in qs.only(
                'inquiry_deadline', 'inquiry_deadline_2', 'order_request_date'
            ).iterator(chunk_size=200):
                if not cls.can_evaluate(purchase):
                    continue
                evaluated += 1
                if cls.evaluate_purchase(purchase):
                    deviated += 1
                else:
                    on_time += 1

            results.append({
                'name': name,
                'total': row['total'] or 0,
                'evaluated': evaluated,
                'on_time': on_time,
                'deviated': deviated,
                'rate': round(deviated / evaluated * 100, 1) if evaluated else 0,
            })
        return results