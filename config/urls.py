from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from purchases.views import dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('', dashboard, name='dashboard'),
    path('purchases/', include('purchases.urls', namespace='purchases')),
    path('inquiries/', include('inquiries.urls', namespace='inquiries')),
    path('orders/', include('orders.urls', namespace='orders')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
    path('deliveries/', include('deliveries.urls', namespace='deliveries')),
    path('audit/', include('audit.urls', namespace='audit')),
    path('reports/', include('reports.urls', namespace='reports')),
]

from django.conf import settings
settings.LOGIN_URL = '/accounts/login/'
settings.LOGIN_REDIRECT_URL = '/'
settings.LOGOUT_REDIRECT_URL = '/accounts/login/'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
elif getattr(settings, 'SERVE_MEDIA', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)