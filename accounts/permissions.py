from django.contrib.auth.decorators import user_passes_test
from rest_framework.permissions import BasePermission


# ============================================
# DRF Permissions (برای API ها)
# ============================================

class IsSuperUser(BasePermission):
    """فقط سوپر یوزر"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser_role


class IsAdminOrAbove(BasePermission):
    """مدیر تدارکات و بالاتر"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin_role


class IsExpertOrAbove(BasePermission):
    """کارشناس تدارکات و بالاتر"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_expert_role


class IsWarehouse(BasePermission):
    """فقط انباردار"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_warehouse_role


class CanIssueInquiry(BasePermission):
    """فقط کارشناس و بالاتر می‌توانند استعلام صادر کنند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_issue_inquiry


class CanCreateOrder(BasePermission):
    """فقط مدیر تدارکات و بالاتر می‌توانند دستور خرید صادر کنند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_create_order


class CanRegisterDelivery(BasePermission):
    """فقط انباردار و سوپر یوزر می‌توانند تحویل ثبت کنند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_register_delivery


class CanViewReports(BasePermission):
    """فقط مدیر تدارکات و بالاتر می‌توانند گزارش‌ها را ببینند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_view_reports


class CanViewAuditLog(BasePermission):
    """فقط سوپر یوزر می‌تواند تاریخچه تغییرات را ببیند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_view_audit_log


class CanEditAllFields(BasePermission):
    """فقط سوپر یوزر می‌تواند همه فیلدها را ویرایش کند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_edit_all_fields


class CanSyncExcel(BasePermission):
    """فقط مدیر تدارکات و بالاتر می‌توانند اکسل sync کنند"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.can_sync_excel


# ============================================
# Function-based Decorators (برای View های معمولی)
# ============================================

def is_superuser_check(user):
    return user.is_authenticated and user.is_superuser_role


def is_admin_or_above_check(user):
    return user.is_authenticated and user.is_admin_role


def is_expert_or_above_check(user):
    return user.is_authenticated and user.is_expert_role


def is_warehouse_check(user):
    return user.is_authenticated and user.is_warehouse_role


# Decorators
superuser_required = user_passes_test(is_superuser_check)
admin_required = user_passes_test(is_admin_or_above_check)
expert_required = user_passes_test(is_expert_or_above_check)
warehouse_required = user_passes_test(is_warehouse_check)


# ============================================
# Helper Function برای View ها
# ============================================

def check_permission(user, permission_type):
    """
    بررسی دسترسی کاربر بر اساس نوع permission
    استفاده: check_permission(request.user, 'can_issue_inquiry')
    """
    if not user.is_authenticated:
        return False
    
    permission_map = {
        'can_issue_inquiry': user.can_issue_inquiry,
        'can_create_order': user.can_create_order,
        'can_register_delivery': user.can_register_delivery,
        'can_view_reports': user.can_view_reports,
        'can_view_audit_log': user.can_view_audit_log,
        'can_edit_all_fields': user.can_edit_all_fields,
        'can_manage_users': user.can_manage_users,
        'can_sync_excel': user.can_sync_excel,
    }
    
    return permission_map.get(permission_type, False)