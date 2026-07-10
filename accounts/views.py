import time

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import OperationalError
from django.db.models import Q
from .models import User, Warehouse, ProductCategory, CategoryDeadlineRule
from .permissions import superuser_required, admin_required


def _resolve_assigned_warehouse(post_data):
    """انتخاب انبار از لیست یا ایجاد انبار جدید"""
    new_name = (post_data.get('new_warehouse_name') or '').strip()
    if new_name:
        wh, _ = Warehouse.objects.get_or_create(
            name=new_name,
            defaults={'sort_order': Warehouse.objects.count() + 1, 'is_active': True},
        )
        return wh

    warehouse_id = post_data.get('assigned_warehouse', '')
    if warehouse_id:
        return Warehouse.objects.filter(pk=warehouse_id, is_active=True).first()
    return None


def login_view(request):
    """صفحه ورود"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            for attempt in range(4):
                try:
                    login(request, user)
                    break
                except OperationalError:
                    if attempt == 3:
                        messages.error(
                            request,
                            'پایگاه داده مشغول است. اگر sync اکسل در حال اجراست، چند ثانیه صبر کنید و دوباره تلاش کنید.',
                        )
                        return render(request, 'registration/login.html', {'form': form})
                    time.sleep(0.4 * (attempt + 1))

            from audit.models import AuditLog
            AuditLog.log(
                user=user,
                action='login',
                entity_type='User',
                entity_id=user.pk,
                entity_repr=user.username,
                description='ورود به سیستم',
                request=request
            )

            messages.success(request, f'خوش آمدید {user.get_display_name()}!')
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است')
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    """خروج از سیستم"""
    if request.user.is_authenticated:
        # ذخیره لاگ خروج
        from audit.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='logout',
            entity_type='User',
            entity_id=request.user.pk,
            entity_repr=request.user.username,
            description='خروج از سیستم',
            request=request
        )
    
    logout(request)
    messages.info(request, 'شما با موفقیت خارج شدید')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """نمایش و ویرایش پروفایل"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.phone = request.POST.get('phone', '')
        
        # فقط expert می‌تواند expert_name را تغییر دهد
        if user.role == 'expert':
            user.expert_name = request.POST.get('expert_name', '')
        
        # فقط warehouse می‌تواند warehouse را تغییر دهد
        if user.role == 'warehouse':
            user.assigned_warehouse = _resolve_assigned_warehouse(request.POST)
        else:
            user.assigned_warehouse = None
        
        user.save()
        messages.success(request, 'پروفایل با موفقیت به‌روز شد')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'warehouses': Warehouse.get_active_choices(),
    })


@login_required
def change_password_view(request):
    """تغییر رمز عبور"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # جلوگیری از logout
            
            # لاگ تغییر رمز
            from audit.models import AuditLog
            AuditLog.log(
                user=user,
                action='update',
                entity_type='User',
                entity_id=user.pk,
                entity_repr=user.username,
                description='تغییر رمز عبور',
                request=request
            )
            
            messages.success(request, 'رمز عبور با موفقیت تغییر کرد')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'لطفاً خطاها را اصلاح کنید')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


# ============================================
# User Management (فقط برای Superuser)
# ============================================

@superuser_required
def user_list_view(request):
    """لیست کاربران (فقط superuser)"""
    users = User.objects.all().order_by('-date_joined')
    
    # فیلتر
    search = request.GET.get('search', '')
    role = request.GET.get('role', '')
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search)
        )
    
    if role:
        users = users.filter(role=role)
    
    context = {
        'users': users,
        'search': search,
        'role': role,
        'role_choices': User.Role.choices,
    }
    return render(request, 'accounts/user_list.html', context)


@superuser_required
def user_create_view(request):
    """ایجاد کاربر جدید (فقط superuser)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')
        email = request.POST.get('email', '')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        phone = request.POST.get('phone', '')
        expert_name = request.POST.get('expert_name', '')
        assigned_warehouse = None
        requester_scope = ''
        if role == 'warehouse':
            assigned_warehouse = _resolve_assigned_warehouse(request.POST)
            if not assigned_warehouse:
                messages.error(request, 'برای انباردار، انتخاب یا تعریف انبار الزامی است')
                return redirect('accounts:user_create')
        elif role == 'requester':
            requester_scope = (request.POST.get('requester_scope') or '').strip()
            if requester_scope not in dict(User.RequesterScope.choices):
                messages.error(request, 'برای درخواست‌دهنده، انتخاب حوزه الزامی است')
                return redirect('accounts:user_create')
        
        # بررسی تکراری نبودن username
        if User.objects.filter(username=username).exists():
            messages.error(request, 'این نام کاربری قبلاً ثبت شده است')
            return redirect('accounts:user_create')
        
        # ایجاد کاربر
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=role,
            expert_name=expert_name,
            assigned_warehouse=assigned_warehouse,
            requester_scope=requester_scope,
        )
        
        # لاگ
        from audit.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='create',
            entity_type='User',
            entity_id=user.pk,
            entity_repr=user.username,
            description=f'ایجاد کاربر جدید با نقش {user.get_role_display()}',
            request=request
        )
        
        messages.success(request, f'کاربر {username} با موفقیت ایجاد شد')
        return redirect('accounts:user_list')
    
    context = {
        'role_choices': User.Role.choices,
        'requester_scope_choices': User.RequesterScope.choices,
        'warehouses': Warehouse.get_active_choices(),
    }
    return render(request, 'accounts/user_form.html', context)


