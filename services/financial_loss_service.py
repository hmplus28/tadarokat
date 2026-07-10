"""گزارش ضرر مالی — مقایسه فاکتور با مبالغ خرید (بدون جمع‌کردن بودجه)"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional

from services.monetary_service import MonetaryService


class FinancialLossService:
    """
    ملاک:
    - مقایسه جداگانه — بدون جمع AC+AD+AN
    - مرجع اصلی: جمع کل سفارش (AC) در برابر جمع کل فاکتور (AL)
    - اگر AL > AC → ضرر مالی به اندازه اختلاف
    - AD و AN فقط برای نمایش مقایسه‌ای در گزارش
    """

    COMPARE_FIELDS = ('order_total', 'advance_payment', 'payment_request_amount')
    BASELINE_FIELD = 'order_total'
    FINANCIAL_AMOUNT_FIELDS = (
        'order_total', 'advance_payment', 'payment_request_amount', 'invoice_total',
    )
    EVAL_FIELDS = (
        'pk', 'purchase_number', 'order_request_number', 'product_title', 'product_code',
        'expert_name', 'product_category', 'purchase_date',
        *COMPARE_FIELDS, 'invoice_total',
    )
    ITERATOR_CHUNK_SIZE = 2000

    @classmethod
    def _to_decimal(cls, value) -> Decimal:
        try:
            return Decimal(value or 0)
        except Exception:
            return Decimal(0)

    @classmethod
    def _evaluable_queryset(cls, base_queryset):
        return base_queryset.filter(order_total__gt=0, invoice_total__gt=0)

    @classmethod
    def _normalize_amounts_from_row(cls, row: Mapping) -> Dict[str, Decimal]:
        raw = {
            field: cls._to_decimal(row.get(field))
            for field in cls.FINANCIAL_AMOUNT_FIELDS
        }
        return MonetaryService.normalize_amounts(raw, fields=cls.FINANCIAL_AMOUNT_FIELDS)

    @classmethod
    def _normalized_amounts(cls, purchase) -> Dict[str, Decimal]:
        raw = {
            field: cls._to_decimal(getattr(purchase, field, 0))
            for field in cls.FINANCIAL_AMOUNT_FIELDS
        }
        return MonetaryService.normalize_amounts(raw, fields=cls.FINANCIAL_AMOUNT_FIELDS)

    @classmethod
    def get_invoice_total(cls, purchase) -> Decimal:
        return cls._normalized_amounts(purchase)['invoice_total']

    @classmethod
    def get_baseline_total(cls, purchase) -> Decimal:
        return cls._normalized_amounts(purchase)[cls.BASELINE_FIELD]

    @classmethod
    def can_evaluate(cls, purchase) -> bool:
        return (
            cls._to_decimal(getattr(purchase, 'invoice_total', 0)) > 0
            and cls._to_decimal(getattr(purchase, cls.BASELINE_FIELD, 0)) > 0
        )

    @classmethod
    def _field_comparison(cls, invoice_total: Decimal, field_value: Decimal) -> Dict[str, Any]:
        if field_value <= 0:
            return {
                'has_value': False,
                'difference': 0.0,
                'has_loss': False,
                'loss_amount': 0.0,
                'loss_rate': 0.0,
            }
        difference = invoice_total - field_value
        loss_amount = difference if difference > 0 else Decimal(0)
        loss_rate = float(loss_amount / field_value * 100) if loss_amount > 0 else 0.0
        return {
            'has_value': True,
            'difference': float(difference),
            'has_loss': loss_amount > 0,
            'loss_amount': float(loss_amount),
            'loss_rate': round(loss_rate, 1),
        }

    @classmethod
    def _evaluate_amounts(cls, amounts: Mapping[str, Decimal]) -> Dict[str, Any]:
        order_total = amounts['order_total']
        advance_payment = amounts['advance_payment']
        payment_request_amount = amounts['payment_request_amount']
        invoice_total = amounts['invoice_total']
        baseline = order_total

        comparisons = {
            'order_total': cls._field_comparison(invoice_total, order_total),
            'advance_payment': cls._field_comparison(invoice_total, advance_payment),
            'payment_request_amount': cls._field_comparison(invoice_total, payment_request_amount),
        }
        primary = comparisons['order_total']

        if invoice_total <= 0 or baseline <= 0:
            return {
                'status': 'incomplete',
                'label': 'داده ناقص',
                'order_total': float(order_total),
                'advance_payment': float(advance_payment),
                'payment_request_amount': float(payment_request_amount),
                'invoice_total': float(invoice_total),
                'comparisons': comparisons,
                'difference': 0.0,
                'loss_amount': 0.0,
                'loss_rate': 0.0,
                'has_loss': False,
            }

        return {
            'status': 'loss' if primary['has_loss'] else 'on_budget',
            'label': 'ضرر مالی' if primary['has_loss'] else 'بدون ضرر',
            'order_total': float(order_total),
            'advance_payment': float(advance_payment),
            'payment_request_amount': float(payment_request_amount),
            'invoice_total': float(invoice_total),
            'comparisons': comparisons,
            'difference': primary['difference'],
            'loss_amount': primary['loss_amount'],
            'loss_rate': primary['loss_rate'],
            'has_loss': primary['has_loss'],
        }

    @classmethod
    def evaluate_purchase(cls, purchase) -> Dict[str, Any]:
        return cls._evaluate_amounts(cls._normalized_amounts(purchase))

    @classmethod
    def _report_dedupe_key(cls, row: Mapping) -> str:
        purchase_no = (row.get('purchase_number') or '').strip()
        order_no = (row.get('order_request_number') or '').strip()
        if purchase_no and order_no:
            return f'pair:{purchase_no}:{order_no}'
        return f'row:{row["pk"]}'

    @classmethod
    def _purchase_row(cls, row: Mapping, detail: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'pk': row['pk'],
            'purchase_number': row['purchase_number'],
            'order_request_number': (row.get('order_request_number') or '').strip() or '—',
            'product_title': (row.get('product_title') or '')[:80],
            'product_code': row.get('product_code') or '',
            'expert_name': row.get('expert_name') or '—',
            'product_category': row.get('product_category') or '—',
            'purchase_date': row.get('purchase_date') or '—',
            **detail,
        }

    @classmethod
    def _empty_bucket(cls, name: str) -> Dict[str, Any]:
        return {'name': name, 'evaluated': 0, 'with_loss': 0, 'rate': 0.0}

    @classmethod
    def _finalize_buckets(cls, buckets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for data in buckets.values():
            evaluated = data['evaluated']
            with_loss = data['with_loss']
            results.append({
                'name': data['name'],
                'evaluated': evaluated,
                'with_loss': with_loss,
                'rate': round(with_loss / evaluated * 100, 1) if evaluated else 0.0,
            })
        results.sort(key=lambda row: (-row['with_loss'], -row['rate'], row['name']))
        return results

    @classmethod
    def _order_category_stats(cls, category_buckets: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        from accounts.models import ProductCategory

        ordered: List[Dict[str, Any]] = []
        leftovers = dict(category_buckets)

        for category in ProductCategory.objects.filter(is_active=True).order_by('sort_order', 'name'):
            bucket = leftovers.pop(category.name, None)
            ordered.append(bucket if bucket else cls._empty_bucket(category.name))

        ordered.extend(cls._finalize_buckets(leftovers))
        return ordered

    @classmethod
    def build_report(cls, base_queryset=None) -> Dict[str, Any]:
        """یک‌بار خواندن داده — ساخت همه بخش‌های گزارش ضرر مالی"""
        if base_queryset is None:
            from purchases.models import Purchase
            base_queryset = Purchase.objects.all()

        queryset = cls._evaluable_queryset(base_queryset).order_by('purchase_number', 'pk')

        evaluated = 0
        with_loss_count = 0
        on_budget = 0
        under_budget = 0
        loss_rates: List[float] = []

        category_buckets: Dict[str, Dict[str, Any]] = {}
        expert_buckets: Dict[str, Dict[str, Any]] = {}
        loss_cases: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()

        for row in queryset.values(*cls.EVAL_FIELDS).iterator(chunk_size=cls.ITERATOR_CHUNK_SIZE):
            dedupe_key = cls._report_dedupe_key(row)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            amounts = cls._normalize_amounts_from_row(row)
            if amounts['invoice_total'] <= 0 or amounts['order_total'] <= 0:
                continue

            detail = cls._evaluate_amounts(amounts)
            evaluated += 1

            if detail['has_loss']:
                with_loss_count += 1
                loss_rates.append(detail['loss_rate'])
                loss_cases.append(cls._purchase_row(row, detail))
            elif detail['difference'] < 0:
                under_budget += 1
            else:
                on_budget += 1

            category_name = (row.get('product_category') or '').strip() or '—'
            category_bucket = category_buckets.setdefault(
                category_name,
                {'name': category_name, 'evaluated': 0, 'with_loss': 0},
            )
            category_bucket['evaluated'] += 1
            if detail['has_loss']:
                category_bucket['with_loss'] += 1

            expert_name = (row.get('expert_name') or '').strip() or '—'
            expert_bucket = expert_buckets.setdefault(
                expert_name,
                {'name': expert_name, 'evaluated': 0, 'with_loss': 0},
            )
            expert_bucket['evaluated'] += 1
            if detail['has_loss']:
                expert_bucket['with_loss'] += 1

        loss_cases.sort(
            key=lambda item: (-item['loss_amount'], -item['loss_rate'], item['purchase_number'])
        )

        avg_loss_rate = round(sum(loss_rates) / len(loss_rates), 1) if loss_rates else 0.0
        overall = {
            'evaluated': evaluated,
            'with_loss': with_loss_count,
            'on_budget': on_budget,
            'under_budget': under_budget,
            'loss_rate': round(with_loss_count / evaluated * 100, 1) if evaluated else 0.0,
            'avg_loss_rate': avg_loss_rate,
        }

        return {
            'overall': overall,
            'category_stats': cls._order_category_stats(category_buckets),
            'expert_stats': cls._finalize_buckets(expert_buckets),
            'loss_cases': loss_cases,
            'loss_total': len(loss_cases),
        }

    @classmethod
    def get_overall_summary(cls, base_queryset=None) -> Dict[str, Any]:
        return cls.build_report(base_queryset)['overall']

    @classmethod
    def get_loss_cases(cls, base_queryset=None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cases = cls.build_report(base_queryset)['loss_cases']
        if limit is not None:
            return cases[:limit]
        return cases

    @classmethod
    def _aggregate_bucket(cls, base_queryset, group_field: str) -> List[Dict[str, Any]]:
        key = 'category_stats' if group_field == 'product_category' else 'expert_stats'
        return cls.build_report(base_queryset)[key]

    @classmethod
    def get_summary_by_category(cls, base_queryset=None) -> List[Dict[str, Any]]:
        return cls.build_report(base_queryset)['category_stats']

    @classmethod
    def get_summary_by_expert(cls, base_queryset=None) -> List[Dict[str, Any]]:
        return cls.build_report(base_queryset)['expert_stats']