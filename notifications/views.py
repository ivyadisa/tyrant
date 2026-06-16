from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q

from .models import Notification, NotificationSetting, NotificationType
from .serializers import (
    NotificationSerializer,
    NotificationSettingSerializer,
)


class NotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user notifications."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def list(self, request, *args, **kwargs):
        """List notifications for the current user."""
        queryset = self.get_queryset()

        # Filter by read status
        is_read = request.query_params.get("is_read")
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == "true")

        # Filter by type
        notification_type = request.query_params.get("type")
        if notification_type:
            queryset = queryset.filter(type=notification_type)

        # Pagination
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        start = (page - 1) * page_size
        end = start + page_size

        notifications = queryset[start:end]
        serializer = self.get_serializer(notifications, many=True)

        return Response({
            "notifications": serializer.data,
            "count": queryset.count(),
            "unread_count": queryset.filter(is_read=False).count(),
        })

    def retrieve(self, request, *args, **kwargs):
        """Get a single notification."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({"message": "Notification marked as read"})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        """Mark all notifications as read."""
        notifications = self.get_queryset().filter(is_read=False)
        from django.utils import timezone
        notifications.update(is_read=True, read_at=timezone.now())
        return Response({"message": "All notifications marked as read"})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get the unread notification count."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread_count": count})

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


class NotificationSettingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification settings."""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return NotificationSetting.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        """Get notification settings for current user."""
        setting, _ = NotificationSetting.objects.get_or_create(user=request.user)
        serializer = NotificationSettingSerializer(setting)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """Update notification settings."""
        setting, _ = NotificationSetting.objects.get_or_create(user=request.user)
        serializer = NotificationSettingSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    update = partial_update


# ============ ADMIN ONLY VIEWS ============

class AdminNotificationViewSet(viewsets.ModelViewSet):
    """Admin-only viewset for managing system notifications."""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        # Admin can see all notifications
        return Notification.objects.all()

    @action(detail=False, methods=["get"])
    def send_to_role(self, request):
        """Send notification to all users of a specific role."""
        from users.models import User

        recipient_role = request.data.get("recipient_role")
        notification_type = request.data.get("type")
        title = request.data.get("title")
        message = request.data.get("message")

        if not all([notification_type, title, message]):
            return Response(
                {"error": "type, title, and message are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        notifications = []
        for user in users:
            notifications.append(
                Notification(
                    recipient=user,
                    type=notification_type,
                    title=title,
                    message=message,
                )
            )

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