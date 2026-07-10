"""دسترسی و فیلترهای نقش کارشناس — فقط پرونده‌های خودش"""

from django.db.models import Q


def is_pure_expert_user(user) -> bool:
    """کارشناس خالص (نه مدیر تدارکات)"""
    return getattr(user, 'role', '') == 'expert'


def get_expert_identity(user) -> str:
    """نام کارشناس برای تطبیق با فیلد expert_name در خرید"""
    if not user or not user.is_authenticated:
        return ''
    return (getattr(user, 'expert_name', '') or user.get_display_name() or '').strip()


def build_expert_purchase_q(user) -> Q:
    name = get_expert_identity(user)
    if not name:
        return Q(pk__in=[])
    return Q(expert_name__iexact=name) | Q(expert_name__icontains=name)


def filter_purchases_for_expert(queryset, user=None):
    if not is_pure_expert_user(user):
        return queryset
    return queryset.filter(build_expert_purchase_q(user)).distinct()


def expert_can_view_purchase(purchase, user=None) -> bool:
    if not is_pure_expert_user(user):
        return True
    name = get_expert_identity(user)
    if not name:
        return False
    expert = (purchase.expert_name or '').strip()
    return expert.lower() == name.lower() or name.lower() in expert.lower()


def filter_inquiries_for_expert(queryset, user=None):
    if not is_pure_expert_user(user):
        return queryset
    name = get_expert_identity(user)
    if not name:
        return queryset.none()
    return queryset.filter(
        Q(expert_name__iexact=name)
        | Q(expert_name__icontains=name)
        | Q(purchase__expert_name__iexact=name)
        | Q(purchase__expert_name__icontains=name)
    ).distinct()