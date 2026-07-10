from django.urls import path
from . import views

app_name = 'inquiries'

urlpatterns = [
    path('', views.inquiry_list, name='list'),
    path('<int:pk>/', views.inquiry_detail, name='detail'),
    path('issue/<int:purchase_pk>/', views.issue_inquiry_wizard, name='issue'),
    path('issue/submit/', views.issue_inquiry_submit, name='issue_submit'),
    path('issue/export/', views.export_wizard_preinvoices, name='export_wizard'),
    path('api/purchase-detail/<int:pk>/', views.purchase_detail_ajax, name='purchase_detail_ajax'),
    path('api/last-similar/<int:pk>/', views.last_similar_purchase_ajax, name='last_similar_purchase'),
]