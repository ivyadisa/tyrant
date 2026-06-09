from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Booking
from datetime import date


@receiver(post_save, sender=Booking)
def booking_post_save(sender, instance, created, **kwargs):
    """Update unit status when booking is created or payment status changes."""
    unit = instance.unit

    if instance.booking_status == "CANCELLED":
        active_others = unit.bookings.exclude(id=instance.id).filter(
            booking_status__in=["PENDING", "CONFIRMED", "PAID", "COMPLETED"]
        ).exists()
        if not active_others:
            unit.status = "VACANT"
            unit.save()
            unit.apartment.recalc_unit_counts()
        return

    # For testing phase: auto-set OCCUPIED since payment is auto-completed
    if instance.booking_status in ["CONFIRMED", "PAID", "COMPLETED"]:
        unit.status = "OCCUPIED"

    unit.save()
    unit.apartment.recalc_unit_counts()


@receiver(post_delete, sender=Booking)
def booking_post_delete(sender, instance, **kwargs):
    """Reset unit status when booking is deleted."""
    unit = instance.unit
    
    # Check if there are other active bookings for this unit
    active_others = unit.bookings.filter(booking_status__in=["PENDING", "CONFIRMED", "PAID", "COMPLETED"]).exists()
    
    if not active_others:
        unit.status = "VACANT"
        unit.save()
        unit.apartment.recalc_unit_counts()
