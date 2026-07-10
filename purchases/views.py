from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Prefetch
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.conf import settings
from pathlib import Path
import shutil
from datetime import datetime

# Import permissions
from accounts.permissions import (
    admin_required,
    superuser_required,
    expert_required,
    is_admin_or_above_check,
)
from accounts.warehouse_access import is_warehouse_user, warehouse_can_view_purchase
from accounts.requester_access import (
    is_requester_user,
    filter_purchases_for_requester,
    requester_can_view_purchase,
    get_requester_scope_label,
)
from accounts.expert_access import (
    is_pure_expert_user,
    filter_purchases_for_expert,
    expert_can_view_purchase,
    get_expert_identity,
)


def _redirect_if_requester(request):
    if is_requester_user(request.user):
        messages.info(request, 'فقط گردش کار درخواست‌های واحد شما در بخش خرید قابل مشاهده است.')
        return redirect('purchases:list')
    return None

# Import models
from .models import Purchase, IGNORE_PHRASES
from .forms import SuperuserPurchaseEditForm
from inquiries.models import Inquiry
from orders.models import Order
from deliveries.models import Delivery

# Import services
from services.export_service import ExportService
from services.excel_importer import ExcelImporter
from services.excel_template_service import ExcelTemplateService
from services.excel_full_export_service import ExcelFullExportService
from services.excel_import_progress import ExcelImportProgress
from services.excel_upload_job import start_excel_upload_job


# ============================================================================
# Dashboard View
# ============================================================================

