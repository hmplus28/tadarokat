"""دسترسی و فیلترهای نقش درخواست‌دهنده (پیگیری گردش کار واحد خود)"""

from django.db.models import Q

REQUESTER_SCOPES = {
    'it': {
        'label': 'آی‌تی',
        'categories': ['آی تی', 'آیتى', 'ای تی', 'ایتی', 'IT', 'it'],
        'warehouses': ['آی تی', 'ای تی', 'ایتی', 'IT', 'انبار آی تی', 'انبار ایتی'],
    },
    'abnieh': {
        'label': 'ابنیه و عمران',
        'categories': ['ابنیه', 'عمران', 'ابنیه و مصالح', 'ابنیه و عمران'],
        'warehouses': ['ابنیه', 'عمران', 'انبار ابنیه'],
    },
    'tolid': {
        'label': 'تولید و نت',
        'categories': ['عمومی تولید', 'تولید', 'نت و تاسیسات', 'نت', 'تاسیسات'],
        'warehouses': [
            'انبار نت', 'انبار تاسیسات', 'نت', 'تاسیسات', 'تولید', 'انبار تولید',
        ],
    },
}


def is_requester_user(user) -> bool:
    return getattr(user, 'is_requester_role', False)


def get_requester_scope_label(user) -> str:
    scope = getattr(user, 'requester_scope', '') or ''
    cfg = REQUESTER_SCOPES.get(scope)
    return cfg['label'] if cfg else '—'


def _terms_q(field: str, terms: list) -> Q:
    q = Q()
    for term in terms:
        term = (term or '').strip()
        if term:
            q |= Q(**{f'{field}__icontains': term})
    return q


def _scope_terms(scope: str) -> tuple[list, list]:
    cfg = REQUESTER_SCOPES.get(scope, {})
    return list(cfg.get('categories', [])), list(cfg.get('warehouses', []))


def build_purchase_scope_q(scope: str) -> Q:
    """ساخت Q فیلتر پرونده‌های مرتبط با حوزه درخواست‌دهنده"""
    if scope not in REQUESTER_SCOPES:
        return Q(pk__in=[])

    categories, warehouses = _scope_terms(scope)
    all_terms = categories + warehouses

    purchase_q = _terms_q('product_category', categories)
    purchase_q |= _terms_q('supply_unit', warehouses)

    from inquiries.models import Inquiry
    from orders.models import Order
    from deliveries.models import Delivery

    inquiry_q = (
        _terms_q('product_category', categories)
        | _terms_q('warehouse', warehouses)
        | _terms_q('supply_unit', warehouses)
    )
    inquiry_numbers = Inquiry.objects.filter(inquiry_q).values_list('inquiry_number', flat=True)
    inquiry_purchase_ids = Inquiry.objects.filter(inquiry_q).values_list('purchase_id', flat=True)

    purchase_q |= Q(inquiry_number__in=inquiry_numbers)
    purchase_q |= Q(pk__in=inquiry_purchase_ids)

    order_q = _terms_q('warehouse', warehouses)
    order_purchase_ids = Order.objects.filter(order_q).values_list('purchase_id', flat=True)
    purchase_q |= Q(pk__in=order_purchase_ids)

    delivery_q = _terms_q('warehouse', warehouses)
    delivery_purchase_ids = Delivery.objects.filter(delivery_q).exclude(
        purchase_id__isnull=True
    ).values_list('purchase_id', flat=True)
    purchase_q |= Q(pk__in=delivery_purchase_ids)

    if not all_terms:
        return Q(pk__in=[])

    return purchase_q


def filter_purchases_for_requester(queryset, user=None):
    scope = getattr(user, 'requester_scope', '') or ''
    if not scope:
        return queryset.none()
    return queryset.filter(build_purchase_scope_q(scope)).distinct()


def requester_can_view_purchase(purchase, user=None) -> bool:
    if not is_requester_user(user):
        return False
    scope = getattr(user, 'requester_scope', '') or ''
    if not scope:
        return False
    from purchases.models import Purchase
    return Purchase.objects.filter(pk=purchase.pk).filter(
        build_purchase_scope_q(scope)
    ).exists()