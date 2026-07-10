"""تجمیع مبالغ سطح سفارش — جلوگیری از شمارش تکراری جمع کل (AC)"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from purchases.models import Purchase


class OrderAmountService:
    """
    جمع کل سفارش (order_total / AC) مربوط به کل سفارش است، نه هر ردیف کالا.
    ردیف‌های با شماره سفارش یکسان فقط یک‌بار در جمع گزارش‌ها لحاظ می‌شوند.
    """

    AMOUNT_FIELD = 'order_total'
    KEY_FIELD = 'order_request_number'

    @classmethod
    def dedupe_key(cls, purchase: Purchase) -> str:
        order_no = (getattr(purchase, cls.KEY_FIELD, '') or '').strip()
        if order_no:
            return f'order:{order_no}'
        return f'line:{purchase.pk}'

    @classmethod
    def get_amount(cls, purchase: Purchase, field: str = AMOUNT_FIELD) -> Decimal:
        try:
            return Decimal(getattr(purchase, field, 0) or 0)
        except Exception:
            return Decimal(0)

    @classmethod
    def iter_unique_amount_rows(
        cls,
        queryset,
        field: str = AMOUNT_FIELD,
        fields: Optional[Iterable[str]] = None,
    ) -> Iterable[Tuple[Purchase, Decimal, str]]:
        only_fields = {
            'pk', cls.KEY_FIELD, field, 'product_category',
            *(fields or ()),
        }
        seen: Set[str] = set()

        for purchase in queryset.order_by('pk').only(*only_fields).iterator(chunk_size=500):
            key = cls.dedupe_key(purchase)
            if key in seen:
                continue
            seen.add(key)
            amount = cls.get_amount(purchase, field)
            if amount > 0:
                yield purchase, amount, key

    @classmethod
    def sum_unique_amounts(cls, queryset, field: str = AMOUNT_FIELD) -> Decimal:
        return sum(
            (amount for _, amount, _ in cls.iter_unique_amount_rows(queryset, field=field)),
            Decimal(0),
        )

    @classmethod
    def category_label(cls, purchase: Purchase, unassigned: str = 'بدون گروه کالایی') -> str:
        return (purchase.product_category or '').strip() or unassigned

    @classmethod
    def aggregate_by_category(
        cls,
        queryset,
        field: str = AMOUNT_FIELD,
        unassigned: str = 'بدون گروه کالایی',
    ) -> Dict[str, Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'amount': Decimal(0),
                'order_keys': set(),
                'line_count': 0,
            }
        )
        seen_global: Set[str] = set()

        for purchase in queryset.order_by('pk').only(
            'pk', cls.KEY_FIELD, field, 'product_category'
        ).iterator(chunk_size=500):
            category = cls.category_label(purchase, unassigned)
            bucket = buckets[category]
            bucket['line_count'] += 1

            key = cls.dedupe_key(purchase)
            if key in seen_global:
                continue

            amount = cls.get_amount(purchase, field)
            if amount <= 0:
                continue

            seen_global.add(key)
            bucket['amount'] += amount
            bucket['order_keys'].add(key)

        return {
            name: {
                'amount': data['amount'],
                'purchase_count': data['line_count'],
                'with_amount': len(data['order_keys']),
                'order_count': len(data['order_keys']),
            }
            for name, data in buckets.items()
        }