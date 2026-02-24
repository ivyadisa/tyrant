from rest_framework import serializers
from .models import Booking

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = [
            "id",
            "tenant",
            "landlord",
            "booking_confirmation_code",
            "booking_status",
            "payment_status",
            "created_at",
            "updated_at",
        ]
