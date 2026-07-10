from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from services.export_service import ExportService
from services.order_review_service import OrderReviewService
from accounts.permissions import admin_required
from .models import Order
from .forms import CreateOrderForm, AdvanceStageForm
from purchases.models import Purchase
from services.order_service import OrderService, STAGE_FLOW
from accounts.warehouse_access import (
    is_warehouse_user,
    filter_orders_for_warehouse,
    warehouse_can_view_order,
)

@login_required
def order_list(request):
    """لیست دستورات خرید با آمار KPI"""
    from django.db.models import Count, Q
    
    from accounts.requester_access import is_requester_user
    if is_requester_user(request.user):
        messages.info(request, 'فقط گردش کار درخواست‌های واحد شما قابل مشاهده است.')
        return redirect('purchases:list')

    is_warehouse = is_warehouse_user(request.user)
    if is_warehouse:
        messages.info(request, 'انباردار از بخش رسیدهای تحویل و اعلان‌ها استفاده می‌کند.')
        return redirect('deliveries:list')

    queryset = Order.objects.select_related('purchase', 'inquiry')
    
    # آمار KPI (روی کل دیتاست)
    all_stats = Order.objects.all().aggregate(
        pending=Count('id', filter=Q(stage='order_issued')),
        payment=Count('id', filter=Q(stage='payment')),
        delivered=Count('id', filter=Q(stage='delivered')),
    )
    
    search = request.GET.get('search', '')
    stage = request.GET.get('stage', '')
    
    if search:
        from services.search_service import SearchService
        queryset = SearchService.filter_orders(queryset, search)
    if stage:
        queryset = queryset.filter(stage=stage)

    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'search': search,
        'stage': stage,
        'stage_choices': Order.Stage.choices,
        'pending_count': all_stats['pending'],
        'payment_count': all_stats['payment'],
        'delivered_count': all_stats['delivered'],
        'is_warehouse_view': False,
    }
    return render(request, 'orders/list.html', context)


@login_required
def order_detail(request, pk):
    """جزئیات دستور + فرم پیشبرد مرحله"""
    from accounts.requester_access import is_requester_user
    if is_requester_user(request.user):
        messages.info(request, 'جزئیات گردش کار در صفحه درخواست خرید نمایش داده می‌شود.')
        order = get_object_or_404(Order.objects.select_related('purchase'), pk=pk)
        return redirect('purchases:detail', pk=order.purchase_id)

    order = get_object_or_404(Order.objects.select_related('purchase'), pk=pk)
    is_warehouse = is_warehouse_user(request.user)

    if is_warehouse and not warehouse_can_view_order(order, request.user):
        messages.error(request, 'این دستور مربوط به انبار شما نیست یا هنوز آماده تحویل نشده.')
        return redirect('deliveries:list')

    stage_info = OrderService.get_stage_info(order.stage)
    can_advance = OrderService.can_advance(order) and not is_warehouse

    form = None
    if can_advance and request.user.role not in ['warehouse']:
        if request.method == 'POST':
            form = AdvanceStageForm(request.POST)
            if form.is_valid():
                try:
                    next_info = STAGE_FLOW[order.stage]
                    fields = next_info['required_fields']
                    data = {
                        fields[0]: form.cleaned_data.get('field1', ''),
                        fields[1]: form.cleaned_data.get('field2', '') if len(fields) > 1 else '',
                        'note': form.cleaned_data.get('note', ''),
                    }
                    OrderService.advance_stage(order, data, request.user.username)
                    messages.success(request, f'✅ مرحله «{next_info["label"]}» با موفقیت ثبت شد')
                    return redirect('orders:detail', pk=pk)
                except ValueError as e:
                    messages.error(request, str(e))
        else:
            form = AdvanceStageForm()
            # تنظیم لیبل‌های داینامیک
            next_info = STAGE_FLOW[order.stage]
            fields = next_info['required_fields']
            field_labels = {
                'order_request_number': 'شماره سفارش',
                'order_request_date': 'تاریخ سفارش',
                'payment_number': 'شماره پرداخت / واریزی',
                'payment_date': 'تاریخ پرداخت',
                'delivery_number': 'شماره تحویل / مجوز ورود',
                'delivery_date': 'تاریخ تحویل',
            }
            if len(fields) >= 1:
                form.fields['field1'].label = field_labels.get(fields[0], fields[0])
                form.fields['field1'].required = True
            if len(fields) >= 2:
                form.fields['field2'].label = field_labels.get(fields[1], fields[1])
                form.fields['field2'].required = True

    context = {
        'order': order,
        'stage_info': stage_info,
        'can_advance': can_advance,
        'form': form,
        'stage_flow': STAGE_FLOW,
        'is_warehouse_view': is_warehouse,
    }
    return render(request, 'orders/detail.html', context)


