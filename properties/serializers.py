from rest_framework import serializers
from .models import Apartment, Unit, Amenity

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ["id", "name", "icon_url"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = [
            "id", "apartment", "unit_number_or_id", "category", "type",
            "size_sqft", "price_per_month", "status", "interior_images",
            "exterior_images", "description", "last_status_updated", "created_at", "updated_at"
        ]
        read_only_fields = ["last_status_updated", "created_at", "updated_at"]


class ApartmentSerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)

    class Meta:
        model = Apartment
        fields = [
            "id", "landlord", "name", "address", "latitude", "longitude",
            "overview_description", "exterior_image_url", "lease_agreement_document_url",
            "rules_and_policies", "amenities", "units",
            "verification_status",
            "total_units", "occupied_units", "created_at", "updated_at"
        ]
        read_only_fields = ["landlord", "total_units", "occupied_units", "created_at", "updated_at"]
