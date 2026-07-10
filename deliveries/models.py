from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Delivery(models.Model):
    """مدل تحویل کالا و رسید انبار"""

    delivery_number = models.CharField(max_length=50, unique=True, db_index=True, verbose_name=_('شماره تحویل / مجوز ورود'))
    
    # می‌تواند به Order یا مستقیم به Purchase متصل باشد
    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, 
        related_name='deliveries', 
        verbose_name=_('دستور خرید'),
        null=True, blank=True
    )
    purchase = models.ForeignKey(
        'purchases.Purchase', on_delete=models.CASCADE,
        related_name='deliveries',
        verbose_name=_('درخواست خرید'),
        null=True, blank=True
    )
    
    # Snapshot اطلاعات در زمان تحویل
    product_title = models.CharField(max_length=255, verbose_name=_('عنوان کالا'))
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('مقدار تحویلی'))
    unit = models.CharField(max_length=50, blank=True, verbose_name=_('واحد'))
    
    warehouse = models.CharField(max_length=100, blank=True, verbose_name=_('انبار مقصد'))
    receiver = models.CharField(max_length=100, blank=True, verbose_name=_('تحویل گیرنده'))
    delivery_date = models.CharField(max_length=20, verbose_name=_('تاریخ تحویل'))
    
    supplier = models.CharField(max_length=200, blank=True, verbose_name=_('تامین کننده'))
    
    description = models.TextField(blank=True, verbose_name=_('توضیحات انباردار'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name='registered_deliveries'
    )

    class Meta:
        verbose_name = _('تحویل')
        verbose_name_plural = _('تحویل‌ها')
        db_table = 'deliveries'
        ordering = ['-delivery_date', '-pk']

    def __str__(self):
        return f"{self.delivery_number} - {self.product_title[:30]}"