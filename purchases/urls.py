from django.urls import path
from . import views

app_name = 'purchases'

urlpatterns = [
    path('', views.purchase_list, name='list'),
    path('<int:pk>/', views.purchase_detail, name='detail'),
    path('<int:pk>/edit/', views.purchase_edit, name='edit'),
    path('export/', views.export_purchases_excel, name='export'),
    path('upload-excel/', views.upload_excel, name='upload_excel'),
    path('upload-excel/start/', views.upload_excel_start, name='upload_excel_start'),
    path('upload-excel/status/<str:job_id>/', views.upload_excel_status, name='upload_excel_status'),
    path('upload-excel/template/', views.download_excel_template, name='download_excel_template'),
    path('upload-excel/export-full/', views.download_full_excel_export, name='download_full_excel_export'),
    path('upload-excel/download/<str:token>/', views.download_uploaded_excel, name='download_uploaded_excel'),
    path('sync-recalculate/', views.sync_and_recalculate, name='sync_recalculate'),
]