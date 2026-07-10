from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # User Management (Superuser only)
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit_view, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete_view, name='user_delete'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active_view, name='user_toggle_active'),
    path('warehouses/', views.warehouse_list_view, name='warehouse_list'),
    path('category-deadlines/', views.category_deadline_list_view, name='category_deadline_list'),
]