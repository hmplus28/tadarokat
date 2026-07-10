from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.order_list, name='list'),
    path('review/', views.order_review_queue, name='review_queue'),
    path('review/action/', views.order_review_action, name='review_action'),
    path('<int:pk>/', views.order_detail, name='detail'),
    path('create/<int:purchase_pk>/', views.create_order, name='create'),
    path('export/', views.export_orders_excel, name='export'),
]