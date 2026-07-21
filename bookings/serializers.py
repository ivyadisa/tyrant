from rest_framework import serializers
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    unit_number = serializers.SerializerMethodField()
    apartment_name = serializers.SerializerMethodField()
    apartment_address = serializers.SerializerMethodField()
    price_per_month = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    tenant_email = serializers.SerializerMethodField()
    tenant_phone = serializers.SerializerMethodField()
    landlord_name = serializers.SerializerMethodField()
    landlord_email = serializers.SerializerMethodField()
    landlord_phone = serializers.SerializerMethodField()

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
            "lease_agreement",
        ]

    def get_unit_number(self, obj):
        return obj.unit.unit_number_or_id if obj.unit else None

    def get_apartment_name(self, obj):
        return obj.unit.apartment.name if obj.unit and obj.unit.apartment else None

    def get_apartment_address(self, obj):
        return obj.unit.apartment.address if obj.unit and obj.unit.apartment else None

    def get_price_per_month(self, obj):
        return obj.unit.price_per_month if obj.unit else None

    def get_tenant_name(self, obj):
        if not obj.tenant:
            return None
        return obj.tenant.full_name or obj.tenant.username

    def get_tenant_email(self, obj):
        return obj.tenant.email if obj.tenant else None

    def get_tenant_phone(self, obj):
        return obj.tenant.phone_number if obj.tenant else None

    def get_landlord_name(self, obj):
        if not obj.landlord:
            return None
        return obj.landlord.full_name or obj.landlord.username

    def get_landlord_email(self, obj):
        return obj.landlord.email if obj.landlord else None

    def get_landlord_phone(self, obj):
        return obj.landlord.phone_number if obj.landlord else None