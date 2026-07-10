from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Inquiry(models.Model):
    """مدل استعلام صادر شده"""
    
    class Status(models.TextChoices):
        DRAFT = 'draft', _('پیش‌نویس')
        ISSUED = 'issued', _('صادر شده')
        APPROVED = 'approved', _('تایید شده')
        REJECTED = 'rejected', _('رد شده')
        COMPLETED = 'completed', _('تکمیل شده')
    
    # اطلاعات اصلی
    inquiry_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name=_('شماره استعلام')
    )
    purchase = models.ForeignKey(
        'purchases.Purchase',
        on_delete=models.CASCADE,
        related_name='inquiries',
        verbose_name=_('درخواست خرید')
    )
    
    # اطلاعات استعلام
    inquiry_date = models.CharField(max_length=20, verbose_name=_('تاریخ استعلام'))
    deadline = models.CharField(max_length=20, blank=True, verbose_name=_('مهلت استعلام'))
    purchase_type = models.CharField(max_length=50, blank=True, verbose_name=_('نوع خرید'))
    urgency_code = models.CharField(max_length=50, blank=True, verbose_name=_('رمز فوریت'))
    
    # اطلاعات تکمیلی
    supply_unit = models.CharField(max_length=100, blank=True, verbose_name=_('واحد/رمز تامین'))
    reason = models.TextField(blank=True, verbose_name=_('علت خرید'))
    warehouse = models.CharField(max_length=100, blank=True, verbose_name=_('انبار'))
    product_category = models.CharField(max_length=100, blank=True, verbose_name=_('گروه بندی کالایی'))
    warehouse_request_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('شماره درخواست کالا از انبار'),
    )
    warehouse_request_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ ثبت کالا از انبار'),
    )
    requester = models.CharField(max_length=100, blank=True, verbose_name=_('درخواست دهنده'))
    risk_note = models.TextField(blank=True, verbose_name=_('ریسک عدم خرید'))
    
    # کارشناس
    expert_name = models.CharField(max_length=100, blank=True, verbose_name=_('کارشناس خرید'))
    issuer = models.CharField(max_length=100, blank=True, verbose_name=_('صادر کننده سند'))
    
    # وضعیت
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ISSUED,
        db_index=True,
        verbose_name=_('وضعیت')
    )
    
    # متادیتا
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_inquiries',
        verbose_name=_('ایجاد کننده')
    )
    
    class Meta:
        verbose_name = _('استعلام')
        verbose_name_plural = _('استعلام‌ها')
        db_table = 'inquiries'
        ordering = ['-inquiry_number']
        indexes = [
            models.Index(fields=['inquiry_number']),
            models.Index(fields=['purchase']),
            models.Index(fields=['expert_name']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.inquiry_number} - خرید {self.purchase.purchase_number if self.purchase_id else '?'}"
    
    @staticmethod
    def get_next_inquiry_number():
        """تولید شماره استعلام بعدی"""
        from django.db.models import Max
        
        # دریافت بیشترین شماره فعلی
        max_num = Inquiry.objects.aggregate(Max('inquiry_number'))['inquiry_number__max']
        
        if not max_num:
            return '9001'
        
        try:
            # تلاش برای تبدیل به عدد و افزایش
            next_num = int(max_num) + 1
            return str(next_num)
        except (ValueError, TypeError):
            # اگر شماره غیرعددی بود، از timestamp استفاده کن
            import time
            return f"9{int(time.time()) % 10000}"
        

class PreInvoice(models.Model):
    """پیش‌فاکتور پیمانکار"""
    inquiry = models.ForeignKey(
        Inquiry, on_delete=models.CASCADE, 
        related_name='pre_invoices',
        verbose_name=_('استعلام')
    )
    contractor = models.CharField(max_length=200, verbose_name=_('پیمانکار'))
    invoice_number = models.CharField(max_length=100, blank=True, verbose_name=_('شماره پیش‌فاکتور'))
    invoice_date = models.CharField(max_length=20, blank=True, verbose_name=_('تاریخ پیش‌فاکتور'))
    city = models.CharField(max_length=100, blank=True, verbose_name=_('شهر'))
    validity_days = models.IntegerField(default=7, verbose_name=_('اعتبار (روز)'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name=_('درصد مالیات'))
    discount = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name=_('تخفیف'))
    notes = models.TextField(blank=True, verbose_name=_('توضیحات'))
    is_selected = models.BooleanField(default=False, verbose_name=_('انتخاب شده'))
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'pre_invoices'
        verbose_name = _('پیش‌فاکتور')
        verbose_name_plural = _('پیش‌فاکتورها')
    
    def __str__(self):
        return f"{self.contractor} - {self.inquiry.inquiry_number}"
    
    @property
    def subtotal(self):
        return sum(line.total for line in self.lines.all())
    
    @property
    def tax_amount(self):
        return self.subtotal * (self.tax_rate / 100)
    
    @property
    def total(self):
        return self.subtotal + self.tax_amount - self.discount


class PreInvoiceLine(models.Model):
    """قلم پیش‌فاکتور"""
    pre_invoice = models.ForeignKey(
        PreInvoice, on_delete=models.CASCADE,
        related_name='lines',
        verbose_name=_('پیش‌فاکتور')
    )
    row_number = models.IntegerField(default=1, verbose_name=_('ردیف'))
    product_title = models.CharField(max_length=255, verbose_name=_('عنوان کالا'))
    product_code = models.CharField(max_length=50, blank=True, verbose_name=_('کد کالا'))
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('تعداد'))
    unit = models.CharField(max_length=50, blank=True, verbose_name=_('واحد'))
    unit_price = models.DecimalField(max_digits=15, decimal_places=0, verbose_name=_('فی واحد'))
    description = models.TextField(blank=True, verbose_name=_('توضیحات'))
    
    class Meta:
        db_table = 'pre_invoice_lines'
        verbose_name = _('قلم پیش‌فاکتور')
        verbose_name_plural = _('اقلام پیش‌فاکتور')
    
    def __str__(self):
        return f"{self.product_title} × {self.quantity}"
    
    @property
    def total(self):
        return float(self.quantity) * float(self.unit_price)