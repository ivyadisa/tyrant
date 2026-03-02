from django.contrib import admin
from .models import Apartment, Unit, Amenity

try:
    from .signals import Reservation
    admin.site.register(Reservation)
except Exception:
    pass

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "landlord", "total_units", "occupied_units", "verification_status")
    list_filter = ("verification_status",)
    search_fields = ("name", "landlord__email", "address")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("unit_number_or_id", "apartment", "status", "price_per_month")
    list_filter = ("status", "category", "type")
    search_fields = ("unit_number_or_id", "apartment__name")
