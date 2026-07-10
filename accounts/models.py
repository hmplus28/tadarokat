from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class Warehouse(models.Model):
    """انبار مقصد — هر انبار می‌تواند چند کاربر انباردار داشته باشد"""

    name = models.CharField(max_length=100, unique=True, verbose_name=_('نام انبار'))
    is_active = models.BooleanField(default=True, verbose_name=_('فعال'))
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name=_('ترتیب نمایش'))

    class Meta:
        verbose_name = _('انبار')
        verbose_name_plural = _('انبارها')
        db_table = 'warehouses'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @classmethod
    def get_active_choices(cls):
        return cls.objects.filter(is_active=True).order_by('sort_order', 'name')


class ProductCategory(models.Model):
    """گروه‌بندی کالایی — برای صدور استعلام و گزارش‌ها"""

    name = models.CharField(max_length=100, unique=True, verbose_name=_('نام گروه'))
    is_active = models.BooleanField(default=True, verbose_name=_('فعال'))
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name=_('ترتیب نمایش'))
    code_prefixes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('پیشوند کد کالا'),
        help_text=_('پیشوند کد قلم خریدنی — با کاما جدا شود. برای تخصیص خودکار گروه'),
    )
    payment_lead_days = models.PositiveSmallIntegerField(
        default=7,
        verbose_name=_('لید تایم پرداخت (روز)'),
        help_text=_('حداکثر روز مجاز از ثبت واریزی (AP) تا انجام واریزی (AQ)'),
    )

    class Meta:
        verbose_name = _('گروه کالایی')
        verbose_name_plural = _('گروه‌های کالایی')
        db_table = 'product_categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @classmethod
    def get_active_choices(cls):
        return cls.objects.filter(is_active=True).order_by('sort_order', 'name')


class CategoryDeadlineRule(models.Model):
    """قوانین مهلت ثبت درخواست — ترکیب دلخواه روز ماه + روز هفته — ملاک: تاریخ درخواست (ستون D)"""

    JALALI_WEEKDAY_CHOICES = [
        (0, _('شنبه')),
        (1, _('یکشنبه')),
        (2, _('دوشنبه')),
        (3, _('سه‌شنبه')),
        (4, _('چهارشنبه')),
        (5, _('پنج‌شنبه')),
        (6, _('جمعه')),
    ]

    class RuleType(models.TextChoices):
        MONTH_DAYS = 'month_days', _('روزهای مشخص ماه')
        WEEK_STARTS = 'week_starts', _('شنبه ابتدای هر هفته')  # legacy — از allowed_weekdays استفاده کنید

    category = models.OneToOneField(
        ProductCategory,
        on_delete=models.CASCADE,
        related_name='deadline_rule',
        verbose_name=_('گروه کالایی'),
    )
    rule_type = models.CharField(
        max_length=20,
        choices=RuleType.choices,
        default=RuleType.MONTH_DAYS,
        verbose_name=_('نوع قانون'),
    )
    allowed_days = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('روزهای مجاز ماه'),
        help_text=_('مثلاً: 5,25 یا 10,25'),
    )
    allowed_weekdays = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_('روزهای هفته مجاز'),
        help_text=_('0=شنبه، 1=یکشنبه، ... 6=جمعه — با کاما'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('فعال'))
    notes = models.CharField(max_length=200, blank=True, verbose_name=_('توضیح'))

    class Meta:
        verbose_name = _('قانون مهلت گروه کالایی')
        verbose_name_plural = _('قوانین مهلت گروه‌های کالایی')
        db_table = 'category_deadline_rules'

    def __str__(self):
        return f'{self.category.name} — {self.describe_rule()}'

    def get_month_day_list(self):
        if not self.allowed_days.strip():
            return []
        days = []
        for part in self.allowed_days.split(','):
            part = part.strip()
            if part.isdigit():
                day = int(part)
                if 1 <= day <= 31:
                    days.append(day)
        return sorted(set(days))

    def get_weekday_index_list(self) -> list:
        raw = (self.allowed_weekdays or '').strip()
        if not raw and self.rule_type == self.RuleType.WEEK_STARTS:
            return [0]
        indices = []
        for part in raw.split(','):
            part = part.strip()
            if part.isdigit():
                idx = int(part)
                if 0 <= idx <= 6:
                    indices.append(idx)
        return sorted(set(indices))

    @classmethod
    def weekday_label(cls, index: int) -> str:
        for i, label in cls.JALALI_WEEKDAY_CHOICES:
            if i == index:
                return str(label)
        return str(index)

    def compute_allowed_days_in_month(self, year: int, month: int) -> list:
        """اجتماع روزهای مشخص ماه + روزهای هفته انتخاب‌شده در همان ماه"""
        days = set(self.get_month_day_list())
        weekday_indices = self.get_weekday_index_list()
        if not weekday_indices:
            return sorted(days)

        try:
            import jdatetime
        except ImportError:
            return sorted(days)

        for day in range(1, 32):
            try:
                d = jdatetime.date(year, month, day)
            except ValueError:
                break
            if d.weekday() in weekday_indices:
                days.add(day)
        return sorted(days)

    def get_allowed_day_list(self, year: int = None, month: int = None):
        if year and month:
            return self.compute_allowed_days_in_month(year, month)
        return self.get_month_day_list()

    def describe_rule(self):
        parts = []
        if self.allowed_days.strip():
            parts.append(f'روزهای {self.allowed_days} ماه')
        weekday_indices = self.get_weekday_index_list()
        if weekday_indices:
            names = '، '.join(self.weekday_label(i) for i in weekday_indices)
            parts.append(f'{names} هر هفته')
        return ' + '.join(parts) if parts else 'تعریف نشده'


