from services.notification_service import NotificationService


def notification_count(request):
    if request.user.is_authenticated:
        return {'unread_notifications': NotificationService.get_unread_count(request.user)}
    return {'unread_notifications': 0}