from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('properties/', include('properties.urls')),
    path('wallet/', include('wallet.urls')),
    path('bookings/', include('bookings.urls')),
]
