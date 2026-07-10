from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
import json

from .models import Inquiry, PreInvoice, PreInvoiceLine
from purchases.models import Purchase
from services.notification_service import NotificationService
from services.export_service import ExportService
from services.inquiry_service import InquiryService


@login_required
def inquiry_list(request):
    """لیست استعلام‌ها"""
    if getattr(request.user, 'is_requester_role', False):
        messages.info(request, 'فقط گردش کار درخواست‌های واحد شما قابل مشاهده است.')
        return redirect('purchases:list')
    if getattr(request.user, 'is_warehouse_role', False):
        messages.info(request, 'انباردار به بخش دستورات پرداخت‌شده دسترسی دارد.')
        return redirect('orders:list')

    from accounts.expert_access import filter_inquiries_for_expert

    queryset = filter_inquiries_for_expert(
        Inquiry.objects.select_related('purchase', 'created_by'),
        request.user,
    )
    
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')
    
    if search:
        from services.search_service import SearchService
        queryset = SearchService.filter_inquiries(queryset, search)
    if status:
        queryset = queryset.filter(status=status)
    
    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    return render(request, 'inquiries/list.html', {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'status_choices': Inquiry.Status.choices,
    })


@login_required
def inquiry_detail(request, pk):
    """جزئیات استعلام با پیش‌فاکتورها"""
    from services.order_review_service import OrderReviewService

    inquiry = get_object_or_404(
        Inquiry.objects.select_related('purchase'),
        pk=pk
    )
    pre_invoices = inquiry.pre_invoices.prefetch_related('lines').all()
    purchase = inquiry.purchase
    show_review_actions = (
        request.user.can_create_order
        and purchase
        and purchase.can_issue_order
        and inquiry.status in (Inquiry.Status.ISSUED, Inquiry.Status.APPROVED)
    )

    return render(request, 'inquiries/detail.html', {
        'inquiry': inquiry,
        'pre_invoices': pre_invoices,
        'show_review_actions': show_review_actions,
        'purchase_ids': [purchase.pk] if purchase else [],
        'current_expert': purchase.expert_name if purchase else '',
        'expert_choices': OrderReviewService.get_expert_choices() if show_review_actions else [],
        'review_next_url': request.get_full_path(),
        'can_issue_order': purchase.can_issue_order if purchase else False,
    })


@login_required
def issue_inquiry_wizard(request, purchase_pk):
    """Wizard صدور استعلام"""
    purchase = get_object_or_404(Purchase, pk=purchase_pk)
    
    # 🆕 استفاده از can_issue_inquiry
    if not purchase.can_issue_inquiry:
        messages.error(request, 'این خرید نیازی به استعلام ندارد یا قبلاً پردازش شده است')
        return redirect('purchases:list')
    
    # 🆕 بررسی دسترسی کاربر
    if not request.user.can_issue_inquiry:
        messages.error(request, 'شما دسترسی صدور استعلام را ندارید')
        return redirect('purchases:list')
    
    from accounts.models import Warehouse, ProductCategory

    return render(request, 'inquiries/issue_wizard.html', {
        'purchase': purchase,
        'warehouses': Warehouse.get_active_choices(),
        'product_categories': ProductCategory.get_active_choices(),
    })


