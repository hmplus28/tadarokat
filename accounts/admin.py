from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Warehouse, ProductCategory, CategoryDeadlineRule


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('sort_order', 'name')


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('sort_order', 'name')


@admin.register(CategoryDeadlineRule)
class CategoryDeadlineRuleAdmin(admin.ModelAdmin):
    list_display = ('category', 'allowed_days', 'allowed_weekdays', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('category__name', 'notes')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'expert_name')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        (_('اطلاعات تکمیلی'), {
            'fields': ('role', 'expert_name', 'assigned_warehouse', 'requester_scope', 'phone'),
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (_('اطلاعات تکمیلی'), {
            'fields': ('role', 'expert_name', 'assigned_warehouse', 'requester_scope', 'phone'),
        }),
    )