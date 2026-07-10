from django.contrib import admin
from django.utils.html import format_html
from .models import Purchase


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'purchase_number',
        'product_title_short',
        'product_code',
        'expert_name',
        'status',
        'current_status_badge',
        'purchase_date',
    )
    list_filter = ('current_status', 'status', 'expert_name', 'supply_unit')
    search_fields = (
        'purchase_number', 'product_title', 'product_code',
        'requester', 'expert_name', 'inquiry_number', 'order_number'
    )
    readonly_fields = ('current_status', 'created_at', 'updated_at')
    ordering = ('-purchase_number',)
    
    fieldsets = (
        ('اطلاعات اولیه', {
            'fields': (
                'purchase_number', 'base_number', 'request_date',
                'purchase_date', 'supply_unit', 'requester'
            )
        }),
        ('اطلاعات کالا', {
            'fields': (
                'product_code', 'product_title', 'unit', 'quantity'
            )
        }),
        ('وضعیت', {
            'fields': (
                'status', 'required_date', 'current_status',
                'expert_name', 'description'
            )
        }),
        ('مراحل خرید', {
            'fields': (
                ('inquiry_number', 'inquiry_deadline'),
                ('order_number', 'order_date'),
                ('order_request_number', 'order_request_date'),
                ('delivery_number', 'delivery_date'),
            )
        }),
        ('متادیتا', {
            'fields': ('created_at', 'updated_at', 'imported_by')
        }),
    )
    
    def product_title_short(self, obj):
        return obj.product_title[:50] + '...' if len(obj.product_title) > 50 else obj.product_title
    product_title_short.short_description = 'عنوان کالا'
    
    def current_status_badge(self, obj):
        colors = {
            'waiting_inquiry': '#94a3b8',
            'inquiry_issued': '#3b82f6',
            'order_issued': '#8b5cf6',
            'order_placed': '#06b6d4',
            'waiting_payment': '#f59e0b',
            'paid': '#10b981',
            'delivered': '#059669',
        }
        color = colors.get(obj.current_status, '#94a3b8')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_current_status_display()
        )
    current_status_badge.short_description = 'وضعیت فعلی'