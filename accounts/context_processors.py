def user_role_classes(request):
    """
    اضافه کردن کلاس‌های CSS بر اساس نقش کاربر
    
    برای admin و superuser، همه کلاس‌های پایین‌تر هم اضافه می‌شوند
    چون آنها به قابلیت‌های پایین‌تر هم دسترسی دارند.
    
    مثال:
    - superuser → role-superuser, role-admin, role-expert, not-warehouse
    - admin → role-admin, role-expert, not-warehouse, not-superuser
    - expert → role-expert, not-warehouse, not-admin, not-superuser
    - warehouse → role-warehouse, not-expert, not-admin, not-superuser
    - requester → role-requester, not-warehouse, not-expert, not-admin, not-superuser, not-manager
    """
    if not request.user.is_authenticated:
        return {
            'role_classes': '', 
            'user_role': '',
            'is_superuser': False,
            'is_admin': False,
            'is_expert': False,
            'is_warehouse': False,
            'is_requester': False,
            'requester_scope_label': '',
        }
    
    role = request.user.role
    classes = ['role-authenticated']
    
    # سوپر یوزر: دسترسی به همه چیز
    if role == 'superuser' or request.user.is_superuser:
        classes.extend([
            'role-superuser', 
            'role-admin', 
            'role-expert', 
            'not-warehouse',
            'not-requester',
        ])
    
    # مدیر تدارکات: دسترسی به admin + expert
    elif role == 'admin':
        classes.extend([
            'role-admin', 
            'role-expert', 
            'not-warehouse', 
            'not-superuser',
            'not-requester',
        ])
    
    # کارشناس: فقط expert
    elif role == 'expert':
        classes.extend([
            'role-expert', 
            'not-warehouse', 
            'not-admin', 
            'not-superuser',
            'not-requester',
        ])
    
    # انباردار: فقط warehouse
    elif role == 'warehouse':
        classes.extend([
            'role-warehouse', 
            'not-expert', 
            'not-admin', 
            'not-superuser',
            'not-requester',
        ])

    # درخواست‌دهنده: پیگیری گردش کار واحد خود
    elif role == 'requester':
        classes.extend([
            'role-requester',
            'requester-only',
            'not-warehouse',
            'not-expert',
            'not-admin',
            'not-superuser',
            'not-manager',
        ])
    
    from accounts.requester_access import get_requester_scope_label
    return {
        'role_classes': ' '.join(classes),
        'user_role': role,
        'is_superuser': request.user.is_superuser_role,
        'is_admin': request.user.is_admin_role,
        'is_expert': request.user.is_expert_role,
        'is_warehouse': request.user.is_warehouse_role,
        'is_requester': request.user.is_requester_role,
        'requester_scope_label': get_requester_scope_label(request.user),
    }