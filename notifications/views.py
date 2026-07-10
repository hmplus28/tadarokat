from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Notification
from services.notification_service import NotificationService


@login_required
def notification_list(request):
    """دریافت لیست اعلان‌های خوانده نشده"""
    notifications = Notification.objects.filter(
        user=request.user, is_read=False
    )[:20]
    
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'type': n.type,
        'url': n.reference_url,
        'time': n.created_at.strftime('%H:%M'),
    } for n in notifications]
    
    return JsonResponse({
        'items': data,
        'unread_count': NotificationService.get_unread_count(request.user),
    })


@login_required
@require_POST
def mark_all_read(request):
    """علامت‌گذاری همه به عنوان خوانده شده"""
    count = NotificationService.mark_all_read(request.user)
    return JsonResponse({'ok': True, 'marked': count})