@login_required
def dashboard(request):
    """داشبورد اصلی با آمار تحلیلی"""
    if is_warehouse_user(request.user):
        from notifications.models import Notification
        from accounts.warehouse_access import filter_deliveries_for_warehouse

        my_deliveries = (
            filter_deliveries_for_warehouse(
                Delivery.objects.select_related('order', 'purchase', 'created_by'),
                request.user,
            )
            .filter(created_by=request.user)
            .order_by('-pk')[:15]
        )
        delivery_count = filter_deliveries_for_warehouse(
            Delivery.objects.all(), request.user
        ).count()
        recent_notifications = (
            Notification.objects.filter(user=request.user)
            .order_by('-created_at')[:12]
        )
        unread_notifications = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()

        return render(request, 'dashboard_warehouse.html', {
            'my_deliveries': my_deliveries,
            'delivery_count': delivery_count,
            'recent_notifications': recent_notifications,
            'unread_notifications': unread_notifications,
            'warehouse_name': request.user.warehouse or '—',
        })

    if is_requester_user(request.user):
        scoped = filter_purchases_for_requester(Purchase.objects.all(), request.user)
        status_counts = {}
        for code, label in Purchase.CurrentStatus.choices:
            count = scoped.filter(current_status=code).count()
            if count:
                status_counts[label] = count
        recent = scoped.order_by('-purchase_number', '-pk')[:12]
        return render(request, 'dashboard_requester.html', {
            'total_count': scoped.count(),
            'status_counts': status_counts,
            'recent_purchases': recent,
            'scope_label': get_requester_scope_label(request.user),
        })

    if is_pure_expert_user(request.user):
        from notifications.models import Notification
        from accounts.expert_access import filter_inquiries_for_expert

        scoped = filter_purchases_for_expert(Purchase.objects.all(), request.user)
        ignore_q = Q()
        for phrase in IGNORE_PHRASES:
            ignore_q |= Q(payment_request_number__icontains=phrase)
            ignore_q |= Q(payment_registration_date__icontains=phrase)

        pending_inquiry = scoped.filter(
            Q(inquiry_number='') | Q(inquiry_number__isnull=True)
        ).filter(
            Q(order_number='') | Q(order_number__isnull=True)
        ).filter(
            Q(delivery_number='') | Q(delivery_number__isnull=True)
        ).filter(
            Q(payment_request_number='') |
            Q(payment_request_number__isnull=True) |
            ignore_q
        ).count()

        status_colors_map = {
            'در انتظار استعلام': '#f59e0b',
            'استعلام صادر شده': '#3b82f6',
            'دستور خرید صادر شده': '#8b5cf6',
            'سفارش صادر شده': '#06b6d4',
            'سفارش متوقف شده': '#ef4444',
            'در انتظار پرداخت': '#ec4899',
            'پرداخت شده': '#10b981',
            'تحویل شده': '#059669',
        }
        status_stats = {}
        for status_code, status_name in Purchase.CurrentStatus.choices:
            count = scoped.filter(current_status=status_code).count()
            if count > 0:
                status_stats[status_name] = {
                    'count': count,
                    'color': status_colors_map.get(status_name, '#94a3b8'),
                }

        inquiry_count = filter_inquiries_for_expert(
            Inquiry.objects.all(), request.user
        ).count()
        stopped_count = scoped.filter(current_status='order_stopped').count()
        recent_notifications = (
            Notification.objects.filter(user=request.user)
            .order_by('-created_at')[:8]
        )

        import json
        return render(request, 'dashboard_expert.html', {
            'total_count': scoped.count(),
            'pending_inquiry': pending_inquiry,
            'inquiry_count': inquiry_count,
            'stopped_count': stopped_count,
            'recent_purchases': scoped.order_by('-purchase_number', '-pk')[:12],
            'expert_label': get_expert_identity(request.user) or request.user.username,
            'recent_notifications': recent_notifications,
            'status_labels': json.dumps(list(status_stats.keys()), ensure_ascii=False),
            'status_counts': json.dumps([s['count'] for s in status_stats.values()]),
            'status_colors': json.dumps([s['color'] for s in status_stats.values()]),
        })

    total = Purchase.objects.count()
    
    # آمار وضعیت‌ها برای نمودار
    status_stats = {}
    status_colors = {
        'در انتظار استعلام': '#f59e0b',
        'استعلام صادر شده': '#3b82f6',
        'دستور خرید صادر شده': '#8b5cf6',
        'سفارش صادر شده': '#06b6d4',
        'سفارش متوقف شده': '#ef4444',
        'در انتظار پرداخت': '#ec4899',
        'پرداخت شده': '#10b981',
        'تحویل شده': '#059669',
    }
    
    for status_code, status_name in Purchase.CurrentStatus.choices:
        count = Purchase.objects.filter(current_status=status_code).count()
        if count > 0:
            status_stats[status_name] = {
                'count': count,
                'color': status_colors.get(status_name, '#94a3b8'),
            }
    
    # آمار انحراف مهلت سفارش به تفکیک کارشناس (ستون O در برابر AB)
    from services.order_deadline_service import OrderDeadlineService

    expert_order_stats = [
        row for row in OrderDeadlineService.get_summary_by_expert()
        if row['evaluated'] > 0
    ]
    expert_order_stats.sort(
        key=lambda row: (-row['deviated'], -row['rate'], -row['evaluated'], row['name'])
    )
    expert_order_stats = expert_order_stats[:8]
    
    # آخرین خریدها
    recent_purchases = Purchase.objects.select_related().order_by('-pk')[:10]
    
    # نیازمند اقدام (با منطق هوشمند)
    ignore_q = Q()
    for phrase in IGNORE_PHRASES:
        ignore_q |= Q(payment_request_number__icontains=phrase)
        ignore_q |= Q(payment_registration_date__icontains=phrase)
    
    pending_inquiry = Purchase.objects.filter(
        Q(inquiry_number='') | Q(inquiry_number__isnull=True)
    ).filter(
        Q(order_number='') | Q(order_number__isnull=True)
    ).filter(
        Q(delivery_number='') | Q(delivery_number__isnull=True)
    ).filter(
        Q(payment_request_number='') |
        Q(payment_request_number__isnull=True) |
        ignore_q
    ).count()
    
    from services.order_amount_service import OrderAmountService

    financial = {
        'total_order_value': OrderAmountService.sum_unique_amounts(Purchase.objects.all(), 'order_total'),
        'total_invoice_value': OrderAmountService.sum_unique_amounts(Purchase.objects.all(), 'invoice_total'),
    }
    
    # تعداد استعلام‌ها و دستورات
    inquiry_count = Inquiry.objects.count()
    order_count = Order.objects.count()
    delivery_count = Delivery.objects.count()

    from services.deadline_service import DeadlineService
    from services.category_amount_service import CategoryAmountService
    from services.product_amount_service import ProductAmountService
    from services.payment_lead_service import PaymentLeadService

    deadline_overall = DeadlineService.get_overall_summary()
    deadline_by_category = [
        c for c in DeadlineService.get_summary_by_category() if c['evaluated'] > 0
    ]

    show_report_charts = is_admin_or_above_check(request.user)
    report_chart_data = {}
    if show_report_charts:

        base_qs = Purchase.objects.all()
        cat_summary = CategoryAmountService.get_summary(base_qs)
        top_categories = [c for c in cat_summary['categories'] if c['amount'] > 0][:8]
        prod_summary = ProductAmountService.get_summary(base_qs)
        top_products = prod_summary['products'][:8]
        order_dl_summary = OrderDeadlineService.get_overall_summary(base_qs)
        payment_lead_summary = PaymentLeadService.get_overall_summary(base_qs)

        report_chart_data = {
            'category_labels': [c['name'] for c in top_categories],
            'category_amounts': [c['amount'] for c in top_categories],
            'product_labels': [
                (p['product_title'] or p['product_code'])[:45] for p in top_products
            ],
            'product_amounts': [p['amount'] for p in top_products],
            'order_dl_on_time': order_dl_summary['on_time'],
            'order_dl_deviated': order_dl_summary['deviated'],
            'payment_on_time': payment_lead_summary['on_time'],
            'payment_deviated': payment_lead_summary['deviated'],
        }
    
    # آمار نوع خرید
    type_stats = list(
        Purchase.objects.exclude(purchase_type='')
        .values('purchase_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    context = {
        'total': total,
        'status_stats': status_stats,
        'status_labels': list(status_stats.keys()),
        'status_counts': [s['count'] for s in status_stats.values()],
        'status_colors': [s['color'] for s in status_stats.values()],
        'expert_order_stats': expert_order_stats,
        'expert_names': [e['name'] for e in expert_order_stats],
        'expert_on_time': [e['on_time'] for e in expert_order_stats],
        'expert_deviated': [e['deviated'] for e in expert_order_stats],
        'expert_rates': [e['rate'] for e in expert_order_stats],
        'type_stats': type_stats,
        'type_labels': [t['purchase_type'] for t in type_stats],
        'type_counts': [t['count'] for t in type_stats],
        'recent_purchases': recent_purchases,
        'pending_inquiry': pending_inquiry,
        'financial': financial,
        'inquiry_count': inquiry_count,
        'order_count': order_count,
        'delivery_count': delivery_count,
        'deadline_overall': deadline_overall,
        'deadline_by_category': deadline_by_category,
        'show_report_charts': show_report_charts,
        **report_chart_data,
    }
    return render(request, 'dashboard.html', context)


# ============================================================================
# Purchase List View
# ============================================================================

@login_required
def purchase_list(request):
    """لیست درخواست‌های خرید با آمار KPI"""
    if is_warehouse_user(request.user):
        messages.info(request, 'انباردار از داشبورد انبار، اعلان‌ها و رسیدهای تحویل استفاده می‌کند.')
        return redirect('deliveries:list')

    queryset = Purchase.objects.all()
    is_requester = is_requester_user(request.user)
    is_expert_view = is_pure_expert_user(request.user)
    if is_requester:
        queryset = filter_purchases_for_requester(queryset, request.user)
    elif is_expert_view:
        queryset = filter_purchases_for_expert(queryset, request.user)
    
    # ساخت ignore_q برای مقادیر "در انتظار..."
    ignore_q = Q()
    for phrase in IGNORE_PHRASES:
        ignore_q |= Q(payment_request_number__icontains=phrase)
        ignore_q |= Q(payment_registration_date__icontains=phrase)
    
    # آمار KPI (روی دیتاست قابل مشاهده قبل از فیلتر جستجو)
    if is_requester:
        stats_base = filter_purchases_for_requester(Purchase.objects.all(), request.user)
    elif is_expert_view:
        stats_base = filter_purchases_for_expert(Purchase.objects.all(), request.user)
    else:
        stats_base = Purchase.objects.all()
    all_stats = stats_base.aggregate(
        pending=Count('id', filter=(
            (Q(inquiry_number='') | Q(inquiry_number__isnull=True)) &
            (Q(order_number='') | Q(order_number__isnull=True)) &
            (Q(delivery_number='') | Q(delivery_number__isnull=True)) &
            (Q(payment_request_number='') | Q(payment_request_number__isnull=True) | ignore_q)
        )),
        inquiry=Count('id', filter=~Q(inquiry_number='')),
        paid=Count('id', filter=Q(current_status='paid')),
        delivered=Count('id', filter=Q(current_status='delivered')),
    )
    
    # فیلترها
    search = request.GET.get('search', '')
    expert = request.GET.get('expert', '')
    status = request.GET.get('status', '')
    filter_type = request.GET.get('filter', '')
    
    if search:
        from services.search_service import SearchService
        queryset = SearchService.filter_purchases(queryset, search)
    if expert:
        queryset = queryset.filter(expert_name__icontains=expert)
    if status:
        queryset = queryset.filter(current_status=status)
    
    if filter_type == 'no_inquiry':
        queryset = queryset.filter(
            Q(inquiry_number='') | Q(inquiry_number__isnull=True)
        ).filter(
            Q(order_number='') | Q(order_number__isnull=True)
        ).filter(
            Q(delivery_number='') | Q(delivery_number__isnull=True)
        ).filter(
            Q(payment_request_number='') |
            Q(payment_request_number__isnull=True) |
            ignore_q
        ).filter(
            Q(payment_registration_date='') |
            Q(payment_registration_date__isnull=True) |
            ignore_q
        )
    elif filter_type == 'inquiry':
        queryset = queryset.exclude(
            Q(inquiry_number='') | Q(inquiry_number__isnull=True)
        )
    elif filter_type == 'delivered':
        queryset = queryset.filter(current_status='delivered')
    elif filter_type == 'paid':
        queryset = queryset.filter(current_status='paid')
    
    queryset = queryset.order_by('-purchase_number', 'line_number')
    
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    experts_list = stats_base.exclude(expert_name='').values_list(
        'expert_name', flat=True
    ).distinct().order_by('expert_name')
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'expert': expert,
        'status': status,
        'filter_type': filter_type,
        'experts_list': experts_list,
        'status_choices': Purchase.CurrentStatus.choices,
        'pending_count': all_stats['pending'],
        'inquiry_count': all_stats['inquiry'],
        'paid_count': all_stats['paid'],
        'delivered_count': all_stats['delivered'],
        'is_requester_view': is_requester,
        'is_expert_view': is_expert_view,
        'scope_label': get_requester_scope_label(request.user) if is_requester else '',
        'expert_label': get_expert_identity(request.user) if is_expert_view else '',
    }
    return render(request, 'purchases/list.html', context)