@superuser_required
def user_edit_view(request, pk):
    """ویرایش کاربر (فقط superuser)"""
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        old_role = user.role
        
        user.username = request.POST.get('username')
        user.email = request.POST.get('email', '')
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.phone = request.POST.get('phone', '')
        user.role = request.POST.get('role')
        user.expert_name = request.POST.get('expert_name', '')
        if user.role == 'warehouse':
            user.assigned_warehouse = _resolve_assigned_warehouse(request.POST)
            user.requester_scope = ''
            if not user.assigned_warehouse:
                messages.error(request, 'برای انباردار، انتخاب یا تعریف انبار الزامی است')
                return redirect('accounts:user_edit', pk=pk)
        elif user.role == 'requester':
            user.assigned_warehouse = None
            user.requester_scope = (request.POST.get('requester_scope') or '').strip()
            if user.requester_scope not in dict(User.RequesterScope.choices):
                messages.error(request, 'برای درخواست‌دهنده، انتخاب حوزه الزامی است')
                return redirect('accounts:user_edit', pk=pk)
        else:
            user.assigned_warehouse = None
            user.requester_scope = ''
        user.is_active = request.POST.get('is_active') == 'on'
        
        # تغییر رمز (اختیاری)
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        user.save()
        
        # لاگ
        from audit.models import AuditLog
        changes = []
        if old_role != user.role:
            changes.append(f'نقش از {old_role} به {user.role}')
        
        description = f'ویرایش کاربر - {", ".join(changes) if changes else "بدون تغییر مهم"}'
        AuditLog.log(
            user=request.user,
            action='update',
            entity_type='User',
            entity_id=user.pk,
            entity_repr=user.username,
            description=description,
            request=request
        )
        
        messages.success(request, f'کاربر {user.username} با موفقیت به‌روز شد')
        return redirect('accounts:user_list')
    
    context = {
        'user_obj': user,
        'role_choices': User.Role.choices,
        'requester_scope_choices': User.RequesterScope.choices,
        'warehouses': Warehouse.get_active_choices(),
    }
    return render(request, 'accounts/user_form.html', context)


@superuser_required
def warehouse_list_view(request):
    """مدیریت انبارهای مقصد"""
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        if not name:
            messages.error(request, 'نام انبار الزامی است')
        elif Warehouse.objects.filter(name=name).exists():
            messages.error(request, 'این انبار قبلاً ثبت شده است')
        else:
            Warehouse.objects.create(
                name=name,
                sort_order=Warehouse.objects.count() + 1,
            )
            messages.success(request, f'انبار «{name}» اضافه شد')
        return redirect('accounts:warehouse_list')

    warehouses = Warehouse.objects.prefetch_related('users').order_by('sort_order', 'name')
    return render(request, 'accounts/warehouse_list.html', {'warehouses': warehouses})


