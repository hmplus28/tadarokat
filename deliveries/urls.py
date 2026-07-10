from django.urls import path
from . import views

app_name = 'deliveries'

urlpatterns = [
    path('', views.delivery_list, name='list'),
    path('create/<int:order_pk>/', views.create_delivery, name='create'),
    path('<int:pk>/', views.delivery_detail, name='detail'),
]