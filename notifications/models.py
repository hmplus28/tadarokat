from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """مدل اعلان‌های سیستم"""

    class Type(models.TextChoices):
        INFO = 'info', _('اطلاعیه')
        SUCCESS = 'success', _('موفقیت')
        WARNING = 'warning', _('هشدار')
        INQUIRY = 'inquiry', _('استعلام جدید')
        ORDER = 'order', _('دستور خرید')
        DELIVERY = 'delivery', _('تحویل کالا')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name=_('کاربر')
    )
    title = models.CharField(max_length=200, verbose_name=_('عنوان'))
    message = models.TextField(verbose_name=_('پیام'))
    type = models.CharField(
        max_length=20, choices=Type.choices, default=Type.INFO, verbose_name=_('نوع')
    )
    reference_url = models.CharField(
        max_length=500, blank=True, verbose_name=_('لینک مرجع')
    )
    is_read = models.BooleanField(default=False, verbose_name=_('خوانده شده'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('تاریخ ایجاد'))

    class Meta:
        verbose_name = _('اعلان')
        verbose_name_plural = _('اعلان‌ها')
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} -> {self.user.username}"