# ============================================================================
# Purchase Detail View
# ============================================================================

@login_required
def purchase_detail(request, pk):
    """جزئیات یک درخواست خرید"""
    purchase = get_object_or_404(Purchase, pk=pk)

    is_requester = is_requester_user(request.user)
    is_expert_view = is_pure_expert_user(request.user)

    if is_expert_view and not expert_can_view_purchase(purchase, request.user):
        messages.error(request, 'این پرونده به کارشناس دیگری ارجاع شده است.')
        return redirect('purchases:list')

    if is_requester:
        if not requester_can_view_purchase(purchase, request.user):
            messages.error(request, 'این پرونده در حوزه واحد شما نیست.')
            return redirect('purchases:list')

    if is_warehouse_user(request.user):
        if not warehouse_can_view_purchase(purchase, request.user):
            messages.error(request, 'انباردار فقط پرونده‌های مرتبط با انبار خود را می‌بیند.')
            return redirect('deliveries:list')
        related_order = Order.objects.filter(purchase=purchase).first()
        if not related_order and purchase.order_number:
            related_order = Order.objects.filter(order_number=purchase.order_number).first()
        if related_order:
            return redirect('orders:detail', pk=related_order.pk)
        return redirect('deliveries:list')

    # دریافت سایر خط‌های همین خرید
    sibling_lines = Purchase.objects.filter(
        purchase_number=purchase.purchase_number
    ).order_by('line_number')

    related_inquiry = None
    if purchase.inquiry_number:
        related_inquiry = Inquiry.objects.filter(
            inquiry_number=purchase.inquiry_number
        ).prefetch_related('pre_invoices__lines').first()

    related_order = purchase.orders.first()
    if not related_order and purchase.order_number:
        related_order = Order.objects.filter(order_number=purchase.order_number).first()
    
    from services.deadline_service import DeadlineService
    deadline_detail = DeadlineService.get_evaluation_detail(purchase)

    context = {
        'purchase': purchase,
        'sibling_lines': sibling_lines,
        'related_inquiry': related_inquiry,
        'related_order': related_order,
        'deadline_detail': deadline_detail,
        'can_issue_order': (
            not is_requester
            and request.user.can_create_order
            and purchase.can_issue_order
            and not related_order
        ),
        'is_requester_view': is_requester,
        'is_expert_view': is_expert_view,
    }
    
    return render(request, 'purchases/detail.html', context)


