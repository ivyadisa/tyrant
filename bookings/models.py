import uuid
from django.db import models
from django.conf import settings
from properties.models import Unit

User = settings.AUTH_USER_MODEL

class Booking(models.Model):
    BOOKING_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("PAID", "Paid"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("UNPAID", "Unpaid"),
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="bookings")
    tenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenant_bookings")
    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name="landlord_bookings")
    booking_status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default="PENDING")
    reservation_date = models.DateTimeField(auto_now_add=True)
    move_in_date = models.DateField()
    booking_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="UNPAID")
    booking_confirmation_code = models.CharField(max_length=10, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking {self.booking_confirmation_code} - {self.tenant}"

    def save(self, *args, **kwargs):
        if not self.booking_confirmation_code:
            self.booking_confirmation_code = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)
