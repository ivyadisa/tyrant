from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Unit, Apartment
from django.utils import timezone
from django.db import models
import uuid
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Reservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="reservations")
    tenant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reserved_on = models.DateTimeField(auto_now_add=True)
    move_in_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)  

    def __str__(self):
        return f"Resv {self.id} - {self.unit}"

@receiver(post_save, sender=Reservation)
def reservation_post_save(sender, instance, created, **kwargs):
    unit = instance.unit
    if instance.active:
        from datetime import date
        if instance.move_in_date and instance.move_in_date > date.today():
            unit.status = "RESERVED"
        else:
            unit.status = "OCCUPIED"
    else:
        active_others = unit.reservations.filter(active=True).exclude(id=instance.id).exists()
        if active_others:
            other = unit.reservations.filter(active=True).exclude(id=instance.id).last()
            unit.status = "RESERVED" if (other.move_in_date and other.move_in_date > date.today()) else "OCCUPIED"
        else:
            unit.status = "VACANT"
    unit.save()
    unit.apartment.recalc_unit_counts()


@receiver(post_delete, sender=Reservation)
def reservation_post_delete(sender, instance, **kwargs):
    unit = instance.unit
    active_others = unit.reservations.filter(active=True).exists()
    if not active_others:
        unit.status = "VACANT"
        unit.save()
        unit.apartment.recalc_unit_counts()