PURCHASE_EDIT_FIELD_SECTIONS = [
    ('اطلاعات درخواست', [
        'base_number', 'request_date', 'purchase_date', 'supply_unit', 'requester',
        'status', 'required_date', 'expert_name', 'description',
    ]),
    ('مشخصات کالا', ['product_code', 'product_title', 'unit', 'quantity']),
    ('استعلام', [
        'inquiry_number', 'inquiry_received_date', 'inquiry_deadline',
        'inquiry_deadline_2', 'purchase_type',
    ]),
    ('پیش‌فاکتور', ['preinvoice_number', 'preinvoice_price', 'preinvoice_total']),
    ('دستور خرید', ['order_number', 'order_date']),
    ('سفارش', [
        'order_request_number', 'order_request_status', 'order_request_date',
        'order_total', 'advance_payment', 'deductions',
    ]),
    ('تحویل', ['delivered_quantity', 'delivery_number', 'delivery_date', 'supplier']),
    ('فاکتور', ['invoice_price', 'invoice_number', 'invoice_total']),
    ('پرداخت', [
        'payment_request_amount', 'payment_request_number',
        'payment_registration_date', 'payment_completion_date',
    ]),
]


def _build_purchase_edit_sections(form):
    """تبدیل نام فیلدها به BoundField برای رندر مستقیم در قالب"""
    sections = []
    for title, field_names in PURCHASE_EDIT_FIELD_SECTIONS:
        fields = [form[name] for name in field_names if name in form.fields]
        sections.append((title, fields))
    return sections


