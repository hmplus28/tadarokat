from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from .models import AuditLog
from accounts.permissions import superuser_required


@login_required
@superuser_required
def audit_log_list(request):
    """لیست لاگ‌های تغییرات - فقط سوپر یوزر"""
    queryset = AuditLog.objects.select_related('user')
    
    # پارامترهای فیلتر
    search = request.GET.get('search', '')
    action = request.GET.get('action', '')
    entity_type = request.GET.get('entity_type', '')
    user_filter = request.GET.get('user', '')
    days = request.GET.get('days', '30')
    
    # فیلتر تاریخ
    try:
        days_int = int(days)
        since = timezone.now() - timedelta(days=days_int)
        queryset = queryset.filter(created_at__gte=since)
    except (ValueError, TypeError):
        days_int = 30
        since = timezone.now() - timedelta(days=30)
        queryset = queryset.filter(created_at__gte=since)
    
    # فیلترهای جستجو
    if search:
        queryset = queryset.filter(
            Q(entity_repr__icontains=search) |
            Q(description__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )
    if action:
        queryset = queryset.filter(action=action)
    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)
    if user_filter:
        queryset = queryset.filter(user__username__icontains=user_filter)
    
    # آمار کلی (روی queryset فیلتر شده)
    stats = queryset.aggregate(
        total=Count('id'),
        creates=Count('id', filter=Q(action='create')),
        updates=Count('id', filter=Q(action='update')),
        deletes=Count('id', filter=Q(action='delete')),
        logins=Count('id', filter=Q(action='login')),
        issues=Count('id', filter=Q(action='issue')),
    )
    
    # نمودار روزانه
    daily_stats = list(
        queryset.annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # Pagination
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    # لیست entity types منحصر به فرد (از کل دیتابیس نه فقط فیلتر شده)
    entity_types = list(
        AuditLog.objects.values_list('entity_type', flat=True)
        .distinct().order_by('entity_type')
    )
    
    # لیست کاربران منحصر به فرد (برای فیلتر سریع)
    active_users = list(
        AuditLog.objects.exclude(user__isnull=True)
        .values_list('user__username', flat=True)
        .distinct()
        .order_by('user__username')[:50]
    )
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'action': action,
        'entity_type': entity_type,
        'user_filter': user_filter,
        'days': days,
        'stats': stats,
        'daily_stats': daily_stats,
        'daily_dates': [str(s['date']) for s in daily_stats],
        'daily_counts': [s['count'] for s in daily_stats],
        'entity_types': entity_types,
        'active_users': active_users,
        'action_choices': AuditLog.Action.choices,
    }
    return render(request, 'audit/list.html', context)