"""سرویس مدیریت اعلان‌ها"""
from notifications.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

ROLE_ALIASES = {
    'manager': 'admin',
    'مدیر': 'admin',
}


class NotificationService:
    @staticmethod
    def _resolve_role(role: str) -> str:
        return ROLE_ALIASES.get(role, role)

    @staticmethod
    def notify(user, title: str, message: str, n_type: str = 'info', url: str = ''):
        """ارسال اعلان به یک کاربر خاص"""
        if not user or not getattr(user, 'is_authenticated', False):
            return None
        return Notification.objects.create(
            user=user, title=title, message=message, type=n_type, reference_url=url
        )

    @staticmethod
    def notify_role(role: str, title: str, message: str, n_type: str = 'info', url: str = ''):
        """ارسال اعلان به تمام کاربران دارای یک نقش خاص"""
        resolved = NotificationService._resolve_role(role)
        users = User.objects.filter(role=resolved, is_active=True)
        notifications = []
        for user in users:
            notifications.append(Notification(
                user=user, title=title, message=message, type=n_type, reference_url=url
            ))
        if notifications:
            Notification.objects.bulk_create(notifications)
        return len(notifications)

    @staticmethod
    def notify_roles(roles, title: str, message: str, n_type: str = 'info', url: str = ''):
        """ارسال اعلان به چند نقش"""
        total = 0
        for role in roles:
            total += NotificationService.notify_role(role, title, message, n_type, url)
        return total

    @staticmethod
    def _warehouse_users_for(warehouse_name: str = ''):
        qs = User.objects.filter(role='warehouse', is_active=True).select_related('assigned_warehouse')
        name = (warehouse_name or '').strip()
        if name:
            matched = qs.filter(assigned_warehouse__name=name)
            if matched.exists():
                return matched
        return qs

    @staticmethod
    def notify_warehouse_users(
        warehouse_name: str,
        title: str,
        message: str,
        n_type: str = 'info',
        url: str = '',
    ) -> int:
        """اعلان به انباردار(های) مرتبط با انبار مقصد"""
        users = list(NotificationService._warehouse_users_for(warehouse_name))
        if not users:
            return 0
        Notification.objects.bulk_create([
            Notification(
                user=user,
                title=title,
                message=message,
                type=n_type,
                reference_url=url,
            )
            for user in users
        ])
        return len(users)

    @staticmethod
    def notify_warehouse_payment_ready(order):
        """اعلان: دستور پرداخت‌شده — آماده ثبت رسید تحویل"""
        wh = (order.warehouse or getattr(order.purchase, 'supply_unit', '') or '').strip()
        msg = (
            f'دستور {order.order_number} — «{order.product_title[:40]}» '
            f'پرداخت شده. برای ثبت رسید تحویل اقدام کنید.'
        )
        return NotificationService.notify_warehouse_users(
            wh,
            '📦 کالای آماده دریافت',
            msg,
            'order',
            f'/orders/{order.pk}/',
        )

    @staticmethod
    def notify_warehouse_goods_request(inquiry) -> int:
        """اعلان: کارشناس درخواست کالا از انبار ثبت کرده"""
        req_no = (inquiry.warehouse_request_number or '').strip()
        req_date = (inquiry.warehouse_request_date or '').strip()
        if not req_no and not req_date:
            return 0

        wh = (inquiry.warehouse or inquiry.supply_unit or '').strip()
        purchase_no = inquiry.purchase.purchase_number if inquiry.purchase_id else '—'
        parts = [f'استعلام {inquiry.inquiry_number}', f'خرید {purchase_no}']
        if req_no:
            parts.append(f'شماره درخواست {req_no}')
        if req_date:
            parts.append(f'تاریخ {req_date}')
        msg = ' — '.join(parts)
        return NotificationService.notify_warehouse_users(
            wh,
            '📋 درخواست کالا از انبار',
            msg,
            'inquiry',
            f'/deliveries/',
        )

    @staticmethod
    def notify_warehouse_delivery_scheduled(order) -> int:
        """اعلان: کارشناس تاریخ/شماره تحویل ثبت کرده"""
        delivery_date = (order.delivery_date or '').strip()
        delivery_no = (order.delivery_number or '').strip()
        if not delivery_date and not delivery_no:
            return 0

        wh = (order.warehouse or getattr(order.purchase, 'supply_unit', '') or '').strip()
        msg = f'دستور {order.order_number} — «{order.product_title[:40]}»'
        if delivery_no:
            msg += f' — شماره تحویل: {delivery_no}'
        if delivery_date:
            msg += f' — تاریخ: {delivery_date}'
        return NotificationService.notify_warehouse_users(
            wh,
            '📅 تاریخ تحویل ثبت شد',
            msg,
            'delivery',
            f'/orders/{order.pk}/',
        )

    @staticmethod
    def get_unread_count(user) -> int:
        if not user.is_authenticated:
            return 0
        return Notification.objects.filter(user=user, is_read=False).count()

    @staticmethod
    def mark_all_read(user) -> int:
        count = Notification.objects.filter(user=user, is_read=False).update(is_read=True)
        return count