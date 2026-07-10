"""بررسی مدیر تدارکات قبل از صدور دستور — ارجاع کارشناس و بازگشت استعلام"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from inquiries.models import Inquiry
from orders.models import Order
from purchases.models import Purchase, is_valid_value

User = get_user_model()

INQUIRY_RESET_FIELDS = (
    'inquiry_number',
    'inquiry_received_date',
    'inquiry_deadline',
    'inquiry_deadline_2',
    'preinvoice_number',
    'purchase_type',
    'supplier',
)

INQUIRY_RESET_DECIMAL_FIELDS = (
    'preinvoice_price',
    'preinvoice_total',
)


class OrderReviewService:
    """عملیات مدیر در صف صدور دستور خرید"""

    @staticmethod
    def get_expert_choices() -> List[Dict[str, str]]:
        """لیست کارشناسان فعال برای انتخاب در فرم ارجاع"""
        seen: set[str] = set()
        choices: List[Dict[str, str]] = []
        qs = User.objects.filter(role='expert', is_active=True).order_by(
            'expert_name', 'first_name', 'username'
        )
        for user in qs:
            label = (user.expert_name or user.get_display_name() or user.username).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            choices.append({
                'value': label,
                'label': label,
                'username': user.username,
            })
        return choices

    @staticmethod
    def get_pending_queue(search: str = '', expert: str = ''):
        """ردیف‌های آماده صدور دستور (استعلام دارند، دستور ندارند)"""
        has_order = Order.objects.filter(purchase_id=OuterRef('pk'))
        qs = (
            Purchase.objects
            .annotate(_has_order=Exists(has_order))
            .filter(_has_order=False)
            .exclude(Q(inquiry_number__isnull=True) | Q(inquiry_number=''))
            .select_related()
            .order_by('-purchase_number', 'line_number')
        )
        if search:
            from services.search_service import SearchService
            qs = SearchService.filter_purchases(qs, search)
        if expert:
            qs = qs.filter(expert_name__icontains=expert)

        return [p for p in qs if p.can_issue_order]

    @classmethod
    def _resolve_purchases(cls, purchase_ids: Sequence[int]) -> List[Purchase]:
        if not purchase_ids:
            raise ValueError('حداقل یک ردیف انتخاب کنید.')
        purchases = list(
            Purchase.objects.filter(pk__in=purchase_ids).order_by('purchase_number', 'line_number')
        )
        if len(purchases) != len(set(purchase_ids)):
            raise ValueError('برخی ردیف‌های انتخاب‌شده یافت نشدند.')
        invalid = [p for p in purchases if not p.can_issue_order]
        if invalid:
            labels = ', '.join(f'{p.purchase_number}-{p.line_number}' for p in invalid[:5])
            raise ValueError(f'این ردیف‌ها آماده صدور دستور نیستند: {labels}')
        return purchases

    @classmethod
    @transaction.atomic
    def reassign_expert(
        cls,
        purchase_ids: Sequence[int],
        new_expert_name: str,
        manager,
        note: str = '',
        request=None,
    ) -> Dict:
        new_expert_name = (new_expert_name or '').strip()
        if not new_expert_name:
            raise ValueError('کارشناس مقصد را انتخاب کنید.')

        purchases = cls._resolve_purchases(purchase_ids)
        updated = 0

        for purchase in purchases:
            old_expert = purchase.expert_name or ''
            if old_expert == new_expert_name:
                continue

            purchase.expert_name = new_expert_name
            purchase.save(update_fields=['expert_name', 'current_status'])

            inquiry = cls._get_linked_inquiry(purchase)
            if inquiry:
                inquiry.expert_name = new_expert_name
                inquiry.save(update_fields=['expert_name', 'updated_at'])

            cls._audit(
                manager, 'update', purchase,
                field_name='expert_name',
                old_value=old_expert,
                new_value=new_expert_name,
                description=note or f'ارجاع از {old_expert or "—"} به {new_expert_name}',
                request=request,
            )
            cls._notify_expert(
                new_expert_name,
                '👤 ارجاع پرونده خرید',
                (
                    f'خرید {purchase.purchase_number}-{purchase.line_number} '
                    f'«{purchase.product_title[:40]}» توسط مدیر به شما ارجاع شد.'
                    + (f' توضیح: {note}' if note else '')
                ),
                purchase,
            )
            updated += 1

        return {'updated': updated, 'total': len(purchases)}

    @classmethod
    @transaction.atomic
    def return_for_reinquiry(
        cls,
        purchase_ids: Sequence[int],
        manager,
        note: str = '',
        new_expert_name: str = '',
        request=None,
    ) -> Dict:
        note = (note or '').strip()
        if not note:
            raise ValueError('دلیل بازگشت برای استعلام مجدد الزامی است.')

        new_expert_name = (new_expert_name or '').strip()
        purchases = cls._resolve_purchases(purchase_ids)
        returned = 0

        for purchase in purchases:
            old_inquiry = purchase.inquiry_number or ''
            old_expert = purchase.expert_name or ''
            target_expert = new_expert_name or old_expert

            inquiry = cls._get_linked_inquiry(purchase)
            if inquiry:
                inquiry.status = Inquiry.Status.REJECTED
                suffix = f'\n[بازگشت توسط مدیر — {manager.get_display_name()}] {note}'
                inquiry.risk_note = f'{(inquiry.risk_note or "").strip()}{suffix}'.strip()
                if new_expert_name:
                    inquiry.expert_name = new_expert_name
                inquiry.save()

            for field in INQUIRY_RESET_FIELDS:
                setattr(purchase, field, '')
            for field in INQUIRY_RESET_DECIMAL_FIELDS:
                setattr(purchase, field, 0)
            if new_expert_name:
                purchase.expert_name = new_expert_name

            purchase.save()

            cls._audit(
                manager, 'update', purchase,
                field_name='inquiry_number',
                old_value=old_inquiry,
                new_value='',
                description=f'بازگشت برای استعلام مجدد — {note}',
                request=request,
            )
            if target_expert:
                cls._notify_expert(
                    target_expert,
                    '🔄 استعلام مجدد',
                    (
                        f'خرید {purchase.purchase_number}-{purchase.line_number} '
                        f'«{purchase.product_title[:40]}» توسط مدیر برای استعلام مجدد برگشت داده شد.'
                        f' دلیل: {note}'
                    ),
                    purchase,
                )
            returned += 1

        return {'returned': returned, 'total': len(purchases)}

    @staticmethod
    def _get_linked_inquiry(purchase: Purchase) -> Optional[Inquiry]:
        inquiry = Inquiry.objects.filter(purchase=purchase).order_by('-created_at').first()
        if inquiry:
            return inquiry
        if is_valid_value(purchase.inquiry_number):
            return Inquiry.objects.filter(
                inquiry_number=purchase.inquiry_number,
                purchase=purchase,
            ).first()
        return None

    @staticmethod
    def _find_expert_user(expert_name: str):
        name = (expert_name or '').strip()
        if not name:
            return None
        user = User.objects.filter(role='expert', is_active=True, expert_name=name).first()
        if user:
            return user
        return User.objects.filter(
            role='expert', is_active=True
        ).filter(
            Q(first_name__icontains=name) | Q(username__icontains=name)
        ).first()

    @classmethod
    def _notify_expert(cls, expert_name: str, title: str, message: str, purchase: Purchase):
        from services.notification_service import NotificationService
        user = cls._find_expert_user(expert_name)
        if user:
            NotificationService.notify(
                user, title, message, 'purchase', f'/purchases/{purchase.pk}/'
            )

    @staticmethod
    def _audit(manager, action, purchase, *, field_name='', old_value='', new_value='',
               description='', request=None):
        from audit.models import AuditLog
        AuditLog.log(
            user=manager,
            action=action,
            entity_type='بررسی صدور دستور',
            entity_id=str(purchase.pk),
            entity_repr=f'{purchase.purchase_number}-{purchase.line_number}',
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            description=description,
            request=request,
        )