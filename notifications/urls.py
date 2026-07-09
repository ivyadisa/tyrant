from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, NotificationSettingViewSet, AdminNotificationViewSet

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")                          # ← empty string
router.register(r"settings", NotificationSettingViewSet, basename="notification-settings")
router.register(r"admin", AdminNotificationViewSet, basename="admin-notification")

urlpatterns = router.urls