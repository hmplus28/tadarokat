from django.db import models

"""سرویس‌های مرتبط با استعلام"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from datetime import datetime
from typing import Dict, Optional, List, TYPE_CHECKING

from purchases.models import Purchase
from inquiries.models import Inquiry

if TYPE_CHECKING:
    from inquiries.models import PreInvoice


class InquiryService:
    """سرویس مدیریت استعلام‌ها"""
    
    @staticmethod
    def can_issue_for_purchase(purchase: Purchase, user) -> tuple:
        """
        بررسی امکان صدور استعلام برای یک خرید
        
        Returns:
            (can_issue: bool, reason: str)
        """
        # مدیر و انباردار نمی‌توانند
        if user.role in ['manager', 'warehouse']:
            return False, 'فقط کارشناسان و ادمین می‌توانند استعلام صادر کنند'
        
        # کارشناس فقط برای خریدهای خودش
        if user.role == 'expert':
            expert_name = getattr(user, 'expert_name', '') or ''
            if expert_name and expert_name not in (purchase.expert_name or ''):
                return False, 'این خرید متعلق به شما نیست'
        
        # بررسی وجود استعلام قبلی
        if Inquiry.objects.filter(purchase=purchase).exists():
            return False, 'برای این خرید قبلاً استعلام صادر شده است'
        
        # بررسی شماره استعلام در اکسل
        if purchase.inquiry_number:
            return False, 'شماره استعلام در اکسل ثبت شده است'
        
        # بررسی مراحل جلوتر
        blocked_statuses = [
            Purchase.CurrentStatus.ORDER_ISSUED,
            Purchase.CurrentStatus.ORDER_PLACED,
            Purchase.CurrentStatus.WAITING_PAYMENT,
            Purchase.CurrentStatus.PAID,
            Purchase.CurrentStatus.DELIVERED,
        ]
        if purchase.current_status in blocked_statuses:
            return False, 'این خرید به مراحل بعدی رسیده است'
        
        return True, ''
    
    @staticmethod
    @transaction.atomic
    def issue_inquiry(purchase: Purchase, user, data: Dict) -> Inquiry:
        """
        صدور استعلام برای یک خرید
        
        Args:
            purchase: خرید مورد نظر
            user: کاربر صادر کننده
            data: داده‌های فرم
        """
        # بررسی امکان صدور
        can_issue, reason = InquiryService.can_issue_for_purchase(purchase, user)
        if not can_issue:
            raise ValueError(reason)
        
        # تولید شماره استعلام
        inquiry_number = data.get('inquiry_number') or Inquiry.get_next_inquiry_number()
        
        # بررسی یکتا بودن شماره
        if Inquiry.objects.filter(inquiry_number=inquiry_number).exists():
            raise ValueError(f'شماره استعلام {inquiry_number} قبلاً استفاده شده است')
        
        # محاسبه تاریخ جاری شمسی
        try:
            import jdatetime
            today = jdatetime.date.today().strftime('%Y/%m/%d')
        except ImportError:
            today = datetime.now().strftime('%Y/%m/%d')
        
        # ایجاد استعلام
        inquiry = Inquiry.objects.create(
            inquiry_number=inquiry_number,
            purchase=purchase,
            inquiry_date=data.get('inquiry_date') or today,
            deadline=data.get('deadline', ''),
            purchase_type=data.get('purchase_type', '') or purchase.purchase_type,
            urgency_code=data.get('urgency_code', ''),
            supply_unit=data.get('supply_unit', '') or purchase.supply_unit,
            reason=data.get('reason', ''),
            warehouse=data.get('warehouse', ''),
            product_category=data.get('product_category', '') or purchase.product_category,
            warehouse_request_number=(
                data.get('warehouse_request_number', '') or purchase.base_number or ''
            ),
            warehouse_request_date=(
                data.get('warehouse_request_date', '') or purchase.request_date or ''
            ),
            requester=data.get('requester', '') or purchase.requester,
            risk_note=data.get('risk_note', ''),
            expert_name=purchase.expert_name,
            issuer=user.get_full_name() or user.username,
            status=Inquiry.Status.ISSUED,
            created_by=user,
        )
        
        return inquiry

    @staticmethod
    def _preinvoice_grand_total(pre_invoice) -> float:
        subtotal = float(pre_invoice.subtotal or 0)
        tax_rate = float(pre_invoice.tax_rate or 0)
        discount = float(pre_invoice.discount or 0)
        return subtotal + subtotal * (tax_rate / 100) - discount

    @staticmethod
    def pick_winning_preinvoice(pre_invoices) -> Optional['PreInvoice']:
        """پیش‌فاکتور برنده — انتخاب‌شده یا کمترین جمع کل"""
        items = list(pre_invoices)
        if not items:
            return None
        selected = [p for p in items if getattr(p, 'is_selected', False)]
        pool = selected if selected else items
        return min(pool, key=InquiryService._preinvoice_grand_total)

    @staticmethod
    def sync_purchase_from_preinvoice(purchase: Purchase, pre_invoice) -> Purchase:
        """
        همگام‌سازی فیلدهای پیش‌فاکتور با پرونده خرید.
        تخفیف پیش‌فاکتور → ستون کسور (deductions).
        """
        if not pre_invoice:
            return purchase

        line = pre_invoice.lines.first()
        updates: Dict[str, object] = {}

        if pre_invoice.invoice_number:
            updates['preinvoice_number'] = pre_invoice.invoice_number
        if line and line.unit_price:
            updates['preinvoice_price'] = line.unit_price

        subtotal = pre_invoice.subtotal
        if subtotal:
            updates['preinvoice_total'] = Decimal(str(subtotal))

        discount = Decimal(str(pre_invoice.discount or 0))
        updates['deductions'] = discount

        if pre_invoice.contractor:
            updates['supplier'] = pre_invoice.contractor

        for field, value in updates.items():
            setattr(purchase, field, value)
        purchase.save()
        return purchase

    @staticmethod
    def sync_purchase_from_inquiry(purchase: Purchase, inquiry: Inquiry) -> Purchase:
        """پس از صدور استعلام، پیش‌فاکتور برنده را روی خرید بنویس"""
        pre_invoice = InquiryService.pick_winning_preinvoice(
            inquiry.pre_invoices.prefetch_related('lines').all()
        )
        return InquiryService.sync_purchase_from_preinvoice(purchase, pre_invoice)
    
    @staticmethod
    def get_inquiries_for_user(user, search: str = '', status: str = ''):
        """دریافت استعلام‌ها بر اساس نقش کاربر"""
        queryset = Inquiry.objects.select_related('purchase', 'created_by')
        
        # فیلتر بر اساس نقش
        if user.role == 'expert':
            expert_name = getattr(user, 'expert_name', '') or ''
            if expert_name:
                queryset = queryset.filter(expert_name__icontains=expert_name)
        elif user.role == 'warehouse':
            warehouse = getattr(user, 'warehouse', '') or ''
            if warehouse:
                queryset = queryset.filter(warehouse__icontains=warehouse)
        
        # فیلتر جستجو
        if search:
            queryset = queryset.filter(
                models.Q(inquiry_number__icontains=search) |
                models.Q(purchase__purchase_number__icontains=search) |
                models.Q(purchase__product_title__icontains=search) |
                models.Q(expert_name__icontains=search)
            )
        
        # فیلتر وضعیت
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset