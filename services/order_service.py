"""سرویس مدیریت گردش کار دستور خرید"""
from django.db import transaction
from django.db.models import Q
from typing import Dict, List, Optional
from orders.models import Order


# تعریف ترتیب مراحل و فیلدهای الزامی هر مرحله
STAGE_FLOW = {
    'order_issued': {
        'next': 'order_placed',
        'label': 'ثبت سفارش',
        'required_fields': ['order_request_number', 'order_request_date'],
    },
    'order_placed': {
        'next': 'payment',
        'label': 'ثبت پرداخت',
        'required_fields': ['payment_number', 'payment_date'],
    },
    'payment': {
        'next': 'delivered',
        'label': 'ثبت تحویل',
        'required_fields': ['delivery_number', 'delivery_date'],
    },
    'delivered': {
        'next': None,
        'label': 'تکمیل شده',
        'required_fields': [],
    },
}


class OrderService:
    """منطق تجاری دستورات خرید"""

    @staticmethod
    def get_today_jalali() -> str:
        from datetime import datetime
        try:
            import jdatetime
            return jdatetime.date.today().strftime('%Y/%m/%d')
        except ImportError:
            return datetime.now().strftime('%Y/%m/%d')

    @staticmethod
    def get_similar_purchases(purchase, limit: int = 8) -> List:
        """سوابق خرید کالای مشابه (بر اساس کد یا عنوان)"""
        from purchases.models import Purchase, is_valid_value

        qs = Purchase.objects.exclude(pk=purchase.pk)
        if purchase.product_code and is_valid_value(purchase.product_code):
            qs = qs.filter(product_code=purchase.product_code)
        elif purchase.product_title:
            title = purchase.product_title.strip()
            if len(title) >= 4:
                qs = qs.filter(product_title__icontains=title[:40])
            else:
                return []
        else:
            return []

        qs = qs.filter(
            Q(order_number__gt='') |
            Q(order_request_number__gt='') |
            Q(supplier__gt='')
        ).order_by('-purchase_number', 'line_number')
        return list(qs[:limit])

    @staticmethod
    def get_preinvoice_comparison(inquiry) -> List[Dict]:
        """داده مقایسه پیش‌فاکتور پیمانکاران برای صفحه صدور دستور"""
        if not inquiry:
            return []

        rows = []
        pre_invoices = inquiry.pre_invoices.prefetch_related('lines').all()
        for pi in pre_invoices:
            line = pi.lines.first()
            unit_price = float(line.unit_price) if line else 0
            rows.append({
                'id': pi.pk,
                'contractor': pi.contractor,
                'invoice_number': pi.invoice_number,
                'unit_price': unit_price,
                'total': float(pi.total),
                'is_selected': pi.is_selected,
            })
        if rows:
            min_total = min(r['total'] for r in rows if r['total'] > 0) if any(r['total'] > 0 for r in rows) else 0
            for row in rows:
                row['is_lowest'] = row['total'] > 0 and row['total'] == min_total
        return rows

    @staticmethod
    def get_order_create_defaults(purchase, inquiry=None) -> Dict:
        """مقادیر پیش‌فرض فرم صدور دستور (شماره و تاریخ خودکار)"""
        from purchases.models import is_valid_value

        defaults = {
            'order_number': Order.get_next_order_number(),
            'order_date': OrderService.get_today_jalali(),
            'unit_price': purchase.preinvoice_price or None,
            'contractor': purchase.supplier or '',
        }

        if inquiry:
            selected = inquiry.pre_invoices.filter(is_selected=True).prefetch_related('lines').first()
            if not selected:
                candidates = list(inquiry.pre_invoices.prefetch_related('lines').all())
                if candidates:
                    selected = min(candidates, key=lambda p: float(p.total or 0))
            if selected:
                defaults['contractor'] = selected.contractor
                line = selected.lines.first()
                if line and line.unit_price:
                    defaults['unit_price'] = line.unit_price
                elif is_valid_value(purchase.preinvoice_price):
                    defaults['unit_price'] = purchase.preinvoice_price

        return defaults

    @staticmethod
    def get_stage_info(stage: str) -> Dict:
        """دریافت اطلاعات مرحله جاری"""
        return STAGE_FLOW.get(stage, STAGE_FLOW['order_issued'])

    @staticmethod
    def can_advance(order: Order) -> bool:
        """آیا امکان پیشبرد مرحله وجود دارد؟"""
        info = STAGE_FLOW.get(order.stage)
        return info is not None and info['next'] is not None

    @staticmethod
    @transaction.atomic
    def advance_stage(order: Order, data: Dict, username: str) -> Order:
        """
        پیشبرد دستور به مرحله بعدی
        
        Args:
            order: دستور خرید
            data: داده‌های فرم (شامل فیلدهای الزامی مرحله بعد)
            username: کاربر انجام دهنده
        """
        current_info = STAGE_FLOW.get(order.stage)
        if not current_info or not current_info['next']:
            raise ValueError('این دستور قبلاً تکمیل شده است')

        next_stage = current_info['next']
        next_info = STAGE_FLOW[next_stage]

        # اعتبارسنجی فیلدهای الزامی
        missing = []
        for field in next_info['required_fields']:
            val = data.get(field, '').strip() if isinstance(data.get(field), str) else data.get(field)
            if not val:
                missing.append(field)
        
        if missing:
            field_labels = {
                'order_request_number': 'شماره سفارش',
                'order_request_date': 'تاریخ سفارش',
                'payment_number': 'شماره پرداخت',
                'payment_date': 'تاریخ پرداخت',
                'delivery_number': 'شماره تحویل',
                'delivery_date': 'تاریخ تحویل',
            }
            labels = [field_labels.get(f, f) for f in missing]
            raise ValueError(f'فیلدهای الزامی برای مرحله «{next_info["label"]}»: {", ".join(labels)}')

        # به‌روزرسانی فیلدها
        updates = {'stage': next_stage}
        for field in next_info['required_fields']:
            updates[field] = data[field].strip() if isinstance(data[field], str) else data[field]

        # افزودن توضیحات اختیاری
        note = data.get('note', '').strip()
        if note:
            prev_desc = order.description or ''
            updates['description'] = f"{prev_desc}\n📝 [{next_info['label']}] {note}".strip()

        # به‌روزرسانی وضعیت
        if next_stage == 'delivered':
            updates['status'] = 'تحویل شده'
        elif next_stage == 'payment':
            updates['status'] = 'پرداخت شده'
        elif next_stage == 'order_placed':
            updates['status'] = 'سفارش داده شده'

        for key, value in updates.items():
            setattr(order, key, value)
        order.save()

        from services.notification_service import NotificationService
        if next_stage == 'payment':
            NotificationService.notify_warehouse_payment_ready(order)
        elif next_stage == 'delivered':
            NotificationService.notify_warehouse_delivery_scheduled(order)

        return order

    @staticmethod
    @transaction.atomic
    def create_from_purchase(purchase, user, data: Dict, inquiry=None) -> Order:
        """ایجاد دستور خرید مستقیم از درخواست خرید"""
        from inquiries.models import Inquiry

        today = OrderService.get_today_jalali()
        order_number = (data.get('order_number') or '').strip() or Order.get_next_order_number()

        if Order.objects.filter(order_number=order_number).exists():
            raise ValueError(f'شماره دستور {order_number} تکراری است')

        if purchase.orders.exists():
            raise ValueError('برای این خرید قبلاً دستور صادر شده است')

        if not inquiry and purchase.inquiry_number:
            inquiry = Inquiry.objects.filter(inquiry_number=purchase.inquiry_number).first()

        if inquiry:
            from services.inquiry_service import InquiryService
            selected_pi = None
            contractor = (data.get('contractor') or '').strip()
            if contractor:
                selected_pi = inquiry.pre_invoices.filter(
                    contractor=contractor
                ).prefetch_related('lines').first()
            if not selected_pi:
                selected_pi = InquiryService.pick_winning_preinvoice(
                    inquiry.pre_invoices.prefetch_related('lines').all()
                )
            if selected_pi:
                InquiryService.sync_purchase_from_preinvoice(purchase, selected_pi)

        qty = float(purchase.quantity or 0)
        price = float(data.get('unit_price') or purchase.preinvoice_price or 0)
        order_date = (data.get('order_date') or '').strip() or today
        contractor = (data.get('contractor') or '').strip()

        order = Order.objects.create(
            order_number=order_number,
            inquiry=inquiry,
            purchase=purchase,
            product_title=purchase.product_title or '',
            product_code=purchase.product_code or '',
            quantity=qty,
            unit=purchase.unit or '',
            unit_price=price,
            total_price=qty * price,
            contractor=contractor,
            warehouse=purchase.supply_unit or '',
            expert_name=purchase.expert_name or '',
            stage=Order.Stage.ORDER_ISSUED,
            status='جاری',
            order_date=order_date,
            description=data.get('description', ''),
            issued_by=user.get_full_name() or user.username,
            created_by=user,
        )

        purchase.order_number = order_number
        purchase.order_date = order_date
        if contractor:
            purchase.supplier = contractor
        if price:
            purchase.preinvoice_price = price
        purchase.save()

        return order