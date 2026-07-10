from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings


# ============================================================================
# توابع کمکی برای تشخیص مقادیر معتبر (Module-level)
# ============================================================================

IGNORE_PHRASES = [
    'در انتظار تکمیل روند خرید',
    'در انتظار ثبت',
    'در حال بررسی',
    'فاقد دستور',
    'خرید کارپردازی و فاقد دستور',
    'فاکتورثبت نشده است',
    'فاکتور ثبت نشده است',
    'تکمیل روند',
    'ثبت نشده',
    'نامشخص',
]

IGNORE_EXACT = {
    'nan', 'none', 'null', '-', '—', '0',
    '#n/a', '#n/a!', '#value!', '#ref!', '#div/0!', '#name?',
}

STOPPED_ORDER_PHRASES = (
    'متوقف شده',
    'متوقف',
    'لغو شده',
    'لغو',
    'کنسل',
    'cancel',
    'stopped',
)


def is_order_stopped_status(val) -> bool:
    """آیا وضعیت سفارش (ستون اکسل) به‌معنی توقف/لغو است؟"""
    if is_empty_value(val):
        return False
    text = str(val).strip().lower()
    for phrase in STOPPED_ORDER_PHRASES:
        if phrase.lower() in text:
            return True
    return False


def is_empty_value(val) -> bool:
    """
    بررسی می‌کند آیا مقدار خالی یا نامعتبر است.
    شامل مقادیر Excel مثل #N/A و عبارات فارسی "در انتظار..."
    """
    if val is None:
        return True
    
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return True
        
        # چک کردن مقادیر دقیق Excel
        if val.lower() in IGNORE_EXACT:
            return True
        
        # چک کردن عبارات فارسی "در انتظار..."
        for phrase in IGNORE_PHRASES:
            if phrase in val:
                return True
        
        return False
    
    # برای مقادیر عددی
    try:
        return float(val) == 0
    except (TypeError, ValueError):
        return False


def is_valid_value(val) -> bool:
    """مقدار واقعاً معتبر است (نقطه مقابل is_empty_value)"""
    return not is_empty_value(val)


def is_tankhah(val) -> bool:
    """تشخیص پرداخت تنخواه"""
    if val is None:
        return False
    if isinstance(val, str):
        val_lower = val.lower()
        return 'تنخواه' in val or 'tankhah' in val_lower
    return False


def is_real_date(val) -> bool:
    """
    بررسی می‌کند آیا مقدار واقعاً یک تاریخ است (نه متن "در انتظار...")
    تاریخ‌های شمسی معمولاً شامل / هستند مثل 1405/3/16
    """
    if is_empty_value(val):
        return False
    
    val_str = str(val).strip()
    
    # چک کردن فرمت تاریخ شمسی یا میلادی
    if '/' in val_str or '-' in val_str:
        parts = val_str.replace('-', '/').split('/')
        if len(parts) >= 2:
            try:
                # چک کنیم بخش‌ها عدد هستند
                numeric_parts = 0
                for part in parts[:3]:
                    if part.strip().isdigit():
                        numeric_parts += 1
                return numeric_parts >= 2
            except:
                return False
    
    return False


# ============================================================================
# مدل Purchase
# ============================================================================

