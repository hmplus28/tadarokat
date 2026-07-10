from django.contrib import admin
from django.utils.html import format_html
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'user', 'action_badge', 'entity_type', 
        'entity_repr_short', 'field_name', 'ip_address'
    )
    list_filter = ('action', 'entity_type', 'created_at', 'user')
    search_fields = ('entity_repr', 'entity_id', 'description', 'user__username')
    readonly_fields = (
        'user', 'action', 'entity_type', 'entity_id', 'entity_repr',
        'field_name', 'old_value', 'new_value', 'description',
        'ip_address', 'user_agent', 'created_at'
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    def entity_repr_short(self, obj):
        return obj.entity_repr[:50] + '...' if len(obj.entity_repr) > 50 else obj.entity_repr
    entity_repr_short.short_description = 'موجودیت'
    
    def action_badge(self, obj):
        colors = {
            'create': '#10b981',
            'update': '#3b82f6',
            'delete': '#ef4444',
            'login': '#8b5cf6',
            'logout': '#6b7280',
            'export': '#f59e0b',
            'issue': '#06b6d4',
            'advance': '#ec4899',
        }
        color = colors.get(obj.action, '#6b7280')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; border-radius:4px; font-size:11px;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'عملیات'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser