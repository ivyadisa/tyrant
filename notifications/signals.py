"""
Signal handlers for automatic notifications.
These will be imported in the notifications app's ready() method.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

User = settings.AUTH_USER_MODEL


def register_notification_signals():
    """Register all notification signals."""
    from .models import (
        Notification,
        NotificationType,
        create_notification,
        notify_admins,
        notify_landlord,
    )
    from users.models import User
    from bookings.models import Booking
    from properties.models import Apartment, VerificationStatus

    # ================= USER SIGNALS =================

    @receiver(post_save, sender=User)
    def user_created_notification(sender, instance, created, **kwargs):
        """Notify admins when a new user registers."""
        if created:
            # Don't notify for admin users (created by admin)
            if instance.role == User.ROLE_ADMIN:
                return

            notify_admins(
                notification_type=NotificationType.USER_REGISTRATION,
                title="New User Registration",
                message=f"A new {instance.get_role_display()} '{instance.username}' has registered and requires verification.",
                related_object_type="User",
                related_object_id=instance.id,
            )

    # ================= BOOKING SIGNALS =================

    @receiver(post_save, sender=Booking)
    def booking_created_notification(sender, instance, created, **kwargs):
        """Notify landlord when a new booking is requested."""
        if created and instance.booking_status == "PENDING":
            notify_landlord(
                landlord=instance.landlord,
                notification_type=NotificationType.BOOKING_REQUEST,
                title="New Booking Request",
                message=f"{instance.tenant.full_name or instance.tenant.username} has requested to book {instance.unit}.",
                related_object_type="Booking",
                related_object_id=instance.id,
            )

            # Also notify admins
            notify_admins(
                notification_type=NotificationType.BOOKING_REQUEST,
                title="New Booking Request",
                message=f"A new booking request for {instance.unit} from {instance.tenant.username} is pending approval.",
                related_object_type="Booking",
                related_object_id=instance.id,
            )

    @receiver(post_save, sender=Booking)
    def booking_confirmed_notification(sender, instance, created, **kwargs):
        """Notify tenant when booking is confirmed."""
        if not created and instance.booking_status == "CONFIRMED":
            # Get previous status
            old_status = Booking.objects.get(id=instance.id).booking_status
            if old_status != "CONFIRMED":
                create_notification(
                    recipient=instance.tenant,
                    notification_type=NotificationType.BOOKING_CONFIRMED,
                    title="Booking Confirmed",
                    message=f"Your booking for {instance.unit} has been confirmed!",
                    related_object_type="Booking",
                    related_object_id=instance.id,
                )

    @receiver(post_save, sender=Booking)
    def booking_cancelled_notification(sender, instance, created, **kwargs):
        """Notify parties when booking is cancelled."""
        if not created and instance.booking_status == "CANCELLED":
            # Notify tenant
            create_notification(
                recipient=instance.tenant,
                notification_type=NotificationType.BOOKING_CANCELLED,
                title="Booking Cancelled",
                message=f"Your booking for {instance.unit} has been cancelled.",
                related_object_type="Booking",
                related_object_id=instance.id,
            )

            # Notify landlord
            notify_landlord(
                landlord=instance.landlord,
                notification_type=NotificationType.BOOKING_CANCELLED,
                title="Booking Cancelled",
                message=f"Booking for {instance.unit} by {instance.tenant.username} has been cancelled.",
                related_object_type="Booking",
                related_object_id=instance.id,
            )

    @receiver(post_save, sender=Booking)
    def booking_payment_notification(sender, instance, created, **kwargs):
        """Notify landlord when payment is received."""
        if not created and instance.payment_status == "COMPLETED":
            # Notify landlord
            notify_landlord(
                landlord=instance.landlord,
                notification_type=NotificationType.BOOKING_PAYMENT,
                title="Payment Received",
                message=f"Payment of KES {instance.booking_amount} received for booking {instance.booking_confirmation_code}.",
                related_object_type="Booking",
                related_object_id=instance.id,
            )

    # ================= APARTMENT SIGNALS =================

    @receiver(post_save, sender=Apartment)
    def apartment_submitted_notification(sender, instance, created, **kwargs):
        """Notify admins when a new apartment is submitted for verification."""
        if created or (
            not created
            and instance.verification_status == VerificationStatus.PENDING
            and Apartment.objects.get(id=instance.id).verification_status
            != VerificationStatus.PENDING
        ):
            # Check if this is a new submission (was NOT_REQUESTED -> PENDING)
            notify_admins(
                notification_type=NotificationType.APARTMENT_SUBMITTED,
                title="New Apartment Submission",
                message=f"New apartment '{instance.name}' by {instance.landlord.username} submitted for verification.",
                related_object_type="Apartment",
                related_object_id=instance.id,
            )

    @receiver(post_save, sender=Apartment)
    def apartment_verified_notification(sender, instance, created, **kwargs):
        """Notify landlord when apartment is verified."""
        if not created and instance.verification_status == VerificationStatus.VERIFIED:
            # Get old status
            old = Apartment.objects.get(id=instance.id).verification_status
            if old != VerificationStatus.VERIFIED:
                create_notification(
                    recipient=instance.landlord,
                    notification_type=NotificationType.APARTMENT_VERIFIED,
                    title="Apartment Verified",
                    message=f"Your apartment '{instance.name}' has been verified and is pending final approval.",
                    related_object_type="Apartment",
                    related_object_id=instance.id,
                )

    @receiver(post_save, sender=Apartment)
    def apartment_approved_notification(sender, instance, created, **kwargs):
        """Notify landlord when apartment is approved."""
        if not created and instance.is_approved:
            # Get old is_approved
            old = Apartment.objects.get(id=instance.id).is_approved
            if not old:
                create_notification(
                    recipient=instance.landlord,
                    notification_type=NotificationType.APARTMENT_APPROVED,
                    title="Apartment Approved",
                    message=f"Congratulations! Your apartment '{instance.name}' has been approved and is now live.",
                    related_object_type="Apartment",
                    related_object_id=instance.id,
                )


# Note: Signals are connected when this module is imported
# Just import this module to register signals:
# import notifications.signals