@login_required
def create_order(request, purchase_pk):
    """صدور دستور خرید از درخواست خرید"""
    from inquiries.models import Inquiry

    purchase = get_object_or_404(Purchase, pk=purchase_pk)

    if request.user.role in ['warehouse']:
        messages.error(request, 'انباردار اجازه صدور دستور خرید ندارد')
        return redirect('purchases:detail', pk=purchase_pk)

    if not request.user.can_create_order:
        messages.error(request, 'فقط مدیر تدارکات می‌تواند دستور خرید صادر کند')
        return redirect('purchases:detail', pk=purchase_pk)

    if not purchase.can_issue_order or purchase.orders.exists():
        messages.error(request, 'این خرید آماده صدور دستور نیست (استعلام یا دستور قبلی وجود دارد)')
        return redirect('purchases:detail', pk=purchase_pk)

    related_inquiry = None
    if purchase.inquiry_number:
        related_inquiry = Inquiry.objects.filter(
            inquiry_number=purchase.inquiry_number
        ).prefetch_related('pre_invoices__lines').first()

    defaults = OrderService.get_order_create_defaults(purchase, related_inquiry)

    if request.method == 'POST':
        form = CreateOrderForm(request.POST)
        if form.is_valid():
            try:
                order = OrderService.create_from_purchase(
                    purchase, request.user, form.cleaned_data, inquiry=related_inquiry
                )
                messages.success(request, f'✅ دستور خرید {order.order_number} صادر شد')
                return redirect('orders:detail', pk=order.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = CreateOrderForm(initial=defaults)

    context = {
        'form': form,
        'purchase': purchase,
        'related_inquiry': related_inquiry,
        'preinvoice_comparison': OrderService.get_preinvoice_comparison(related_inquiry),
        'similar_purchases': OrderService.get_similar_purchases(purchase),
        'auto_order_number': defaults['order_number'],
        'auto_order_date': defaults['order_date'],
        'show_review_actions': True,
        'purchase_ids': [purchase.pk],
        'current_expert': purchase.expert_name or '',
        'expert_choices': OrderReviewService.get_expert_choices(),
        'review_next_url': request.get_full_path(),
    }
    return render(request, 'orders/create.html', context)


@login_required
@admin_required
def order_review_queue(request):
    """صف بررسی مدیر — ردیف‌های آماده صدور دستور"""
    search = request.GET.get('search', '')
    expert_filter = request.GET.get('expert', '')
    pending_items = OrderReviewService.get_pending_queue(search=search, expert=expert_filter)

    return render(request, 'orders/review_queue.html', {
        'pending_items': pending_items,
        'pending_count': len(pending_items),
        'search': search,
        'expert_filter': expert_filter,
        'expert_choices': OrderReviewService.get_expert_choices(),
    })


@login_required
@admin_required
@require_http_methods(['POST'])
def order_review_action(request):
    """ارجاع کارشناس یا بازگشت برای استعلام مجدد"""
    purchase_ids = request.POST.getlist('purchase_ids')
    action = request.POST.get('action', '')
    note = request.POST.get('note', '')
    expert_name = request.POST.get('expert_name', '')
    next_url = request.POST.get('next') or ''

    try:
        ids = [int(x) for x in purchase_ids if str(x).isdigit()]
        if action == 'reassign':
            result = OrderReviewService.reassign_expert(
                ids, expert_name, request.user, note=note, request=request,
            )
            updated = result.get('updated', 0)
            if updated:
                messages.success(request, f'✅ {updated} ردیف به کارشناس جدید ارجاع شد.')
            else:
                messages.info(request, 'کارشناس قبلاً همان بود — تغییری اعمال نشد.')
        elif action == 'return_inquiry':
            result = OrderReviewService.return_for_reinquiry(
                ids, request.user, note=note, new_expert_name=expert_name, request=request,
            )
            messages.success(
                request,
                f'🔄 {result["returned"]} ردیف برای استعلام مجدد به کارشناس برگشت داده شد.',
            )
        else:
            messages.error(request, 'عملیات نامعتبر است.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'خطا: {e}')

    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('orders:review_queue')


@login_required
def export_orders_excel(request):
    """خروجی اکسل از دستورات با فیلترهای جاری"""
    queryset = Order.objects.all()
    
    search = request.GET.get('search', '')
    stage = request.GET.get('stage', '')
    
    if search:
        from services.search_service import SearchService
        queryset = SearchService.filter_orders(queryset, search)
    if stage:
        queryset = queryset.filter(stage=stage)
    
    content, filename = ExportService.export_orders(queryset)
    
    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response