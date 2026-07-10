from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from purchases.models import Purchase
from inquiries.models import Inquiry
from orders.models import Order
from deliveries.models import Delivery
from .models import AuditLog


# نگاشت مدل‌ها به نام فارسی
ENTITY_NAMES = {
    'Purchase': 'درخواست خرید',
    'Inquiry': 'استعلام',
    'Order': 'دستور خرید',
    'Delivery': 'تحویل',
}

# فیلدهایی که تغییراتشان لاگ شود
TRACKED_FIELDS = {
    'Purchase': ['status', 'current_status', 'expert_name', 'inquiry_number', 'order_number'],
    'Inquiry': ['status', 'purchase_type'],
    'Order': ['stage', 'status', 'contractor', 'delivery_number', 'payment_number'],
    'Delivery': ['status'],
}


def _log_model_change(instance, action, **kwargs):
    """ثبت لاگ برای تغییرات مدل"""
    model_name = instance.__class__.__name__
    entity_name = ENTITY_NAMES.get(model_name, model_name)
    
    # پیدا کردن کاربر از instance (در صورت وجود)
    user = None
    if hasattr(instance, 'created_by') and instance.created_by:
        user = instance.created_by
    
    repr_str = str(instance)[:100]
    
    AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_name,
        entity_id=str(instance.pk),
        entity_repr=repr_str,
    )


@receiver(post_save, sender=Purchase)
def purchase_saved(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    _log_model_change(instance, action)


@receiver(post_save, sender=Inquiry)
def inquiry_saved(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    if created:
        action = AuditLog.Action.ISSUE
    _log_model_change(instance, action)


@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    if created:
        action = AuditLog.Action.ISSUE
    _log_model_change(instance, action)


@receiver(post_save, sender=Delivery)
def delivery_saved(sender, instance, created, **kwargs):
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    _log_model_change(instance, action)