@superuser_required
def category_deadline_list_view(request):
    """تعریف گروه کالایی و مهلت مجاز ثبت درخواست — فقط سوپر یوزر"""
    if request.method == 'POST':
        action = request.POST.get('action', 'save_rule')

        if action == 'create_category':
            name = (request.POST.get('name') or '').strip()
            if not name:
                messages.error(request, 'نام گروه کالایی الزامی است')
            elif ProductCategory.objects.filter(name=name).exists():
                messages.error(request, f'گروه «{name}» قبلاً ثبت شده است')
            else:
                ProductCategory.objects.create(
                    name=name,
                    sort_order=ProductCategory.objects.count() + 1,
                    is_active=True,
                )
                messages.success(request, f'گروه کالایی «{name}» اضافه شد')
            return redirect('accounts:category_deadline_list')

        category = get_object_or_404(ProductCategory, pk=request.POST.get('category_id'))
        allowed_days = (request.POST.get('allowed_days') or '').strip()
        weekday_values = request.POST.getlist('weekdays')
        allowed_weekdays = ','.join(sorted(set(w for w in weekday_values if w.isdigit() and 0 <= int(w) <= 6), key=int))
        code_prefixes = (request.POST.get('code_prefixes') or '').strip()
        is_active = request.POST.get('is_active') == 'on'
        notes = (request.POST.get('notes') or '').strip()
        try:
            payment_lead_days = max(1, min(int(request.POST.get('payment_lead_days') or 7), 365))
        except (TypeError, ValueError):
            payment_lead_days = 7

        if not allowed_days and not allowed_weekdays:
            messages.error(request, 'حداقل یک «روز ماه» یا یک «روز هفته» انتخاب کنید')
            return redirect('accounts:category_deadline_list')

        category.code_prefixes = code_prefixes
        category.payment_lead_days = payment_lead_days
        category.save(update_fields=['code_prefixes', 'payment_lead_days'])

        rule, _ = CategoryDeadlineRule.objects.get_or_create(category=category)
        rule.allowed_days = allowed_days
        rule.allowed_weekdays = allowed_weekdays
        rule.rule_type = CategoryDeadlineRule.RuleType.MONTH_DAYS
        rule.is_active = is_active
        rule.notes = notes
        rule.save()

        from services.deadline_service import DeadlineService
        refresh = DeadlineService.refresh_all_categories_and_deadlines()
        messages.success(
            request,
            f'قانون مهلت «{category.name}» ذخیره شد. '
            f'تخصیص گروه: {refresh["from_code_prefix"]} از کد، {refresh["from_inquiries"]} از استعلام. '
            f'انحراف: {refresh["deadline_updated"]} پرونده به‌روز شد.',
        )
        return redirect('accounts:category_deadline_list')

    categories = (
        ProductCategory.objects
        .filter(is_active=True)
        .select_related('deadline_rule')
        .order_by('sort_order', 'name')
    )
    return render(request, 'accounts/category_deadline_list.html', {
        'categories': categories,
        'weekday_choices': CategoryDeadlineRule.JALALI_WEEKDAY_CHOICES,
    })


@superuser_required
@require_http_methods(["POST"])
def user_delete_view(request, pk):
    """حذف کاربر (فقط superuser)"""
    user = get_object_or_404(User, pk=pk)
    
    # جلوگیری از حذف خود
    if user.pk == request.user.pk:
        messages.error(request, 'نمی‌توانید خودتان را حذف کنید')
        return redirect('accounts:user_list')
    
    # لاگ قبل از حذف
    from audit.models import AuditLog
    AuditLog.log(
        user=request.user,
        action='delete',
        entity_type='User',
        entity_id=user.pk,
        entity_repr=user.username,
        description=f'حذف کاربر {user.username}',
        request=request
    )
    
    username = user.username
    user.delete()
    
    messages.success(request, f'کاربر {username} با موفقیت حذف شد')
    return redirect('accounts:user_list')


@superuser_required
@require_http_methods(["POST"])
def user_toggle_active_view(request, pk):
    """فعال/غیرفعال کردن کاربر (فقط superuser)"""
    user = get_object_or_404(User, pk=pk)
    
    # جلوگیری از غیرفعال کردن خود
    if user.pk == request.user.pk:
        return JsonResponse({'success': False, 'error': 'نمی‌توانید خودتان را غیرفعال کنید'})
    
    user.is_active = not user.is_active
    user.save()
    
    # لاگ
    from audit.models import AuditLog
    AuditLog.log(
        user=request.user,
        action='update',
        entity_type='User',
        entity_id=user.pk,
        entity_repr=user.username,
        description=f'{"فعال" if user.is_active else "غیرفعال"} کردن کاربر',
        request=request
    )
    
    return JsonResponse({
        'success': True,
        'is_active': user.is_active,
        'message': f'کاربر {user.username} {"فعال" if user.is_active else "غیرفعال"} شد'
    })