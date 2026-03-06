from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    ApartmentViewSet,
    UnitViewSet,
    LeaseAgreementViewSet,
    KeyAmenityViewSet,
    occupancy_stats,
)

# DRF Router
router = DefaultRouter()

router.register(r"apartments", ApartmentViewSet, basename="apartment")
router.register(r"units", UnitViewSet, basename="unit")
router.register(r"lease-agreements", LeaseAgreementViewSet, basename="lease-agreement")
router.register(r"key-amenities", KeyAmenityViewSet, basename="key-amenity")

urlpatterns = [

    # Router endpoints
    path("", include(router.urls)),

    # Custom API endpoints
    path("occupancy-stats/", occupancy_stats, name="occupancy-stats"),
]