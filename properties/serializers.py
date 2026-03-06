from rest_framework import serializers
from .models import Apartment, Unit, Amenity, LeaseAgreement, KeyAmenity, ApartmentAmenityDistance, KeyAmenityType

class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = ["id", "name", "icon_url"]


class KeyAmenitySerializer(serializers.ModelSerializer):
    amenity_type_display = serializers.CharField(source="get_amenity_type_display", read_only=True)

    class Meta:
        model = KeyAmenity
        fields = ["id", "amenity_type", "amenity_type_display", "name", "latitude", "longitude"]


class ApartmentAmenityDistanceSerializer(serializers.ModelSerializer):
    amenity_type_display = serializers.CharField(source="get_amenity_type_display", read_only=True)

    class Meta:
        model = ApartmentAmenityDistance
        fields = ["id", "amenity_type", "amenity_type_display", "distance_km", "nearest_name"]
        read_only_fields = ["id"]


class ApartmentAmenityDistanceCreateSerializer(serializers.Serializer):
    amenity_type = serializers.ChoiceField(choices=KeyAmenityType.choices)
    distance_km = serializers.DecimalField(max_digits=5, decimal_places=2)
    nearest_name = serializers.CharField(max_length=255, required=False, allow_blank=True)


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
    amenity_distances = ApartmentAmenityDistanceSerializer(many=True, read_only=True)

    class Meta:
        model = Apartment
        fields = [
            "id",
            "landlord",
            "name",
            "address",
            "latitude",
            "longitude",
            "overview_description",
            "exterior_image_url",
            "lease_agreement",
            "rules_and_policies",
            "amenities",
            "units",
            "amenity_distances",
            "verification_status",
            "is_approved",
            "total_units",
            "occupied_units",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "landlord",
            "verification_status",
            "is_approved",
            "total_units",
            "occupied_units",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        request = self.context.get("request")

        if request:
            user = request.user

            # Hide verification details from tenants
            if getattr(user, "role", "").upper() not in ["ADMIN", "LANDLORD"]:
                data.pop("verification_status", None)
                data.pop("is_approved", None)

        return data