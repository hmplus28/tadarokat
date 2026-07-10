"""دسترسی و فیلترهای نقش انباردار"""

WAREHOUSE_ORDER_STAGES = ('payment', 'delivered')
WAREHOUSE_PURCHASE_STATUSES = ('paid', 'delivered')


def is_warehouse_user(user) -> bool:
    return getattr(user, 'is_warehouse_role', False)


def _warehouse_name(user) -> str:
    if user and getattr(user, 'assigned_warehouse_id', None):
        return (user.warehouse or '').strip()
    return ''


def filter_orders_for_warehouse(queryset, user=None):
    qs = queryset.filter(stage__in=WAREHOUSE_ORDER_STAGES)
    wh = _warehouse_name(user)
    if wh:
        qs = qs.filter(warehouse=wh)
    return qs


def filter_purchases_for_warehouse(queryset, user=None):
    qs = queryset.filter(current_status__in=WAREHOUSE_PURCHASE_STATUSES)
    wh = _warehouse_name(user)
    if wh:
        qs = qs.filter(supply_unit=wh)
    return qs


def filter_deliveries_for_warehouse(queryset, user=None):
    wh = _warehouse_name(user)
    if wh:
        queryset = queryset.filter(warehouse=wh)
    return queryset


def warehouse_can_view_order(order, user=None) -> bool:
    if order.stage not in WAREHOUSE_ORDER_STAGES:
        return False
    wh = _warehouse_name(user)
    if wh:
        return (order.warehouse or '') == wh
    return True


def warehouse_can_view_purchase(purchase, user=None) -> bool:
    if purchase.current_status not in WAREHOUSE_PURCHASE_STATUSES:
        return False
    wh = _warehouse_name(user)
    if wh:
        return (purchase.supply_unit or '') == wh
    return True


def warehouse_can_view_delivery(delivery, user=None) -> bool:
    wh = _warehouse_name(user)
    if wh and (delivery.warehouse or '') != wh:
        return False
    return True