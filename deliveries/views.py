from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count

from .models import Delivery
from .forms import CreateDeliveryForm
from orders.models import Order
from services.notification_service import NotificationService
from accounts.warehouse_access import (
    is_warehouse_user,
    filter_deliveries_for_warehouse,
    warehouse_can_view_delivery,
    warehouse_can_view_order,
)


@login_required
def delivery_list(request):
    """لیست تحویل‌ها"""
    from accounts.requester_access import is_requester_user
    if is_requester_user(request.user):
        messages.info(request, 'وضعیت تحویل در گردش کار هر درخواست خرید نمایش داده می‌شود.')
        return redirect('purchases:list')

    is_warehouse = is_warehouse_user(request.user)
    queryset = Delivery.objects.select_related(
        'order', 'purchase', 'created_by'
    ).order_by('-delivery_date', '-pk')

    if is_warehouse:
        queryset = filter_deliveries_for_warehouse(queryset, request.user)

    search = request.GET.get('search', '')
    if search:
        from services.search_service import SearchService
        queryset = SearchService.filter_deliveries(queryset, search)

    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    total_count = queryset.count()
    my_count = 0
    if is_warehouse:
        my_count = queryset.filter(created_by=request.user).count()

    context = {
        'page_obj': page_obj,
        'search': search,
        'total_count': total_count,
        'my_count': my_count,
        'is_warehouse_view': is_warehouse,
        'warehouse_name': request.user.warehouse if is_warehouse else '',
    }
    return render(request, 'deliveries/list.html', context)

@login_required
def create_delivery(request, order_pk):
    """ثبت تحویل برای یک دستور خرید"""
    order = get_object_or_404(Order, pk=order_pk)

    if is_warehouse_user(request.user) and not warehouse_can_view_order(order, request.user):
        messages.error(request, 'این دستور مربوط به انبار شما نیست.')
        return redirect('deliveries:list')

    # فقط نقش‌های مجاز
    if request.user.role not in ['warehouse', 'admin']:
        messages.error(request, 'فقط انباردار و مدیر می‌توانند تحویل ثبت کنند')
        return redirect('orders:detail', pk=order_pk)
    
    if request.method == 'POST':
        form = CreateDeliveryForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # بررسی تکراری نبودن شماره تحویل
            if Delivery.objects.filter(delivery_number=data['delivery_number']).exists():
                messages.error(request, f'شماره تحویل {data["delivery_number"]} قبلاً ثبت شده است')
            else:
                delivery = Delivery.objects.create(
                    delivery_number=data['delivery_number'],
                    order=order,
                    product_title=order.product_title,
                    quantity=order.quantity,
                    unit=order.unit,
                    warehouse=order.warehouse,
                    receiver=data['receiver'],
                    delivery_date=data['delivery_date'],
                    description=data['description'],
                    created_by=request.user,
                )
                
                # بروزرسانی مرحله دستور به تحویل شده
                order.stage = Order.Stage.DELIVERED
                order.status = 'تحویل شده'
                order.delivery_number = data['delivery_number']
                order.delivery_date = data['delivery_date']
                order.save()
                
                # ارسال اعلان به کارشناس و مدیر
                expert_user = None
                if order.created_by:
                    expert_user = order.created_by
                
                notify_msg = f'کالا «{order.product_title[:30]}» با شماره {data["delivery_number"]} تحویل شد.'
                NotificationService.notify_role('admin', '✅ تحویل جدید ثبت شد', notify_msg, 'delivery', f'/deliveries/')
                if expert_user:
                    NotificationService.notify(expert_user, '✅ کالای شما تحویل شد', notify_msg, 'delivery', f'/orders/{order.pk}/')
                
                messages.success(request, f'✅ تحویل {data["delivery_number"]} با موفقیت ثبت شد')
                return redirect('deliveries:list')
    else:
        from datetime import datetime
        try:
            import jdatetime
            today = jdatetime.date.today().strftime('%Y/%m/%d')
        except ImportError:
            today = datetime.now().strftime('%Y/%m/%d')
        
        form = CreateDeliveryForm(initial={'delivery_date': today})
    
    context = {'form': form, 'order': order}
    return render(request, 'deliveries/create.html', context)



@login_required
def delivery_detail(request, pk):
    """جزئیات یک تحویل"""
    delivery = get_object_or_404(
        Delivery.objects.select_related('order', 'purchase'), pk=pk
    )

    if is_warehouse_user(request.user) and not warehouse_can_view_delivery(delivery, request.user):
        messages.error(request, 'دسترسی به این رسید تحویل مجاز نیست.')
        return redirect('deliveries:list')

    context = {
        'delivery': delivery,
        'is_warehouse_view': is_warehouse_user(request.user),
    }
    return render(request, 'deliveries/detail.html', context)