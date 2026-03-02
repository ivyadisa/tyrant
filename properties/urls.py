from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApartmentViewSet, UnitViewSet, LeaseAgreementViewSet
from . import views as local_views

router = DefaultRouter()
router.register(r"apartments", ApartmentViewSet, basename="apartment")
router.register(r"units", UnitViewSet, basename="unit")
router.register(r"lease-agreements", LeaseAgreementViewSet, basename="lease-agreement")

urlpatterns = [
    path("", include(router.urls)),
    path("occupancy-stats/", local_views.occupancy_stats, name="occupancy-stats"),
]
