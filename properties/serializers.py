from rest_framework import serializers
from django.db import models
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth import get_user_model
from .models import Apartment, Unit, Amenity, LeaseAgreement, KeyAmenity, ApartmentAmenityDistance, KeyAmenityType, Review, Tour

User = get_user_model()

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


class ApartmentLandlordSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "phone_number"]


class ApartmentSerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True, read_only=True)
    landlord_info = ApartmentLandlordSerializer(source="landlord", read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    amenity_ids = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="Accepts amenity UUIDs or amenity names.",
    )
    lease_agreement = LeaseAgreementSerializer(read_only=True)
    amenity_distances = ApartmentAmenityDistanceSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    exterior_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Apartment
        fields = [
            "id", "landlord", "name", "address", "latitude", "longitude",
            "landlord_info",
            "overview_description", "exterior_image", "exterior_image_url", "virtual_tour_url",
            "lease_agreement", "rules_and_policies", "amenities", "amenity_ids", "units", "amenity_distances",
            "verification_status",
            "total_units", "occupied_units", "created_at", "updated_at",
            "average_rating", "review_count"
        ]
        read_only_fields = ["landlord", "total_units", "occupied_units", "created_at", "updated_at"]

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews.exists():
            return None
        return round(reviews.aggregate(models.Avg("rating"))["rating__avg"], 1)

    def get_review_count(self, obj):
        return obj.reviews.count()

    def get_exterior_image_url(self, obj):
        if obj.exterior_image:
            return obj.exterior_image.url
        return obj.exterior_image_url

    def validate_amenity_ids(self, value):
        amenities = []
        for raw_value in value:
            token = str(raw_value).strip()
            if not token:
                continue

            try:
                amenity = Amenity.objects.get(pk=token)
            except (Amenity.DoesNotExist, DjangoValidationError, ValueError, TypeError):
                amenity = Amenity.objects.filter(name__iexact=token).first()
                if amenity is None:
                    amenity = Amenity.objects.create(name=token)

            amenities.append(amenity)

        return amenities

    def create(self, validated_data):
        amenities = validated_data.pop("amenity_ids", None)
        apartment = super().create(validated_data)
        if amenities is not None:
            apartment.amenities.set(amenities)
        return apartment

    def update(self, instance, validated_data):
        amenities = validated_data.pop("amenity_ids", None)
        apartment = super().update(instance, validated_data)
        if amenities is not None:
            apartment.amenities.set(amenities)
        return apartment


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "apartment", "user", "user_name", "rating", "comment", "is_verified_tenant", "created_at", "updated_at"]
        read_only_fields = ["user", "created_at", "updated_at"]


class TourSerializer(serializers.ModelSerializer):
    apartment_name = serializers.CharField(source="apartment.name", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Tour
        fields = ["id", "apartment", "apartment_name", "user", "user_name", "tour_type", "scheduled_date", "scheduled_time", "status", "notes", "contact_phone", "created_at", "updated_at"]
        read_only_fields = ["user", "status", "created_at", "updated_at"]
