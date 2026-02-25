from rest_framework import serializers
from .models import Apartment, Unit, Amenity, LeaseAgreement

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ["id", "name", "icon_url"]


class LeaseAgreementSerializer(serializers.ModelSerializer):
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = LeaseAgreement
        fields = ["id", "apartment", "document", "file_hash", "version", "created_at", "updated_at", "file_size"]
        read_only_fields = ["id", "file_hash", "version", "created_at", "updated_at"]

    def get_file_size(self, obj):
        if obj.document:
            return obj.document.size
        return None

    def validate_document(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 10MB.")
        return value


class LeaseAgreementUploadSerializer(serializers.Serializer):
    """Used for uploading new lease agreements - apartment is set by view."""
    document = serializers.FileField()

    def validate_document(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size must be less than 10MB.")
        if value.content_type != 'application/pdf':
            raise serializers.ValidationError("Only PDF files are allowed.")
        return value

    def create(self, validated_data):
        return LeaseAgreement(**validated_data)


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
    lease_agreement = LeaseAgreementSerializer(read_only=True)

    class Meta:
        model = Apartment
        fields = [
            "id", "landlord", "name", "address", "latitude", "longitude",
            "overview_description", "exterior_image_url", "lease_agreement",
            "rules_and_policies", "amenities", "units",
            "verification_status",
            "total_units", "occupied_units", "created_at", "updated_at"
        ]
        read_only_fields = ["landlord", "total_units", "occupied_units", "created_at", "updated_at"]
