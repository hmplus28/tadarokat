from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """لاگ تغییرات سیستم"""

    class Action(models.TextChoices):
        CREATE = 'create', _('ایجاد')
        UPDATE = 'update', _('ویرایش')
        DELETE = 'delete', _('حذف')
        LOGIN = 'login', _('ورود')
        LOGOUT = 'logout', _('خروج')
        EXPORT = 'export', _('خروجی')
        ISSUE = 'issue', _('صدور')
        ADVANCE = 'advance', _('پیشبرد')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name=_('کاربر')
    )
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        verbose_name=_('نوع عملیات')
    )
    entity_type = models.CharField(max_length=50, verbose_name=_('نوع موجودیت'))
    entity_id = models.CharField(max_length=100, blank=True, verbose_name=_('شناسه موجودیت'))
    entity_repr = models.CharField(max_length=255, blank=True, verbose_name=_('نمایش موجودیت'))
    
    field_name = models.CharField(max_length=100, blank=True, verbose_name=_('فیلد'))
    old_value = models.TextField(blank=True, verbose_name=_('مقدار قبلی'))
    new_value = models.TextField(blank=True, verbose_name=_('مقدار جدید'))
    
    description = models.TextField(blank=True, verbose_name=_('توضیحات'))
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_('آدرس IP'))
    user_agent = models.TextField(blank=True, verbose_name=_('User Agent'))
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_('تاریخ'))
    
    class Meta:
        verbose_name = _('لاگ تغییرات')
        verbose_name_plural = _('لاگ‌های تغییرات')
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.entity_repr}"
    
    @classmethod
    def log(cls, user, action, entity_type, entity_id='', entity_repr='', 
            field_name='', old_value='', new_value='', description='', 
            request=None):
        """متد کمکی برای ثبت لاگ"""
        ip = None
        ua = ''
        if request:
            ip = cls._get_client_ip(request)
            ua = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        return cls.objects.create(
            user=user,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            entity_repr=str(entity_repr)[:255],
            field_name=field_name,
            old_value=str(old_value)[:1000] if old_value else '',
            new_value=str(new_value)[:1000] if new_value else '',
            description=description,
            ip_address=ip,
            user_agent=ua,
        )
    
    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')