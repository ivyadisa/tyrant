from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Booking
from datetime import date


@receiver(post_save, sender=Booking)
def booking_post_save(sender, instance, created, **kwargs):
    """Update unit status when booking is created or payment status changes."""
    unit = instance.unit
    
    # Only process active bookings (not cancelled)
    if instance.booking_status == "CANCELLED":
        return
    
    # Determine status based on payment and move_in_date
    if instance.payment_status == "COMPLETED":
        # Payment confirmed: Check if move_in_date has passed
        if instance.move_in_date <= date.today():
            unit.status = "OCCUPIED"
        else:
            unit.status = "RESERVED"
    elif instance.booking_status in ["PENDING", "CONFIRMED"]:
        # Booking created or confirmed but not paid yet
        unit.status = "RESERVED"
    
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
