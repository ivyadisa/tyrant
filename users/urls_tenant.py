from  django.urls import path

from .urls_auth import urlpatterns
from .views import tenant_dashboard


urlpatterns = [
path('dashboard', tenant_dashboard, name='tenant-dashboard')
]