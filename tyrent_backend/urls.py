from django.contrib import admin
from django.urls import path, include 
from django.contrib.sitemaps.views import sitemap
from properties.sitemaps import ApartmentSitemap, UnitSitemap
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView
)

from users.urls_auth import urlpatterns

sitemaps = {
    'apartments': ApartmentSitemap,
    'units': UnitSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    # 🔹 Swagger / OpenAPI
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/',
         SpectacularSwaggerView.as_view(url_name='schema'),
         name='swagger-ui'),
    path('api/auth/', include('users.urls_auth')),
    path('api/admin/', include('users.urls_admin')),
    path('api/users/', include('users.urls_users')),
    path('api/landlord/', include('users.urls_landlord')),
    path('api/tenant/', include('users.urls_tenant')),

    path(
        'api/properties/',
        include(('properties.urls', 'properties'), namespace='properties')
    ),

    path('api/wallet/', include('wallet.urls')),
    path('api/bookings/', include('bookings.urls')),

    path("api/", include("verification.urls")),

    path('api/sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]