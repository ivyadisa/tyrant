import uuid
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class NotificationType(models.TextChoices):
    # User-related notifications
    USER_REGISTRATION = "USER_REGISTRATION", "New User Registration"
    USER_VERIFICATION = "USER_VERIFICATION", "User Verification"
    USER_ROLE_CHANGE = "USER_ROLE_CHANGE", "Role Change"

    # Booking-related notifications
    BOOKING_REQUEST = "BOOKING_REQUEST", "Booking Request"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED", "Booking Confirmed"
    BOOKING_CANCELLED = "BOOKING_CANCELLED", "Booking Cancelled"
    BOOKING_COMPLETED = "BOOKING_COMPLETED", "Booking Completed"
    BOOKING_PAYMENT = "BOOKING_PAYMENT", "Payment Received"

    # Property-related notifications
    APARTMENT_SUBMITTED = "APARTMENT_SUBMITTED", "Apartment Submitted"
    APARTMENT_VERIFIED = "APARTMENT_VERIFIED", "Apartment Verified"
    APARTMENT_REJECTED = "APARTMENT_REJECTED", "Apartment Rejected"
    APARTMENT_APPROVED = "APARTMENT_APPROVED", "Apartment Approved"

    # Tour-related notifications
    TOUR_REQUEST = "TOUR_REQUEST", "Tour Request"
    TOUR_CONFIRMED = "TOUR_CONFIRMED", "Tour Confirmed"
    TOUR_CANCELLED = "TOUR_CANCELLED", "Tour Cancelled"

    # System notifications
    GENERAL = "GENERAL", "General"


class NotificationRecipientType(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    LANDLORD = "LANDLORD", "Landlord"
    TENANT = "TENANT", "Tenant"
    ALL_LANDLORDS = "ALL_LANDLORDS", "All Landlords"


class Notification(models.Model):
    """Notification model for system-wide notifications."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    type = models.CharField(max_length=50, choices=NotificationType.choices)

    #通知内容
    title = models.CharField(max_length=255)
    message = models.TextField()

    # Related object references (optional)
    related_object_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g., 'Booking', 'Apartment', 'User'"
    )
    related_object_id = models.UUIDField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self):
        return f"Notification for {self.recipient}: {self.title}"

    def mark_as_read(self):
        from django.utils import timezone
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])


class NotificationSetting(models.Model):
    """User notification preferences."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="notification_settings"
    )

    # Email notifications toggle
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)

    # Notification type preferences
    notify_booking_requests = models.BooleanField(default=True)
    notify_booking_confirmations = models.BooleanField(default=True)
    notify_user_registrations = models.BooleanField(default=True)
    notify_property_verifications = models.BooleanField(default=True)
    notify_tour_requests = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification settings for {self.user.username}"


# Helper functions to create notifications

def create_notification(
    recipient,
    notification_type,
    title,
    message,
    related_object_type=None,
    related_object_id=None,
):
    """Create a single notification."""
    return Notification.objects.create(
        recipient=recipient,
        type=notification_type,
        title=title,
        message=message,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )


def notify_admins(
    notification_type,
    title,
    message,
    related_object_type=None,
    related_object_id=None,
):
    """Notify all admin users."""
    from users.models import User
    admins = User.objects.filter(role=User.ROLE_ADMIN, status=User.STATUS_ACTIVE)
    notifications = []
    for admin in admins:
        notifications.append(
            Notification(
                recipient=admin,
                type=notification_type,
                title=title,
                message=message,
                related_object_type=related_object_type,
                related_object_id=related_object_id,
            )
        )
    return Notification.objects.bulk_create(notifications)


def notify_landlord(
    landlord,
    notification_type,
    title,
    message,
    related_object_type=None,
    related_object_id=None,
):
    """Notify a specific landlord."""
    return create_notification(
        recipient=landlord,
        notification_type=notification_type,
        title=title,
        message=message,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )