from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from verification.views import VerificationViewSet

router = DefaultRouter()
router.register(r"verification", VerificationViewSet, basename="verification")
urlpatterns = router.urls
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