@login_required
@superuser_required
def purchase_edit(request, pk):
    """ویرایش و تکمیل فیلدهای خرید — فقط سوپر یوزر"""
    purchase = get_object_or_404(Purchase, pk=pk)

    if request.method == 'POST':
        form = SuperuserPurchaseEditForm(request.POST, instance=purchase)
        if form.is_valid():
            purchase = form.save()
            ExcelImporter.sync_inquiries_from_purchases()

            from audit.models import AuditLog
            AuditLog.log(
                user=request.user,
                action='update',
                entity_type='Purchase',
                entity_id=str(purchase.pk),
                entity_repr=f'خرید {purchase.purchase_number}',
                description='ویرایش و تکمیل فیلدهای خرید توسط سوپر یوزر',
                request=request,
            )
            messages.success(request, 'اطلاعات خرید با موفقیت ذخیره شد.')
            return redirect('purchases:detail', pk=pk)
    else:
        form = SuperuserPurchaseEditForm(instance=purchase)

    return render(request, 'purchases/edit.html', {
        'purchase': purchase,
        'form': form,
        'field_sections': _build_purchase_edit_sections(form),
    })


# ============================================================================
# Export Excel View
# ============================================================================

@login_required
def export_purchases_excel(request):
    """خروجی اکسل با فیلترهای جاری"""
    blocked = _redirect_if_requester(request)
    if blocked:
        return blocked
    queryset = Purchase.objects.all()
    
    # ساخت ignore_q برای مقادیر "در انتظار..."
    ignore_q = Q()
    for phrase in IGNORE_PHRASES:
        ignore_q |= Q(payment_request_number__icontains=phrase)
        ignore_q |= Q(payment_registration_date__icontains=phrase)
    
    # اعمال همان فیلترهای لیست
    search = request.GET.get('search', '')
    expert = request.GET.get('expert', '')
    status = request.GET.get('status', '')
    filter_type = request.GET.get('filter', '')
    
    if search:
        from services.search_service import SearchService
        queryset = SearchService.filter_purchases(queryset, search)
    if expert:
        queryset = queryset.filter(expert_name__icontains=expert)
    if status:
        queryset = queryset.filter(current_status=status)
    
    if filter_type == 'no_inquiry':
        queryset = queryset.filter(
            Q(inquiry_number='') | Q(inquiry_number__isnull=True)
        ).filter(
            Q(order_number='') | Q(order_number__isnull=True)
        ).filter(
            Q(delivery_number='') | Q(delivery_number__isnull=True)
        ).filter(
            Q(payment_request_number='') |
            Q(payment_request_number__isnull=True) |
            ignore_q
        )
    elif filter_type == 'delivered':
        queryset = queryset.filter(current_status='delivered')
    elif filter_type == 'paid':
        queryset = queryset.filter(current_status='paid')
    
    content, filename = ExportService.export_purchases(queryset)
    
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================================================
# Excel Upload — import/update + export enriched panel Excel
# ============================================================================

