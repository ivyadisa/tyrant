from rest_framework import serializers
from .models import Notification, NotificationSetting, NotificationType


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for user-facing notifications."""
    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "message",
            "related_object_type",
            "related_object_id",
            "is_read",
            "read_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "type",
            "title",
            "message",
            "related_object_type",
            "related_object_id",
            "read_at",
            "created_at",
        ]


class NotificationSettingSerializer(serializers.ModelSerializer):
    """Serializer for user notification preferences."""
    class Meta:
        model = NotificationSetting
        fields = [
            "id",
            "email_enabled",
            "push_enabled",
            "notify_booking_requests",
            "notify_booking_confirmations",
            "notify_user_registrations",
            "notify_property_verifications",
            "notify_tour_requests",
        ]
        read_only_fields = ["id"]


class NotificationCreateSerializer(serializers.Serializer):
    """Serializer for admin bulk notification creation."""
    recipient_id = serializers.UUIDField(required=False)
    recipient_role = serializers.ChoiceField(
        choices=["ADMIN", "LANDLORD", "TENANT", "ALL_LANDLORDS"],
        required=False
    )
    type = serializers.ChoiceField(choices=NotificationType.choices)
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    related_object_type = serializers.CharField(
        max_length=50, required=False, allow_blank=True
    )
    related_object_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        """Ensure either recipient_id OR recipient_role is provided."""
        if not data.get("recipient_id") and not data.get("recipient_role"):
            raise serializers.ValidationError(
                "Either recipient_id or recipient_role must be provided."
            )
        return data