class Purchase(models.Model):
    """مدل درخواست خرید - متناظر با هر ردیف اکسل"""
    
    class CurrentStatus(models.TextChoices):
        WAITING_INQUIRY = 'waiting_inquiry', _('در انتظار استعلام')
        INQUIRY_ISSUED = 'inquiry_issued', _('استعلام صادر شده')
        ORDER_ISSUED = 'order_issued', _('دستور خرید صادر شده')
        ORDER_PLACED = 'order_placed', _('سفارش صادر شده')
        ORDER_STOPPED = 'order_stopped', _('سفارش متوقف شده')
        WAITING_PAYMENT = 'waiting_payment', _('در انتظار پرداخت')
        PAID = 'paid', _('پرداخت شده')
        DELIVERED = 'delivered', _('تحویل شده')

    CURRENT_STATUS_LABELS = {
        'waiting_inquiry': 'در انتظار استعلام',
        'inquiry_issued': 'استعلام صادر شده',
        'order_issued': 'دستور خرید صادر شده',
        'order_placed': 'سفارش صادر شده',
        'order_stopped': 'سفارش متوقف شده',
        'waiting_payment': 'در انتظار پرداخت',
        'paid': 'پرداخت شده',
        'delivered': 'تحویل شده',
    }

    @classmethod
    def get_status_label(cls, code: str) -> str:
        if not code:
            return '—'
        return cls.CURRENT_STATUS_LABELS.get(str(code), str(code))

    @property
    def current_status_fa(self) -> str:
        return self.get_status_label(self.current_status)

    @property
    def is_order_stopped(self) -> bool:
        """سفارش متوقف/لغو شده و هنوز به پرداخت یا تحویل نرسیده"""
        if not is_valid_value(self.order_request_number):
            return False
        if not is_order_stopped_status(self.order_request_status):
            return False
        if is_valid_value(self.delivery_number) or is_real_date(self.delivery_date):
            return False
        if is_real_date(self.payment_completion_date):
            return False
        if is_tankhah(self.payment_request_number) or is_tankhah(self.payment_registration_date):
            return False
        if is_valid_value(self.payment_request_number):
            return False
        try:
            if self.payment_request_amount and float(self.payment_request_amount) > 0:
                return False
        except (TypeError, ValueError):
            pass
        return True

    @property
    def display_status(self) -> str:
        """وضعیت نمایشی درخواست — اولویت با توقف سفارش فعال"""
        if self.is_order_stopped:
            return (self.order_request_status or 'متوقف شده').strip()
        return (self.status or '').strip()
    
    # ============================================
    # اطلاعات اولیه
    # ============================================
    purchase_number = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name=_('شماره درخواست خرید')
    )
    line_number = models.IntegerField(
        default=1,
        verbose_name=_('شماره خط در اکسل'),
        help_text=_('شماره ردیف در فایل اکسل')
    )
    base_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('شماره درخواست کالا')
    )
    request_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ درخواست کالا')
    )
    purchase_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ درخواست')
    )
    supply_unit = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('واحد تامین')
    )
    requester = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('درخواست کننده')
    )
    product_category = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name=_('گروه بندی کالایی'),
    )
    deadline_deviated = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_('انحراف از مهلت'),
        help_text=_('بر اساس تاریخ درخواست (ستون D) و قانون گروه کالایی'),
    )
    order_deadline_deviated = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_('انحراف از مهلت سفارش'),
        help_text=_('بر اساس مهلت (ستون O) و تاریخ سفارش (ستون AB)'),
    )
    payment_lead_deviated = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name=_('انحراف لید تایم پرداخت'),
        help_text=_('از ثبت واریزی (AP) تا انجام واریزی (AQ) — بر اساس گروه کالایی'),
    )
    
    # ============================================
    # اطلاعات کالا
    # ============================================
    product_code = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('کد قلم خریدنی')
    )
    product_title = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('نام قلم خریدنی')
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('واحد سنجش')
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('مقدار درخواست')
    )
    
    # ============================================
    # اطلاعات کارشناس
    # ============================================
    expert_name = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        verbose_name=_('نام کارشناس خرید')
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('توضیحات درخواست خرید')
    )
    
    # ============================================
    # وضعیت و تاریخ‌ها
    # ============================================
    status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('وضعیت درخواست خرید')
    )
    required_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ نیاز درخواست خرید')
    )
    inquiry_deadline = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('مهلت استعلام')
    )
    inquiry_deadline_2 = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('مهلت استعلام 2')
    )
    
    # ============================================
    # استعلام
    # ============================================
    inquiry_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('شماره استعلام')
    )
    inquiry_received_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ دریافت درخواست')
    )
    purchase_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('روند خرید')
    )
    
    # ============================================
    # پیش فاکتور
    # ============================================
    preinvoice_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('شماره پیش فاکتور')
    )
    preinvoice_price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('فی پیش فاکتور')
    )
    preinvoice_total = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('جمع پیش فاکتور بدون ارزش افزوده')
    )
    
    # ============================================
    # دستور خرید
    # ============================================
    order_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('شماره دستور خرید')
    )
    order_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ دستور خرید')
    )
    
    # ============================================
    # سفارش
    # ============================================
    order_request_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('شماره سفارش')
    )
    order_request_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('وضعیت سفارش')
    )
    order_request_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ سفارش')
    )
    order_total = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('جمع کل سفارش')
    )
    advance_payment = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('مبلغ پیش پرداخت')
    )
    deductions = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('کسور')
    )
    
    # ============================================
    # تحویل
    # ============================================
    delivered_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_('مقدار تحویل')
    )
    delivery_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_('شماره تحویل')
    )
    delivery_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ تحویل')
    )
    
    # ============================================
    # تامین کننده و فاکتور
    # ============================================
    supplier = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('تامین کننده')
    )
    invoice_price = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('فی فاکتور')
    )
    invoice_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('شماره فاکتور')
    )
    invoice_total = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('جمع کل فاکتور')
    )
    
    # ============================================
    # پرداخت
    # ============================================
    payment_request_amount = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        verbose_name=_('مبلغ درخواست پرداخت')
    )
    payment_request_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('شماره درخواست پرداخت')
    )
    payment_registration_date = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('تاریخ ثبت واریزی')
    )
    payment_completion_date = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تاریخ انجام واریزی')
    )
    
    # ============================================
    # وضعیت محاسبه شده
    # ============================================
    current_status = models.CharField(
        max_length=50,
        choices=CurrentStatus.choices,
        default=CurrentStatus.WAITING_INQUIRY,
        db_index=True,
        verbose_name=_('وضعیت فعلی خرید')
    )
    
    # ============================================
    # متادیتا
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('وارد کننده')
    )
    
    class Meta:
        verbose_name = _('درخواست خرید')
        verbose_name_plural = _('درخواست‌های خرید')
        db_table = 'purchases'
        ordering = ['-purchase_number', 'line_number']
        constraints = [
            models.UniqueConstraint(
                fields=['purchase_number', 'line_number'],
                name='unique_purchase_line'
            )
        ]
        indexes = [
            models.Index(fields=['purchase_number', 'current_status']),
            models.Index(fields=['expert_name', 'status']),
            models.Index(fields=['product_code']),
            models.Index(fields=['inquiry_number']),
            models.Index(fields=['order_number']),
            models.Index(fields=['delivery_number']),
        ]

    def __str__(self):
        return f"{self.purchase_number} - {self.product_title[:50] if self.product_title else 'بدون عنوان'}"
    
    def save(self, *args, **kwargs):
        """محاسبه خودکار current_status قبل از ذخیره"""
        self.current_status = self.calculate_current_status()
        super().save(*args, **kwargs)
    
    def calculate_current_status(self) -> str:
        """
        محاسبه وضعیت فعلی بر اساس ستون‌های پر شده.
        نسخه نهایی با استفاده از توابع کمکی ماژولار
        """
        # 1. تحویل شده - بالاترین اولویت
        if is_valid_value(self.delivery_number) or is_real_date(self.delivery_date):
            return self.CurrentStatus.DELIVERED
        
        try:
            if self.delivered_quantity and float(self.delivered_quantity) > 0:
                return self.CurrentStatus.DELIVERED
        except (TypeError, ValueError):
            pass
        
        # 2. پرداخت شده
        # الف) تاریخ انجام واریزی واقعی
        if is_real_date(self.payment_completion_date):
            return self.CurrentStatus.PAID
        
        # ب) تنخواه
        if is_tankhah(self.payment_request_number) or is_tankhah(self.payment_registration_date):
            return self.CurrentStatus.PAID
        
        # 3. در انتظار پرداخت (شماره/مبلغ درخواست بدون تاریخ انجام واریزی)
        if is_valid_value(self.payment_request_number):
            return self.CurrentStatus.WAITING_PAYMENT
        
        try:
            if self.payment_request_amount and float(self.payment_request_amount) > 0:
                return self.CurrentStatus.WAITING_PAYMENT
        except (TypeError, ValueError):
            pass
        
        # 4. سفارش متوقف / لغو شده (قبل از «سفارش صادر شده»)
        if self.is_order_stopped:
            return self.CurrentStatus.ORDER_STOPPED

        # 5. سفارش صادر شده
        if is_valid_value(self.order_request_number):
            return self.CurrentStatus.ORDER_PLACED
        
        # 6. دستور خرید صادر شده
        if is_valid_value(self.order_number):
            return self.CurrentStatus.ORDER_ISSUED
        
        # 7. استعلام صادر شده
        if is_valid_value(self.inquiry_number):
            return self.CurrentStatus.INQUIRY_ISSUED
        
        # 8. در انتظار استعلام (پیش‌فرض)
        return self.CurrentStatus.WAITING_INQUIRY

    WORKFLOW_DISPLAY_FIELDS = [
        'inquiry_number', 'inquiry_received_date', 'inquiry_deadline', 'inquiry_deadline_2',
        'preinvoice_number', 'order_number', 'order_date',
        'order_request_number', 'order_request_status', 'order_request_date',
        'delivery_number', 'delivery_date', 'supplier',
        'invoice_number', 'payment_request_number', 'payment_registration_date',
        'payment_completion_date',
    ]

    @property
    def has_placeholder_workflow_fields(self) -> bool:
        """آیا فیلدی با متن placeholder اکسل (مثل «در انتظار تکمیل...») وجود دارد؟"""
        for field_name in self.WORKFLOW_DISPLAY_FIELDS:
            val = getattr(self, field_name, None)
            if val is None:
                continue
            if isinstance(val, str) and val.strip() and is_empty_value(val):
                return True
        return False

    @property
    def can_issue_inquiry(self) -> bool:
        """آیا می‌توان برای این خرید استعلام صادر کرد؟"""
        # اگر تحویل شده، نمی‌توان
        if is_valid_value(self.delivery_number) or is_real_date(self.delivery_date):
            return False
        
        # اگر پرداخت شده (هر نوع)، نمی‌توان
        if is_real_date(self.payment_completion_date):
            return False
        if is_tankhah(self.payment_request_number) or is_tankhah(self.payment_registration_date):
            return False
        if is_valid_value(self.payment_request_number):
            return False
        try:
            if self.payment_request_amount and float(self.payment_request_amount) > 0:
                return False
        except (TypeError, ValueError):
            pass
        
        # اگر سفارش دارد، نمی‌توان
        if is_valid_value(self.order_request_number):
            return False
        
        # اگر دستور خرید دارد، نمی‌توان
        if is_valid_value(self.order_number):
            return False
        
        # اگر استعلام صادر شده (از اکسل یا سیستم)، دیگر نمی‌توان استعلام جدید صادر کرد
        if is_valid_value(self.inquiry_number):
            return False

        return True

    @property
    def can_issue_order(self) -> bool:
        """آیا مدیر تدارکات می‌تواند دستور خرید صادر کند؟"""
        if is_valid_value(self.delivery_number) or is_real_date(self.delivery_date):
            return False
        if is_valid_value(self.order_number):
            return False
        if not is_valid_value(self.inquiry_number):
            return False
        return True