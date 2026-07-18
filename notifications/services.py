import logging
from .models import Notification, NotificationSetting, NotificationType, notify_admins

logger = logging.getLogger(__name__)

# Maps notification types to their corresponding settings toggle
_TYPE_SETTING_MAP = {
    NotificationType.BOOKING_REQUEST: "notify_booking_requests",
    NotificationType.BOOKING_CONFIRMED: "notify_booking_confirmations",
    NotificationType.BOOKING_CANCELLED: "notify_booking_confirmations",
    NotificationType.BOOKING_COMPLETED: "notify_booking_confirmations",
    NotificationType.BOOKING_PAYMENT: "notify_booking_confirmations",
    NotificationType.USER_REGISTRATION: "notify_user_registrations",
    NotificationType.APARTMENT_SUBMITTED: "notify_property_verifications",
    NotificationType.APARTMENT_VERIFIED: "notify_property_verifications",
    NotificationType.APARTMENT_APPROVED: "notify_property_verifications",
    NotificationType.APARTMENT_REJECTED: "notify_property_verifications",
    NotificationType.TOUR_REQUEST: "notify_tour_requests",
    NotificationType.TOUR_CONFIRMED: "notify_tour_requests",
    NotificationType.TOUR_CANCELLED: "notify_tour_requests",
}


def notify(recipient, notification_type, title, message, related_object_type=None, related_object_id=None):
    """
    Create a notification for a single user, respecting their notification settings.
    Never raises — a notification failure should never break the calling flow.
    """
    try:
        setting, _ = NotificationSetting.objects.get_or_create(user=recipient)

        setting_field = _TYPE_SETTING_MAP.get(notification_type)
        if setting_field and not getattr(setting, setting_field, True):
            return None

        return Notification.objects.create(
            recipient=recipient,
            type=notification_type,
            title=title,
            message=message,
            related_object_type=related_object_type or "",
            related_object_id=related_object_id,
        )
    except Exception as e:
        logger.error(f"Failed to create notification for {recipient}: {e}", exc_info=True)
        return None


def notify_admin_dashboard(notification_type, title, message, related_object_type=None, related_object_id=None):
    """
    Notify all admins so they have full visibility into system activity.
    Bypasses per-user settings — admins always see everything.
    Never raises.
    """
    try:
        return notify_admins(
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
        )
    except Exception as e:
        logger.error(f"Failed to notify admins: {e}", exc_info=True)
        return []