def _serialize_sync_stats(stats: dict) -> dict:
    if not stats:
        return {}
    return {
        k: v for k, v in stats.items()
        if isinstance(v, (str, int, float, bool, list, dict, type(None)))
    }


@login_required
@admin_required
def download_excel_template(request):
    """دانلود قالب اکسل ورودی — داینامیک از اسکیمای importer"""
    from urllib.parse import quote

    content, filename, version = ExcelTemplateService.generate_template_bytes()
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    ascii_name = f'purchase_import_template_{version}.xlsx'
    response['Content-Disposition'] = (
        f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    )
    return response


@login_required
@admin_required
def download_full_excel_export(request):
    """دانلود اکسل خروجی کامل — همه رکوردها با قالب یکپارچه ورودی/خروجی"""
    from urllib.parse import quote

    content, filename, row_count = ExcelFullExportService.generate_export_bytes()
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ascii_name = f'purchase_full_export_{timestamp}.xlsx'
    response['Content-Disposition'] = (
        f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    )

    from audit.models import AuditLog
    AuditLog.log(
        user=request.user,
        action='export',
        entity_type='خروجی اکسل کامل',
        entity_id=timestamp,
        entity_repr=filename,
        description=f'دانلود خروجی کامل: {row_count} ردیف',
        request=request,
    )
    return response


