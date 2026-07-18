from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count
from django.utils import timezone

from .models import Notification, NotificationSetting, NotificationType
from .serializers import (
    NotificationSerializer,
    NotificationSettingSerializer,
    NotificationCreateSerializer,
)


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user notifications."""
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def list(self, request, *args, **kwargs):
        """List notifications for the current user with filtering."""
        queryset = self.get_queryset()

        # Filter by read status
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() in ["true", "1"])

        # Filter by type
        notification_type = request.query_params.get("type")
        if notification_type:
            queryset = queryset.filter(type=notification_type)

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)

        return Response({
            "results": serializer.data,
            "count": queryset.count(),
            "unread_count": queryset.filter(is_read=False).count(),
        })

    def retrieve(self, request, *args, **kwargs):
        """Get a single notification."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return Response({
            "results": serializer.data,
            "count": 1,
            "unread_count": self.get_queryset().filter(is_read=False).count(),
        })

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({"success": True, "message": "All notifications marked as read"})

    @action(detail=False, methods=["get"], url_path="unread")
    def unread(self, request):
        """Get only unread notifications."""
        qs = self.get_queryset().filter(is_read=False)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page, many=True)

        return Response({
            "results": serializer.data,
            "count": qs.count(),
            "unread_count": qs.count(),
        })

    @action(detail=False, methods=["get"])
    def unread_count_by_type(self, request):
        """Get unread count grouped by notification type."""
        queryset = self.get_queryset().filter(is_read=False)
        counts = (
            queryset.values("type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        return Response({"counts": list(counts)})
    
class NotificationSettingViewSet(viewsets.GenericViewSet):
    """ViewSet for managing notification settings (singleton per user)."""
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSettingSerializer

    def get_queryset(self):
        return NotificationSetting.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        """Get current user's notification settings."""
        setting, _ = NotificationSetting.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(setting)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """Update notification settings."""
        setting, _ = NotificationSetting.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    # Alias update to partial_update
    update = partial_update

class AdminNotificationViewSet(viewsets.ModelViewSet):
    """Admin-only viewset for managing system notifications."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.all()

    @action(detail=False, methods=["post"])
    def send_to_role(self, request):
        """Send notification to users by role."""
        serializer = NotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient_role = serializer.validated_data.get("recipient_role")
        notification_type = serializer.validated_data["type"]
        title = serializer.validated_data["title"]
        message = serializer.validated_data["message"]
        related_object_type = serializer.validated_data.get("related_object_type")
        related_object_id = serializer.validated_data.get("related_object_id")

        from users.models import User

        if recipient_role == "ALL_LANDLORDS":
            users = User.objects.filter(
                role=User.ROLE_LANDLORD,
                status=User.STATUS_ACTIVE
            )
        else:
            users = User.objects.filter(
                role=recipient_role,
                status=User.STATUS_ACTIVE
            )

        notifications = [
            Notification(
                recipient=user,
                type=notification_type,
                title=title,
                message=message,
                related_object_type=related_object_type,
                related_object_id=related_object_id,
            )
            for user in users
        ]

        created = Notification.objects.bulk_create(notifications)

        return Response({
            "message": f"Successfully sent to {len(created)} users",
            "count": len(created)
        })

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get notification statistics."""
        total = Notification.objects.count()
        unread = Notification.objects.filter(is_read=False).count()
        by_type = (
            Notification.objects.values("type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        by_role = (
            Notification.objects.values("recipient__role")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response({
            "total": total,
            "unread": unread,
            "by_type": list(by_type),
            "by_role": list(by_role),
        })