@login_required
@require_POST
def issue_inquiry_submit(request):
    """ثبت نهایی Wizard صدور استعلام (AJAX)"""
    try:
        data = json.loads(request.body)
        purchase_pk = data.get('purchase_pk')
        header = data.get('header', {})
        pre_invoices = data.get('pre_invoices', [])
        
        if not purchase_pk or not header:
            return JsonResponse({'error': 'داده‌های ناقص'}, status=400)
        
        purchase = get_object_or_404(Purchase, pk=purchase_pk)
        
        with transaction.atomic():
            # ایجاد استعلام
            inquiry = Inquiry.objects.create(
                inquiry_number=header.get('inquiry_number') or Inquiry.get_next_inquiry_number(),
                purchase=purchase,
                inquiry_date=header.get('inquiry_date', ''),
                deadline=header.get('deadline', ''),
                purchase_type=header.get('purchase_type', 'استعلامی'),
                urgency_code=header.get('urgency_code', ''),
                supply_unit=header.get('supply_unit', ''),
                reason=header.get('reason', ''),
                warehouse=header.get('warehouse', ''),
                product_category=header.get('product_category', ''),
                warehouse_request_number=header.get('warehouse_request_number', ''),
                warehouse_request_date=header.get('warehouse_request_date', ''),
                requester=header.get('requester', ''),
                risk_note=header.get('risk_note', ''),
                expert_name=purchase.expert_name,
                issuer=request.user.get_full_name() or request.user.username,
                status=Inquiry.Status.ISSUED,
                created_by=request.user,
            )
            
            # ایجاد پیش‌فاکتورها
            for inv_data in pre_invoices:
                pre_inv = PreInvoice.objects.create(
                    inquiry=inquiry,
                    contractor=inv_data.get('contractor', ''),
                    invoice_number=inv_data.get('invoice_number', ''),
                    invoice_date=inv_data.get('invoice_date', ''),
                    city=inv_data.get('city', ''),
                    validity_days=inv_data.get('validity_days', 7),
                    tax_rate=inv_data.get('tax_rate', 0),
                    discount=inv_data.get('discount', 0),
                    notes=inv_data.get('notes', ''),
                    is_selected=inv_data.get('is_selected', False),
                )
                
                for line_data in inv_data.get('lines', []):
                    PreInvoiceLine.objects.create(
                        pre_invoice=pre_inv,
                        row_number=line_data.get('row_number', 1),
                        product_title=line_data.get('product_title', ''),
                        product_code=line_data.get('product_code', ''),
                        quantity=line_data.get('quantity', 1),
                        unit=line_data.get('unit', ''),
                        unit_price=line_data.get('unit_price', 0),
                        description=line_data.get('description', ''),
                    )
            
            # به‌روزرسانی خرید + همگام‌سازی پیش‌فاکتور (تخفیف → کسور)
            purchase.inquiry_number = inquiry.inquiry_number
            if header.get('product_category'):
                purchase.product_category = header['product_category']
            from services.deadline_service import DeadlineService
            purchase.deadline_deviated = DeadlineService.evaluate_purchase(purchase)
            purchase.save(update_fields=[
                'inquiry_number', 'deadline_deviated', 'current_status',
                *(['product_category'] if header.get('product_category') else []),
            ])
            InquiryService.sync_purchase_from_inquiry(purchase, inquiry)
            
            # ارسال اعلان به مدیر
            NotificationService.notify_role(
                'admin',
                '📄 استعلام جدید صادر شد',
                f'استعلام {inquiry.inquiry_number} برای خرید {purchase.purchase_number} توسط {request.user.username} صادر شد',
                'inquiry',
                f'/inquiries/{inquiry.pk}/'
            )
            NotificationService.notify_warehouse_goods_request(inquiry)
        
        return JsonResponse({
            'success': True,
            'inquiry_id': inquiry.pk,
            'inquiry_number': inquiry.inquiry_number,
            'message': f'استعلام {inquiry.inquiry_number} با موفقیت صادر شد'
        })
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def export_wizard_preinvoices(request):
    """خروجی اکسل مقایسه پیش‌فاکتورها (Wizard)"""
    try:
        data = json.loads(request.body)
        purchase_data = data.get('purchase_data', {})
        header = data.get('header', {})
        pre_invoices = data.get('pre_invoices', [])

        if not pre_invoices:
            return JsonResponse({'error': 'پیش‌فاکتوری برای خروجی وجود ندارد'}, status=400)

        content, filename = ExportService.export_wizard_preinvoices(
            purchase_data, header, pre_invoices
        )

        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def last_similar_purchase_ajax(request, pk):
    """آخرین خرید مشابه همان کالا برای مقایسه در صدور استعلام"""
    from django.urls import reverse
    from services.order_service import OrderService

    purchase = get_object_or_404(Purchase, pk=pk)
    similar = OrderService.get_similar_purchases(purchase, limit=1)
    if not similar:
        return JsonResponse({'found': False})

    last = similar[0]
    return JsonResponse({
        'found': True,
        'purchase_number': last.purchase_number,
        'line_number': last.line_number,
        'product_title': last.product_title,
        'product_code': last.product_code or '',
        'supplier': last.supplier or '',
        'order_number': last.order_number or '',
        'order_request_number': last.order_request_number or '',
        'preinvoice_price': str(last.preinvoice_price or ''),
        'preinvoice_total': str(last.preinvoice_total or ''),
        'order_total': str(last.order_total or ''),
        'order_date': last.order_date or '',
        'order_request_date': last.order_request_date or '',
        'current_status': last.current_status_fa,
        'detail_url': reverse('purchases:detail', args=[last.pk]),
    })


@login_required
def purchase_detail_ajax(request, pk):
    """API برای دریافت جزئیات خرید (برای Modal)"""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    # سایر خطوط همین خرید
    siblings_qs = Purchase.objects.filter(
        purchase_number=purchase.purchase_number
    ).order_by('line_number')
    siblings = [
        {
            'id': s.pk,
            'line_number': s.line_number,
            'product_title': s.product_title,
            'product_code': s.product_code,
            'quantity': str(s.quantity),
            'unit': s.unit,
            'current_status': s.current_status,
            'current_status_display': s.current_status_fa,
        }
        for s in siblings_qs
    ]
    
    # استعلام مرتبط
    inquiry = Inquiry.objects.filter(purchase=purchase).select_related('created_by').first()
    
    return JsonResponse({
        'id': purchase.pk,
        'purchase_number': purchase.purchase_number,
        'product_title': purchase.product_title,
        'product_code': purchase.product_code,
        'quantity': str(purchase.quantity),
        'unit': purchase.unit,
        'expert_name': purchase.expert_name,
        'requester': purchase.requester,
        'purchase_date': purchase.purchase_date,
        'required_date': purchase.required_date,
        'description': purchase.description,
        'supply_unit': purchase.supply_unit,
        'status': purchase.status,
        'current_status': purchase.current_status,
        'current_status_display': purchase.current_status_fa,
        'inquiry_number': purchase.inquiry_number,
        'order_number': purchase.order_number,
        'delivery_number': purchase.delivery_number,
        'siblings': siblings,
        'inquiry': {
            'id': inquiry.pk,
            'number': inquiry.inquiry_number,
            'status': inquiry.status,
        } if inquiry else None,
    })