def _validate_excel_upload_file(excel_file):
    if not excel_file:
        return 'فایل اکسل انتخاب نشده است.'
    filename = (excel_file.name or '').lower()
    if not filename.endswith(('.xlsx', '.xlsm')):
        return 'فقط فایل‌های Excel (.xlsx) پذیرفته می‌شوند.'
    if excel_file.size > 50 * 1024 * 1024:
        return 'حداکثر حجم فایل ۵۰ مگابایت است.'
    return None


@login_required
@admin_required
def upload_excel(request):
    """صفحه آپلود اکسل با پیشرفت real-time"""
    return render(request, 'purchases/upload_excel.html', {
        'template_version': ExcelTemplateService.get_schema_version(),
        'template_column_count': len(ExcelImporter.get_import_columns()),
    })


@login_required
@admin_required
@require_POST
def upload_excel_start(request):
    """شروع آپلود — ذخیره فایل و اجرای import در پس‌زمینه"""
    excel_file = request.FILES.get('excel_file')
    validation_error = _validate_excel_upload_file(excel_file)
    if validation_error:
        return JsonResponse({'success': False, 'error': validation_error}, status=400)

    upload_dir = settings.MEDIA_ROOT / 'excel_uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)

    import uuid

    token = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_uid = uuid.uuid4().hex[:8]
    from services.excel_file_utils import get_panel_excel_path

    incoming_path = upload_dir / f'incoming_{token}_{file_uid}.xlsx'
    panel_path = get_panel_excel_path()

    try:
        with open(incoming_path, 'wb') as dest:
            for chunk in excel_file.chunks():
                dest.write(chunk)

        progress = start_excel_upload_job(
            user_id=request.user.pk,
            incoming_path=incoming_path,
            panel_path=panel_path,
            token=token,
            original_name=excel_file.name,
        )

        return JsonResponse({
            'success': True,
            'job_id': progress.job_id,
            'token': token,
            'status_url': reverse('purchases:upload_excel_status', args=[progress.job_id]),
        })
    except Exception as e:
        if incoming_path.exists():
            incoming_path.unlink(missing_ok=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@admin_required
def upload_excel_status(request, job_id):
    """وضعیت پیشرفت آپلود"""
    progress = ExcelImportProgress.load(job_id, request.user.pk)
    if not progress:
        return JsonResponse({'success': False, 'error': 'کار پردازش یافت نشد.'}, status=404)

    data = progress.to_dict()
    payload = {
        'success': True,
        'status': data.get('status'),
        'phase': data.get('phase'),
        'phase_label': data.get('phase_label'),
        'percent': data.get('percent', 0),
        'message': data.get('message', ''),
        'logs': data.get('logs', []),
        'error': data.get('error'),
        'import_errors': data.get('import_errors', []),
        'result': data.get('result'),
        'token': data.get('token'),
        'original_name': data.get('original_name'),
    }
    return JsonResponse(payload)


@login_required
@admin_required
def download_uploaded_excel(request, token):
    """دانلود اکسل غنی‌شده با جزئیات پنل"""
    if not token or not token.replace('_', '').isdigit():
        messages.error(request, 'لینک دانلود نامعتبر است.')
        return redirect('purchases:upload_excel')

    from services.excel_file_utils import read_file_bytes, resolve_panel_export_path

    panel_path = resolve_panel_export_path(token)
    if not panel_path:
        messages.error(request, 'فایل خروجی یافت نشد یا منقضی شده است.')
        return redirect('purchases:upload_excel')

    content = read_file_bytes(panel_path)

    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="tadarokat_panel_{token}.xlsx"'
    return response


# ============================================================================
# Sync & Recalculate View (برای دکمه داشبورد)
# ============================================================================

@login_required
@admin_required
@require_POST
def sync_and_recalculate(request):
    """
    Sync اکسل و محاسبه مجدد وضعیت‌ها
    این تابع توسط دکمه "Sync & Recalculate" در داشبورد فراخوانی می‌شود
    """
    try:
        # پیدا کردن فایل اکسل
        file_path = None
        from services.excel_file_utils import get_input_excel_path, get_panel_excel_path

        candidates = [
            get_input_excel_path(),
            Path(r'\\server\share\tadarokat\input.xlsx'),  # مسیر شبکه
        ]
        
        for cand in candidates:
            if cand.exists():
                file_path = cand
                break
        
        sync_stats = None
        excel_export_stats = None
        if file_path:
            # اجرای sync هوشمند (شامل محاسبه مهلت و بازنویسی اکسل)
            sync_stats = ExcelImporter.import_from_excel(
                str(file_path),
                user=request.user,
                full_sync=False,
                export_path=str(get_panel_excel_path()),
            )
            excel_export_stats = (sync_stats or {}).get('excel_export')
        else:
            # اگر فایل اکسل نبود، فقط recalculate کن
            sync_stats = {
                'created': 0,
                'updated': 0,
                'workflow_preserved': 0,
                'skipped': 0,
                'errors': [],
                'deliveries_created': 0,
                'deliveries_skipped': 0,
            }
            from services.deadline_service import DeadlineService
            sync_stats['deadline_deviated_updated'] = DeadlineService.recalculate_all()

        # همگام‌سازی استعلام‌های اکسل با جدول Inquiry (همیشه)
        inquiry_sync = ExcelImporter.sync_inquiries_from_purchases()
        sync_stats['inquiries_created'] = inquiry_sync.get('inquiries_created', 0)
        sync_stats['inquiries_skipped'] = inquiry_sync.get('inquiries_skipped', 0)
        sync_stats['errors'].extend(inquiry_sync.get('inquiries_errors', []))

        # همگام‌سازی دستورات خرید از اکسل (همیشه)
        order_sync = ExcelImporter.sync_orders_from_purchases()
        sync_stats['orders_created'] = order_sync.get('orders_created', 0)
        sync_stats['orders_skipped'] = order_sync.get('orders_skipped', 0)
        sync_stats['errors'].extend(order_sync.get('orders_errors', []))
        
        # محاسبه مجدد وضعیت‌ها (در صورتی که در sync انجام نشده باشد)
        status_updated = 0
        purchases_to_update = []
        
        for purchase in Purchase.objects.all():
            old_status = purchase.current_status
            new_status = purchase.calculate_current_status()
            
            if old_status != new_status:
                purchase.current_status = new_status
                purchases_to_update.append(purchase)
                status_updated += 1
        
        # استفاده از bulk_update برای performance بهتر
        if purchases_to_update:
            Purchase.objects.bulk_update(
                purchases_to_update, 
                ['current_status'],
                batch_size=500
            )
        
        # ثبت لاگ
        from audit.models import AuditLog
        AuditLog.log(
            user=request.user,
            action='update',
            entity_type='همگام‌سازی',
            entity_id='excel',
            entity_repr='همگام‌سازی اکسل و محاسبه مجدد',
            description=f'همگام‌سازی اکسل انجام شد: {sync_stats.get("created", 0)} ایجاد، {sync_stats.get("updated", 0)} به‌روزرسانی، {status_updated} وضعیت تغییر کرد',
            request=request
        )
        
        # فقط فیلدهای قابل serialize در پاسخ API
        safe_sync_stats = _serialize_sync_stats(sync_stats)

        export_msg = ''
        if excel_export_stats:
            export_msg = (
                f" — اکسل: {excel_export_stats.get('rows_updated', 0)} به‌روز، "
                f"{excel_export_stats.get('rows_appended', 0)} ردیف جدید"
            )

        return JsonResponse({
            'success': True,
            'message': f'همگام‌سازی و محاسبه مجدد با موفقیت انجام شد{export_msg}',
            'sync_stats': safe_sync_stats,
            'status_updated': status_updated,
            'excel_export': excel_export_stats,
        })
    
    except FileNotFoundError as e:
        return JsonResponse({
            'success': False,
            'error': f'فایل اکسل یافت نشد: {str(e)}'
        }, status=404)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'خطا در sync: {str(e)}'
        }, status=500)