from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('api/list/', views.notification_list, name='list_api'),
    path('api/mark-read/', views.mark_all_read, name='mark_read_api'),
]