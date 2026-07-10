from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.db.models.functions import Substr
from purchases.models import Purchase
from orders.models import Order
from deliveries.models import Delivery
from inquiries.models import Inquiry
from accounts.permissions import admin_required
from services.stage_analytics import (
    aggregate_stage_averages,
    STAGE_DEFINITIONS,
)
from services.data_validation import validate_random_rows
from services.deadline_service import DeadlineService
from services.order_deadline_service import OrderDeadlineService
from services.date_filter import (
    parse_filter_params,
    apply_report_filters,
    describe_active_filter,
    get_filter_warning,
    SEASONS,
)
from services.report_export_service import ReportExportService
from services.category_amount_service import CategoryAmountService
from services.payment_lead_service import PaymentLeadService, DAY_BUCKETS
from services.product_amount_service import ProductAmountService
from services.financial_loss_service import FinancialLossService
from services.order_amount_service import OrderAmountService
from services.purchase_tree_report_service import PurchaseTreeReportService


def _parse_category_drilldown(request, page_param='cat_page', page_size=100):
    """پارامترهای drill-down کارت گروه کالایی: cat + cat_kind"""
    category = (request.GET.get('cat') or '').strip()
    cat_kind = (request.GET.get('cat_kind') or '').strip()
    if not category or cat_kind not in ('request', 'order', 'payment'):
        return None, None, None, None, None

    try:
        page_num = max(int(request.GET.get(page_param, 1)), 1)
    except (TypeError, ValueError):
        page_num = 1
    offset = (page_num - 1) * page_size
    return category, cat_kind, page_num, offset, page_size


def _build_drilldown_pagination_query(request, page_param='cat_page'):
    query_params = request.GET.copy()
    for key in (page_param, 'req_page', 'order_page', 'page'):
        query_params.pop(key, None)
    return query_params.urlencode()


