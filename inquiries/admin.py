from django.contrib import admin
from django.utils.html import format_html
from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = (
        'inquiry_number',
        'purchase_link',
        'expert_name',
        'inquiry_date',
        'deadline',
        'status_badge',
        'created_by',
    )
    list_filter = ('status', 'purchase_type', 'expert_name')
    search_fields = (
        'inquiry_number', 'purchase__purchase_number',
        'purchase__product_title', 'expert_name', 'issuer'
    )
    readonly_fields = ('inquiry_number', 'created_at', 'updated_at')
    ordering = ('-inquiry_number',)
    raw_id_fields = ('purchase', 'created_by')
    
    def purchase_link(self, obj):
        if obj.purchase:
            return f"{obj.purchase.purchase_number} - {obj.purchase.product_title[:30]}"
        return "—"
    purchase_link.short_description = 'درخواست خرید'
    
    def status_badge(self, obj):
        colors = {
            'draft': '#94a3b8',
            'issued': '#3b82f6',
            'approved': '#10b981',
            'rejected': '#ef4444',
            'completed': '#059669',
        }
        color = colors.get(obj.status, '#94a3b8')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'وضعیت'