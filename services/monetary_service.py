"""نرمال‌سازی مبالغ — تشخیص و اصلاح مقادیر اشتباه خوانده‌شده به تومان (اکسل)"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Iterable, Mapping, MutableMapping, Optional

from purchases.models import Purchase


class MonetaryService:
    """
    همه مبالغ سیستم بر مبنای ریال هستند.
    گاهی یک ستون اکسل به‌اشتباه به تومان import می‌شود (≈۱/۱۰ بقیه فیلدها).
    """

    MONETARY_FIELDS = (
        'order_total',
        'advance_payment',
        'payment_request_amount',
        'invoice_total',
        'preinvoice_total',
        'preinvoice_price',
        'invoice_price',
        'deductions',
    )

    TOMAN_RATIO_LOW = Decimal('0.075')
    TOMAN_RATIO_HIGH = Decimal('0.125')
    RIAL_MULTIPLIER = Decimal('10')

    @classmethod
    def _positive_values(cls, amounts: Mapping[str, Decimal]) -> Dict[str, Decimal]:
        return {
            key: value
            for key, value in amounts.items()
            if value and value > 0
        }

    @classmethod
    def _is_likely_toman(cls, value: Decimal, peers: Iterable[Decimal]) -> bool:
        larger_peers = [peer for peer in peers if peer > value * 2]
        if not larger_peers:
            return False
        reference = sorted(larger_peers)[len(larger_peers) // 2]
        ratio = value / reference
        return cls.TOMAN_RATIO_LOW <= ratio <= cls.TOMAN_RATIO_HIGH

    @classmethod
    def normalize_amounts(
        cls,
        amounts: Mapping[str, Decimal],
        fields: Optional[Iterable[str]] = None,
    ) -> Dict[str, Decimal]:
        target_fields = tuple(fields or cls.MONETARY_FIELDS)
        normalized = {field: Decimal(amounts.get(field) or 0) for field in target_fields}
        positive = cls._positive_values(normalized)
        if len(positive) < 2:
            return normalized

        peer_values = list(positive.values())
        for field, value in positive.items():
            peers = [peer for key, peer in positive.items() if key != field]
            if cls._is_likely_toman(value, peers):
                normalized[field] = value * cls.RIAL_MULTIPLIER
        return normalized

    @classmethod
    def normalize_purchase_data(cls, data: MutableMapping) -> MutableMapping:
        amounts = {
            field: Decimal(data.get(field) or 0)
            for field in cls.MONETARY_FIELDS
            if field in data
        }
        if not amounts:
            return data
        normalized = cls.normalize_amounts(amounts)
        for field, value in normalized.items():
            data[field] = value
        return data

    @classmethod
    def get_purchase_amounts(cls, purchase: Purchase) -> Dict[str, Decimal]:
        raw = {
            field: Decimal(getattr(purchase, field, 0) or 0)
            for field in cls.MONETARY_FIELDS
        }
        return cls.normalize_amounts(raw)