class UserManager(BaseUserManager):
    """مدیر سفارشی برای User"""
    
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError(_('نام کاربری الزامی است'))
        email = self.normalize_email(email) if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'superuser')  # 👈 تغییر به superuser

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    مدل کاربر سفارشی با سلسله مراتب نقش‌ها:
    - superuser: دسترسی کامل به همه چیز
    - admin: مدیر تدارکات (گزارش‌گیری و نظارت)
    - expert: کارشناس تدارکات (صدور استعلام و پیگیری)
    - warehouse: انباردار (ثبت تحویل)
    - requester: درخواست‌دهنده (پیگیری گردش کار واحد خود)
    """

    class RequesterScope(models.TextChoices):
        IT = 'it', _('آی‌تی')
        ABNIEH = 'abnieh', _('ابنیه و عمران')
        TOLID = 'tolid', _('تولید و نت')
    
    class Role(models.TextChoices):
        SUPERUSER = 'superuser', _('سوپر یوزر')
        ADMIN = 'admin', _('مدیر تدارکات')
        EXPERT = 'expert', _('کارشناس تدارکات')
        WAREHOUSE = 'warehouse', _('انباردار')
        REQUESTER = 'requester', _('درخواست‌دهنده')
    
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EXPERT,
        verbose_name=_('نقش'),
        db_index=True
    )
    expert_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('نام کارشناس'),
        help_text=_('فقط برای نقش کارشناس - نامی که در گزارش‌ها نمایش داده می‌شود')
    )
    assigned_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('انبار مسئول'),
        help_text=_('فقط برای نقش انباردار'),
    )
    requester_scope = models.CharField(
        max_length=20,
        choices=RequesterScope.choices,
        blank=True,
        default='',
        verbose_name=_('حوزه درخواست‌دهنده'),
        help_text=_('فقط برای نقش درخواست‌دهنده — تعیین واحد/گروه قابل مشاهده'),
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('تلفن')
    )
    national_id = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('کد ملی')
    )

    objects = UserManager()

    class Meta:
        verbose_name = _('کاربر')
        verbose_name_plural = _('کاربران')
        db_table = 'users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    # ============================================
    # Property های بررسی نقش با سلسله مراتب
    # ============================================
    
    @property
    def is_superuser_role(self):
        """آیا سوپر یوزر است؟"""
        return self.role == self.Role.SUPERUSER or self.is_superuser
    
    @property
    def is_admin_role(self):
        """آیا مدیر تدارکات یا بالاتر است؟"""
        return self.role in [self.Role.SUPERUSER, self.Role.ADMIN] or self.is_superuser
    
    @property
    def is_expert_role(self):
        """آیا کارشناس یا بالاتر است؟"""
        return self.role in [self.Role.SUPERUSER, self.Role.ADMIN, self.Role.EXPERT] or self.is_superuser
    
    @property
    def is_warehouse_role(self):
        """آیا انباردار است؟"""
        return self.role == self.Role.WAREHOUSE

    @property
    def is_requester_role(self):
        """آیا درخواست‌دهنده است؟"""
        return self.role == self.Role.REQUESTER
    
    # ============================================
    # Property های دسترسی (Permissions)
    # ============================================
    
    @property
    def can_issue_inquiry(self):
        """می‌تواند استعلام صادر کند؟"""
        return self.is_expert_role
    
    @property
    def can_create_order(self):
        """می‌تواند دستور خرید صادر کند؟"""
        return self.is_admin_role
    
    @property
    def can_register_delivery(self):
        """می‌تواند تحویل ثبت کند؟"""
        return self.is_warehouse_role or self.is_superuser_role
    
    @property
    def can_view_reports(self):
        """می‌تواند گزارش‌ها را ببیند؟"""
        return self.is_admin_role
    
    @property
    def can_view_audit_log(self):
        """می‌تواند تاریخچه تغییرات را ببیند؟"""
        return self.is_superuser_role
    
    @property
    def can_edit_all_fields(self):
        """می‌تواند همه فیلدها را ویرایش کند؟"""
        return self.is_superuser_role
    
    @property
    def can_manage_users(self):
        """می‌تواند کاربران را مدیریت کند؟"""
        return self.is_superuser_role
    
    @property
    def can_sync_excel(self):
        """می‌تواند اکسل sync کند؟"""
        return self.is_admin_role
    
    # ============================================
    # متدهای کمکی
    # ============================================
    
    def has_role_or_higher(self, target_role):
        """بررسی اینکه آیا کاربر نقش مشخص یا بالاتر دارد"""
        hierarchy = {
            self.Role.REQUESTER: 1,
            self.Role.WAREHOUSE: 1,
            self.Role.EXPERT: 2,
            self.Role.ADMIN: 3,
            self.Role.SUPERUSER: 4,
        }
        
        if self.is_superuser:
            return True
        
        user_level = hierarchy.get(self.role, 0)
        target_level = hierarchy.get(target_role, 0)
        return user_level >= target_level
    
    def get_display_name(self):
        """نام نمایشی کاربر"""
        if self.get_full_name():
            return self.get_full_name()
        if self.expert_name:
            return self.expert_name
        return self.username

    @property
    def warehouse(self):
        """نام انبار (سازگاری با فیلدهای متنی سایر مدل‌ها)"""
        return self.assigned_warehouse.name if self.assigned_warehouse_id else ''