from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Order(models.Model):
    """مدل دستور خرید و گردش کار آن"""

    class Stage(models.TextChoices):
        ORDER_ISSUED = 'order_issued', _('صدور دستور')
        ORDER_PLACED = 'order_placed', _('ثبت سفارش')
        PAYMENT = 'payment', _('پرداخت')
        DELIVERED = 'delivered', _('تحویل شده')

    # اطلاعات اصلی
    order_number = models.CharField(
        max_length=50, unique=True, db_index=True, verbose_name=_('شماره دستور')
    )
    inquiry = models.ForeignKey(
        'inquiries.Inquiry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name=_('استعلام مرتبط')
    )
    purchase = models.ForeignKey(
        'purchases.Purchase', on_delete=models.CASCADE,
        related_name='orders', verbose_name=_('درخواست خرید')
    )

    # مشخصات کالا (Snapshot در زمان صدور)
    product_title = models.CharField(max_length=255, verbose_name=_('عنوان کالا'))
    product_code = models.CharField(max_length=50, blank=True, verbose_name=_('کد کالا'))
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('تعداد'))
    unit = models.CharField(max_length=50, blank=True, verbose_name=_('واحد'))
    unit_price = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name=_('فی واحد'))
    total_price = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name=_('جمع کل'))

    # اطلاعات طرف حساب
    contractor = models.CharField(max_length=200, blank=True, verbose_name=_('تامین کننده / پیمانکار'))
    warehouse = models.CharField(max_length=100, blank=True, verbose_name=_('انبار مقصد'))
    expert_name = models.CharField(max_length=100, blank=True, verbose_name=_('کارشناس مسئول'))

    # وضعیت و مرحله
    stage = models.CharField(
        max_length=20, choices=Stage.choices, default=Stage.ORDER_ISSUED,
        db_index=True, verbose_name=_('مرحله فعلی')
    )
    status = models.CharField(max_length=50, default='جاری', verbose_name=_('وضعیت'))

    # تاریخ‌های مراحل
    order_date = models.CharField(max_length=20, verbose_name=_('تاریخ صدور دستور'))
    order_request_date = models.CharField(max_length=20, blank=True, verbose_name=_('تاریخ ثبت سفارش'))
    order_request_number = models.CharField(max_length=50, blank=True, verbose_name=_('شماره سفارش'))
    payment_date = models.CharField(max_length=20, blank=True, verbose_name=_('تاریخ پرداخت'))
    payment_number = models.CharField(max_length=50, blank=True, verbose_name=_('شماره پرداخت'))
    delivery_date = models.CharField(max_length=20, blank=True, verbose_name=_('تاریخ تحویل'))
    delivery_number = models.CharField(max_length=50, blank=True, verbose_name=_('شماره تحویل / مجوز ورود'))

    # توضیحات
    description = models.TextField(blank=True, verbose_name=_('توضیحات'))

    # متادیتا
    issued_by = models.CharField(max_length=100, blank=True, verbose_name=_('صادر کننده'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_orders'
    )

    class Meta:
        verbose_name = _('دستور خرید')
        verbose_name_plural = _('دستورات خرید')
        db_table = 'orders'
        ordering = ['-order_number']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['stage']),
            models.Index(fields=['purchase']),
            models.Index(fields=['contractor']),
        ]

    def __str__(self):
        return f"{self.order_number} - {self.product_title[:30]}"

    @property
    def is_completed(self):
        return self.stage == self.Stage.DELIVERED

    @staticmethod
    def get_next_order_number():
        from django.db.models import Max
        max_num = Order.objects.aggregate(Max('order_number'))['order_number__max']
        if not max_num:
            return '7001'
        try:
            return str(int(max_num) + 1)
        except (ValueError, TypeError):
            import time
            return f"7{int(time.time()) % 10000}"