def _serve_excel(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@admin_required
def purchase_report(request):
    """گزارش جامع خرید"""
    queryset = Purchase.objects.all()

    total_purchases = queryset.count()
    total_value = {
        'order_total': OrderAmountService.sum_unique_amounts(queryset, 'order_total'),
        'invoice_total': OrderAmountService.sum_unique_amounts(queryset, 'invoice_total'),
    }

    status_stats = {}
    for status_code, status_name in Purchase.CurrentStatus.choices:
        count = queryset.filter(current_status=status_code).count()
        if count > 0:
            status_stats[status_name] = count

    monthly_stats = list(
        queryset
        .exclude(purchase_date='')
        .exclude(purchase_date__isnull=True)
        .annotate(month=Substr('purchase_date', 1, 7))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    for m in monthly_stats:
        if m['month']:
            m['month'] = m['month'].rstrip('/')

    type_stats = list(
        queryset.exclude(purchase_type='')
        .values('purchase_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    category_stats = list(
        queryset.exclude(product_category='')
        .values('product_category')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    completed = queryset.filter(
        Q(current_status='delivered') | Q(current_status='paid')
    ).count()
    completion_rate = round((completed / total_purchases * 100), 1) if total_purchases > 0 else 0

    deadline_deviated_count = queryset.filter(deadline_deviated=True).count()
    deadline_on_time_count = queryset.filter(
        product_category__gt='',
        deadline_deviated=False,
    ).count()

    OrderDeadlineService.recalculate_all()
    order_deadline_summary = OrderDeadlineService.get_overall_summary()

    stage_averages = aggregate_stage_averages(queryset)

    context = {
        'total_purchases': total_purchases,
        'total_value': total_value,
        'status_stats': status_stats,
        'monthly_stats': monthly_stats,
        'type_stats': type_stats,
        'category_stats': category_stats,
        'deadline_deviated_count': deadline_deviated_count,
        'deadline_on_time_count': deadline_on_time_count,
        'order_deadline_summary': order_deadline_summary,
        'completion_rate': completion_rate,
        'stage_averages': stage_averages,
        'stage_definitions': STAGE_DEFINITIONS,
        'inquiry_count': Inquiry.objects.count(),
        'order_count': Order.objects.count(),
        'delivery_count': Delivery.objects.count(),
    }
    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_purchase_report(context)
        return _serve_excel(content, filename)
    return render(request, 'reports/purchase_report.html', context)


@login_required
@admin_required
def expert_performance_report(request):
    """گزارش عملکرد کارشناسان — انحراف مهلت استعلام (O) در برابر تاریخ سفارش (AB)"""
    queryset = Purchase.objects.exclude(expert_name='')
    overall = OrderDeadlineService.get_overall_summary(queryset)
    experts_stats = OrderDeadlineService.get_summary_by_expert(queryset)
    experts_stats.sort(
        key=lambda row: (-row['deviated'], -row['rate'], -row['evaluated'], row['name'])
    )

    chart_experts = [row for row in experts_stats if row['evaluated'] > 0][:12]

    context = {
        'overall': overall,
        'experts_stats': experts_stats,
        'chart_names': [e['name'] for e in chart_experts],
        'chart_on_time': [e['on_time'] for e in chart_experts],
        'chart_deviated': [e['deviated'] for e in chart_experts],
        'chart_rates': [e['rate'] for e in chart_experts],
    }
    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_expert_performance(
            experts_stats, overall
        )
        return _serve_excel(content, filename)
    return render(request, 'reports/expert_performance.html', context)


@login_required
@admin_required
def deadline_deviation_report(request):
    """گزارش تفصیلی انحراف از مهلت — گروه کالایی و انبار"""
    filter_params = parse_filter_params(request)
    filtered_qs = DeadlineService.filter_queryset_for_report(
        Purchase.objects.all(), filter_params,
    )
    filter_warning = get_filter_warning(filter_params)
    has_active_filter = (
        filter_params.get('period') != 'all'
        or bool(filter_params.get('search'))
    )
    if has_active_filter and not filter_warning and filtered_qs.count() == 0:
        filter_warning = 'هیچ پرونده‌ای با این فیلتر یافت نشد — بازه تاریخ یا عبارت جستجو را بررسی کنید (داده‌ها سال ۱۴۰۵ هستند).'

    refresh_stats = DeadlineService.refresh_all_categories_and_deadlines()
    order_refresh_count = OrderDeadlineService.recalculate_all()
    refresh_stats['order_deadline_updated'] = order_refresh_count
    overall = DeadlineService.get_overall_summary(filtered_qs)
    order_overall = OrderDeadlineService.get_overall_summary(filtered_qs)
    order_expert_stats = OrderDeadlineService.get_summary_by_expert(filtered_qs)
    order_category_stats = OrderDeadlineService.get_summary_by_category(filtered_qs)
    unassigned = DeadlineService.get_unassigned_summary(filtered_qs)
    category_stats = DeadlineService.get_summary_by_category(filtered_qs)
    warehouse_stats = DeadlineService.get_summary_by_warehouse(filtered_qs)

    all_request_deviated = DeadlineService.get_deviated_cases(filtered_qs)
    req_paginator = Paginator(all_request_deviated, 100)
    req_page_obj = req_paginator.get_page(request.GET.get('req_page', 1))

    order_cases_by_expert = OrderDeadlineService.get_all_cases_by_expert(filtered_qs)
    flat_order_cases = []
    for expert in order_cases_by_expert:
        for case in expert.get('cases', []):
            flat_order_cases.append({
                **case,
                'expert_name': expert.get('name', '—'),
            })
    order_paginator = Paginator(flat_order_cases, 100)
    order_page_obj = order_paginator.get_page(request.GET.get('order_page', 1))

    query_params = request.GET.copy()
    query_params.pop('req_page', None)
    query_params.pop('order_page', None)
    query_params.pop('cat_page', None)
    pagination_query = query_params.urlencode()

    selected_cat, selected_cat_kind, cat_page_num, cat_offset, cat_page_size = (
        _parse_category_drilldown(request)
    )
    cat_cases = []
    cat_page_obj = None
    cat_total = 0
    if selected_cat and selected_cat_kind == 'request':
        cat_cases, cat_total = DeadlineService.get_deviated_cases_page(
            filtered_qs, selected_cat, offset=cat_offset, limit=cat_page_size,
        )
        cat_page_obj = Paginator(range(cat_total), cat_page_size).get_page(cat_page_num)
    elif selected_cat and selected_cat_kind == 'order':
        cat_cases, cat_total = OrderDeadlineService.get_deviated_cases_page(
            filtered_qs, selected_cat, offset=cat_offset, limit=cat_page_size,
        )
        cat_page_obj = Paginator(range(cat_total), cat_page_size).get_page(cat_page_num)

    drilldown_query = _build_drilldown_pagination_query(request)

    try:
        import jdatetime
        default_year = jdatetime.date.today().year
    except Exception:
        default_year = 1404

    export_data = {
        'filter_label': describe_active_filter(filter_params),
        'overall': overall,
        'order_overall': order_overall,
        'category_stats': category_stats,
        'warehouse_stats': warehouse_stats,
        'order_expert_stats': order_expert_stats,
        'order_category_stats': order_category_stats,
        'recent_deviated': all_request_deviated,
        'order_cases_by_expert': order_cases_by_expert,
    }
    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_deadline_deviation(export_data)
        return _serve_excel(content, filename)

    return render(request, 'reports/deadline_deviation.html', {
        'overall': overall,
        'order_overall': order_overall,
        'unassigned': unassigned,
        'refresh_stats': refresh_stats,
        'category_stats': category_stats,
        'warehouse_stats': warehouse_stats,
        'order_expert_stats': order_expert_stats,
        'order_category_stats': order_category_stats,
        'request_deviated_total': len(all_request_deviated),
        'req_page_obj': req_page_obj,
        'order_cases_total': len(flat_order_cases),
        'order_page_obj': order_page_obj,
        'order_cases_by_expert': order_cases_by_expert,
        'pagination_query': pagination_query,
        'drilldown_query': drilldown_query,
        'selected_cat': selected_cat,
        'selected_cat_kind': selected_cat_kind,
        'cat_cases': cat_cases,
        'cat_page_obj': cat_page_obj,
        'cat_total': cat_total,
        'filter_params': filter_params,
        'filter_label': describe_active_filter(filter_params),
        'filter_warning': filter_warning,
        'seasons': SEASONS,
        'default_year': default_year,
        'clear_url': request.path,
        'show_search': True,
    })


@login_required
@admin_required
def category_amounts_report(request):
    """گزارش جمع مبالغ سفارش (order_total) به تفکیک گروه کالایی"""
    filter_params = parse_filter_params(request)
    filtered_qs = apply_report_filters(Purchase.objects.all(), filter_params)
    summary = CategoryAmountService.get_summary(filtered_qs)
    filter_label = describe_active_filter(filter_params)

    try:
        import jdatetime
        default_year = jdatetime.date.today().year
    except Exception:
        default_year = 1404

    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_category_amounts(
            summary, filter_label
        )
        return _serve_excel(content, filename)

    return render(request, 'reports/category_amounts.html', {
        'summary': summary,
        'filter_params': filter_params,
        'filter_label': filter_label,
        'seasons': SEASONS,
        'default_year': default_year,
        'clear_url': request.path,
        'filter_warning': get_filter_warning(filter_params),
        'show_search': False,
    })


@login_required
@admin_required
def product_amounts_report(request):
    """گزارش ریالی به تفکیک کالا — جمع کل فاکتور (AJ) یا جمع کل سفارش (AA)"""
    filter_params = parse_filter_params(request)
    filtered_qs = apply_report_filters(Purchase.objects.all(), filter_params)
    filter_warning = get_filter_warning(filter_params)
    has_active_filter = (
        filter_params.get('period') != 'all'
        or bool(filter_params.get('search'))
    )
    if has_active_filter and not filter_warning and filtered_qs.count() == 0:
        filter_warning = 'هیچ پرونده‌ای با این فیلتر یافت نشد.'

    summary = ProductAmountService.get_summary(filtered_qs)
    filter_label = describe_active_filter(filter_params)

    try:
        import jdatetime
        default_year = jdatetime.date.today().year
    except Exception:
        default_year = 1404

    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_product_amounts(
            summary, filter_label
        )
        return _serve_excel(content, filename)

    return render(request, 'reports/product_amounts.html', {
        'summary': summary,
        'filter_params': filter_params,
        'filter_label': filter_label,
        'filter_warning': filter_warning,
        'seasons': SEASONS,
        'default_year': default_year,
        'clear_url': request.path,
        'show_search': True,
    })


@login_required
@admin_required
def payment_lead_report(request):
    """گزارش لید تایم پرداخت — ثبت واریزی تا انجام واریزی"""
    filter_params = parse_filter_params(request)
    filtered_qs = apply_report_filters(Purchase.objects.all(), filter_params)
    filter_warning = get_filter_warning(filter_params)
    has_active_filter = (
        filter_params.get('period') != 'all'
        or bool(filter_params.get('search'))
    )
    if has_active_filter and not filter_warning and filtered_qs.count() == 0:
        filter_warning = 'هیچ پرونده‌ای با این فیلتر یافت نشد.'

    PaymentLeadService.recalculate_all()
    overall = PaymentLeadService.get_overall_summary(filtered_qs)
    category_stats = PaymentLeadService.get_summary_by_category(filtered_qs)
    all_deviated = PaymentLeadService.get_recent_deviated(filtered_qs, limit=None)
    filter_label = describe_active_filter(filter_params)

    paginator = Paginator(all_deviated, 100)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_params.pop('cat_page', None)
    pagination_query = query_params.urlencode()

    selected_cat, selected_cat_kind, cat_page_num, cat_offset, cat_page_size = (
        _parse_category_drilldown(request)
    )
    cat_cases = []
    cat_page_obj = None
    cat_total = 0
    if selected_cat and selected_cat_kind == 'payment':
        cat_cases, cat_total = PaymentLeadService.get_deviated_cases_page(
            filtered_qs, selected_cat, offset=cat_offset, limit=cat_page_size,
        )
        cat_page_obj = Paginator(range(cat_total), cat_page_size).get_page(cat_page_num)

    drilldown_query = _build_drilldown_pagination_query(request)

    try:
        import jdatetime
        default_year = jdatetime.date.today().year
    except Exception:
        default_year = 1404

    export_data = {
        'filter_label': filter_label,
        'overall': overall,
        'category_stats': category_stats,
        'recent_deviated': all_deviated,
        'day_buckets': DAY_BUCKETS,
    }
    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_payment_lead(export_data)
        return _serve_excel(content, filename)

    return render(request, 'reports/payment_lead.html', {
        'overall': overall,
        'category_stats': category_stats,
        'deviated_total': len(all_deviated),
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'drilldown_query': drilldown_query,
        'selected_cat': selected_cat,
        'selected_cat_kind': selected_cat_kind,
        'cat_cases': cat_cases,
        'cat_page_obj': cat_page_obj,
        'cat_total': cat_total,
        'day_buckets': DAY_BUCKETS,
        'filter_params': filter_params,
        'filter_label': filter_label,
        'filter_warning': filter_warning,
        'seasons': SEASONS,
        'default_year': default_year,
        'clear_url': request.path,
        'show_search': True,
    })


@login_required
@admin_required
def financial_loss_report(request):
    """گزارش ضرر مالی — مقایسه فاکتور (AL) با سفارش (AC)، بدون جمع بودجه"""
    filter_params = parse_filter_params(request)
    filtered_qs = apply_report_filters(Purchase.objects.all(), filter_params)
    filter_warning = get_filter_warning(filter_params)
    has_active_filter = (
        filter_params.get('period') != 'all'
        or bool(filter_params.get('search'))
    )
    if has_active_filter and not filter_warning and not filtered_qs.exists():
        filter_warning = 'هیچ پرونده‌ای با این فیلتر یافت نشد.'

    filter_label = describe_active_filter(filter_params)
    report = FinancialLossService.build_report(filtered_qs)
    overall = report['overall']
    category_stats = report['category_stats']
    expert_stats = report['expert_stats']
    all_loss_cases = report['loss_cases']
    loss_total = report['loss_total']

    paginator = Paginator(all_loss_cases, 100)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    pagination_query = query_params.urlencode()

    try:
        import jdatetime
        default_year = jdatetime.date.today().year
    except Exception:
        default_year = 1404

    if request.GET.get('export') == 'excel':
        export_data = {
            'filter_label': filter_label,
            'overall': overall,
            'category_stats': category_stats,
            'expert_stats': expert_stats,
            'loss_cases': all_loss_cases,
        }
        content, filename = ReportExportService.export_financial_loss(export_data)
        return _serve_excel(content, filename)

    return render(request, 'reports/financial_loss.html', {
        'overall': overall,
        'category_stats': category_stats,
        'expert_stats': expert_stats,
        'loss_total': loss_total,
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'filter_params': filter_params,
        'filter_label': filter_label,
        'filter_warning': filter_warning,
        'seasons': SEASONS,
        'default_year': default_year,
        'clear_url': request.path,
        'show_search': True,
    })


@login_required
@admin_required
def purchase_tree_report(request):
    """گزارش گراف وضعیت درخواست‌های خرید — بدون فیلتر، همه داده‌ها"""
    all_qs = Purchase.objects.all()
    graph = PurchaseTreeReportService.build_graph(all_qs)

    selected_node = (request.GET.get('node') or '').strip()
    node_meta = PurchaseTreeReportService.get_node_meta(selected_node)
    node_purchases = []
    node_page_obj = None
    if node_meta:
        try:
            page_num = max(int(request.GET.get('page', 1)), 1)
        except (TypeError, ValueError):
            page_num = 1
        page_size = 100
        offset = (page_num - 1) * page_size
        node_purchases, node_total = PurchaseTreeReportService.get_node_purchases_page(
            all_qs,
            selected_node,
            offset=offset,
            limit=page_size,
        )
        node_page_obj = Paginator(range(node_total), page_size).get_page(page_num)

    pagination_query = f'node={selected_node}' if selected_node else ''

    return render(request, 'reports/purchase_tree.html', {
        'graph_total': graph['total'],
        'chart_nodes': graph['nodes'],
        'chart_links': graph['links'],
        'graph_width': graph['width'],
        'graph_height': graph['height'],
        'selected_node': selected_node,
        'node_meta': node_meta,
        'node_purchases': node_purchases,
        'node_page_obj': node_page_obj,
        'pagination_query': pagination_query,
    })


@login_required
@admin_required
def data_quality_report(request):
    """اعتبارسنجی نمونه تصادفی اکسل با پنل"""
    import random

    sample_size = min(max(int(request.GET.get('n', 10)), 1), 50)
    if 'seed' in request.GET:
        seed = int(request.GET['seed'])
    else:
        seed = random.randint(1, 2_147_483_647)
    validation = validate_random_rows(sample_size=sample_size, seed=seed)

    context = {
        'validation': validation,
        'sample_size': sample_size,
        'seed': seed,
    }
    if request.GET.get('export') == 'excel':
        content, filename = ReportExportService.export_data_quality(
            validation, sample_size, seed
        )
        return _serve_excel(content, filename)
    return render(request, 'reports/data_quality.html', context)