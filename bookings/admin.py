from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "booking_confirmation_code",
        "tenant",
        "landlord",
        "unit",
        "booking_amount",
        "booking_status",
        "payment_status",
        "move_in_date",
        "created_at",
    )
    list_filter = (
        "booking_status",
        "payment_status",
        "created_at",
        "move_in_date",
    )
    search_fields = (
        "booking_confirmation_code",
        "tenant__email",
        "landlord__email",
        "unit__unit_number_or_id",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "reservation_date")

    fieldsets = (
        ("Booking Details", {
            "fields": (
                "booking_confirmation_code",
                "tenant",
                "landlord",
                "unit",
                "booking_amount",
                "move_in_date",
            ),
        }),
        ("Status", {
            "fields": (
                "booking_status",
                "payment_status",
            ),
        }),
        ("Timestamps", {
            "fields": (
                "reservation_date",
                "created_at",
                "updated_at",
            ),
        }),
    )
