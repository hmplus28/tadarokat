"""گزارش ریالی به تفکیک کالا — جمع کل فاکتور (AJ) یا جمع کل سفارش (AA)"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Dict, List, Set, Tuple

from services.order_amount_service import OrderAmountService


class ProductAmountService:
    GROUP_PREFIX_LEN = 4

    @classmethod
    def get_line_amount(cls, purchase) -> Tuple[Decimal, str]:
        """
        مبلغ هر ردیف (به ازای هر کد کالا):
        - اگر جمع کل فاکتور (ستون AJ / invoice_price) موجود باشد → همان
        - در غیر این صورت → جمع کل سفارش (ستون AA / order_total)
        """
        try:
            invoice_amount = Decimal(purchase.invoice_price or 0)
        except Exception:
            invoice_amount = Decimal(0)
        if invoice_amount > 0:
            return invoice_amount, 'invoice_price'

        try:
            order_amount = Decimal(purchase.order_total or 0)
        except Exception:
            order_amount = Decimal(0)
        if order_amount > 0:
            return order_amount, 'order_total'

        return Decimal(0), 'none'

    @classmethod
    def _product_key(cls, purchase) -> Tuple[str, str]:
        code = (purchase.product_code or '').strip() or '—'
        title = (purchase.product_title or '').strip() or 'بدون عنوان'
        return code, title

    @classmethod
    def _normalize_code(cls, product_code: str) -> str:
        code = str(product_code or '').strip() or '—'
        if code.endswith('.0') and code[:-2].replace('.', '').isdigit():
            code = code[:-2]
        return code

    @classmethod
    def group_prefix(cls, product_code: str) -> str:
        code = cls._normalize_code(product_code)
        digits = re.sub(r'\D', '', code)
        if len(digits) >= cls.GROUP_PREFIX_LEN:
            return digits[:cls.GROUP_PREFIX_LEN]
        return code[:8] if len(code) > 8 else code

    @classmethod
    def build_product_groups(cls, products: List[Dict[str, Any]], grand_total: float) -> List[Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}

        for row in products:
            prefix = cls.group_prefix(row['product_code'])
            if prefix not in groups:
                groups[prefix] = {
                    'prefix': prefix,
                    'amount': 0.0,
                    'invoice_amount': 0.0,
                    'order_amount': 0.0,
                    'line_count': 0,
                    'product_count': 0,
                    'share': 0.0,
                    'items': [],
                }

            group = groups[prefix]
            group['amount'] += row['amount']
            group['invoice_amount'] += row['invoice_amount']
            group['order_amount'] += row['order_amount']
            group['line_count'] += row['line_count']
            group['product_count'] += 1
            group['items'].append(row)

        results = list(groups.values())
        results.sort(key=lambda row: (-row['amount'], row['prefix']))
        for group in results:
            group['share'] = round(group['amount'] / grand_total * 100, 2) if grand_total else 0
            group['items'].sort(key=lambda item: (-item['amount'], item['product_code']))
        return results

    @classmethod
    def get_summary(cls, queryset) -> Dict[str, Any]:
        products: Dict[str, Dict[str, Any]] = {}
        grand_total = Decimal(0)
        invoice_based_total = Decimal(0)
        order_based_total = Decimal(0)
        with_amount = 0
        invoice_lines = 0
        order_lines = 0
        seen_order_totals: Set[str] = set()

        for purchase in queryset.iterator(chunk_size=500):
            amount, source = cls.get_line_amount(purchase)
            if source == 'order_total':
                dedupe_key = OrderAmountService.dedupe_key(purchase)
                if dedupe_key in seen_order_totals:
                    continue
                seen_order_totals.add(dedupe_key)
            if amount <= 0:
                continue

            code, title = cls._product_key(purchase)
            key = cls._normalize_code(code)
            if key not in products:
                products[key] = {
                    'product_code': key,
                    'product_title': title,
                    'amount': Decimal(0),
                    'invoice_amount': Decimal(0),
                    'order_amount': Decimal(0),
                    'line_count': 0,
                    'invoice_lines': 0,
                    'order_lines': 0,
                }

            row = products[key]
            row['amount'] += amount
            row['line_count'] += 1
            if title and title != 'بدون عنوان':
                row['product_title'] = title

            grand_total += amount
            with_amount += 1

            if source == 'invoice_price':
                row['invoice_amount'] += amount
                row['invoice_lines'] += 1
                invoice_based_total += amount
                invoice_lines += 1
            elif source == 'order_total':
                row['order_amount'] += amount
                row['order_lines'] += 1
                order_based_total += amount
                order_lines += 1

        results = []
        for row in products.values():
            amt = float(row['amount'])
            results.append({
                'product_code': row['product_code'],
                'product_title': row['product_title'],
                'amount': amt,
                'invoice_amount': float(row['invoice_amount']),
                'order_amount': float(row['order_amount']),
                'line_count': row['line_count'],
                'invoice_lines': row['invoice_lines'],
                'order_lines': row['order_lines'],
                'share': 0,
            })

        results.sort(key=lambda r: (-r['amount'], r['product_code']))
        gt = float(grand_total)
        for row in results:
            row['share'] = round(row['amount'] / gt * 100, 2) if gt else 0

        product_groups = cls.build_product_groups(results, gt)

        return {
            'grand_total': gt,
            'with_amount': with_amount,
            'product_count': len(results),
            'invoice_based_total': float(invoice_based_total),
            'order_based_total': float(order_based_total),
            'invoice_lines': invoice_lines,
            'order_lines': order_lines,
            'products': results,
            'product_groups': product_groups,
            'group_count': len(product_groups),
        }