from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('purchases/', views.purchase_report, name='purchase_report'),
    path('experts/', views.expert_performance_report, name='expert_performance'),
    path('data-quality/', views.data_quality_report, name='data_quality'),
    path('deadline-deviation/', views.deadline_deviation_report, name='deadline_deviation'),
    path('category-amounts/', views.category_amounts_report, name='category_amounts'),
    path('payment-lead/', views.payment_lead_report, name='payment_lead'),
    path('product-amounts/', views.product_amounts_report, name='product_amounts'),
    path('financial-loss/', views.financial_loss_report, name='financial_loss'),
    path('purchase-tree/', views.purchase_tree_report, name='purchase_tree'),
]