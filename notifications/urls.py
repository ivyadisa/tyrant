from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    NotificationViewSet,
    NotificationSettingViewSet,
    AdminNotificationViewSet,
)

router = DefaultRouter()

# Main user notification endpoints
router.register(r"", NotificationViewSet, basename="notification")

# User notification settings
router.register(
    r"settings", 
    NotificationSettingViewSet, 
    basename="notification-settings"
)

# Admin-only notification management
router.register(
    r"admin", 
    AdminNotificationViewSet, 
    basename="admin-notification"
)

urlpatterns = router.urls