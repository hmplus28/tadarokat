"""گزارش جمع مبالغ سفارش (ستون AC / order_total) به تفکیک گروه کالایی"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from django.db.models import Count, Q

from services.order_amount_service import OrderAmountService


class CategoryAmountService:
    UNASSIGNED_LABEL = 'بدون گروه کالایی'

    @classmethod
    def get_summary(cls, queryset) -> Dict[str, Any]:
        from accounts.models import ProductCategory

        amount_map = OrderAmountService.aggregate_by_category(
            queryset,
            unassigned=cls.UNASSIGNED_LABEL,
        )

        grand_total_decimal = sum(
            (row['amount'] for row in amount_map.values()),
            Decimal(0),
        )
        grand_total = float(grand_total_decimal)

        line_stats = queryset.aggregate(
            total_purchases=Count('id'),
            without_category=Count('id', filter=Q(product_category='')),
        )
        with_amount = sum(row['with_amount'] for row in amount_map.values())

        results: List[Dict[str, Any]] = []
        seen = set()

        for cat in ProductCategory.objects.filter(is_active=True).order_by('sort_order', 'name'):
            data = amount_map.get(cat.name, {})
            amount = float(data.get('amount') or 0)
            purchase_count = data.get('purchase_count') or 0
            order_count = data.get('order_count') or 0
            results.append({
                'name': cat.name,
                'amount': amount,
                'purchase_count': purchase_count,
                'order_count': order_count,
                'with_amount': order_count,
                'share': round(amount / grand_total * 100, 1) if grand_total else 0,
                'is_registered': True,
                'code_prefixes': cat.code_prefixes or '',
            })
            seen.add(cat.name)

        for name, data in amount_map.items():
            if name in seen:
                continue
            amount = float(data.get('amount') or 0)
            order_count = data.get('order_count') or 0
            results.append({
                'name': name,
                'amount': amount,
                'purchase_count': data.get('purchase_count') or 0,
                'order_count': order_count,
                'with_amount': order_count,
                'share': round(amount / grand_total * 100, 1) if grand_total else 0,
                'is_registered': name != cls.UNASSIGNED_LABEL,
                'code_prefixes': '',
            })

        results.sort(key=lambda row: (-row['amount'], row['name']))

        return {
            'grand_total': grand_total,
            'grand_total_decimal': grand_total_decimal,
            'total_purchases': line_stats['total_purchases'] or 0,
            'with_amount': with_amount,
            'without_category': line_stats['without_category'] or 0,
            'category_count': len([r for r in results if r['amount'] > 0]),
            'categories': results,
        }