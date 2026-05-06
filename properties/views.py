from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
import math
import os
import uuid

from .models import Apartment, Unit, Amenity, LeaseAgreement, KeyAmenity, ApartmentAmenityDistance, KeyAmenityType, Review, Tour
from .serializers import (
    ApartmentSerializer, UnitSerializer, AmenitySerializer, LeaseAgreementSerializer,
    LeaseAgreementUploadSerializer, KeyAmenitySerializer, ApartmentAmenityDistanceSerializer,
    ApartmentAmenityDistanceCreateSerializer, ReviewSerializer, TourSerializer
)
from django.shortcuts import get_object_or_404
from rest_framework.routers import DefaultRouter
from django.db import transaction
from django.db.models import Count, Q, Max, Min
from rest_framework.permissions import IsAuthenticated
from django.core.files.storage import default_storage


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def occupancy_stats(request):
    total = Unit.objects.count()
    occupied = Unit.objects.filter(status="OCCUPIED").count()
    vacant = Unit.objects.filter(status="VACANT").count()
    reserved = Unit.objects.filter(status="RESERVED").count()
    maintenance = Unit.objects.filter(status="MAINTENANCE").count()

    occupancy_rate = (occupied / total * 100) if total > 0 else 0.0

    return Response({
        "total_units": total,
        "occupied": occupied,
        "vacant": vacant,
        "reserved": reserved,
        "maintenance": maintenance,
        "occupancy_rate": round(occupancy_rate, 2)
    })

class IsLandlordOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        # Allow unauthenticated users to read (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        if hasattr(obj, "landlord"):
            return obj.landlord == request.user or getattr(request.user, "role", "") == "ADMIN"
        if hasattr(obj, "apartment"):
            return obj.apartment.landlord == request.user or getattr(request.user, "role", "") == "ADMIN"
        return False

class ApartmentViewSet(viewsets.ModelViewSet):
    queryset = Apartment.objects.all()
    serializer_class = ApartmentSerializer
    permission_classes = [IsLandlordOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = Apartment.objects.all().prefetch_related("amenity_distances", "units")

        distance_filter = self.request.query_params.get("max_distance")
        amenity_filter = self.request.query_params.get("amenity_type")

        if distance_filter and amenity_filter:
            try:
                max_dist = float(distance_filter)
                qs = qs.filter(
                    amenity_distances__amenity_type=amenity_filter,
                    amenity_distances__distance_km__lte=max_dist
                ).distinct()
            except ValueError:
                pass

        # Only filter by landlord if the user is authenticated AND is a landlord
        if user and user.is_authenticated and getattr(user, "role", "").upper() == "LANDLORD":
            return qs.filter(landlord=user)
        return qs

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        queryset = self.get_queryset()

        name = request.query_params.get("name")
        if name:
            queryset = queryset.filter(name__icontains=name)

        verification_status = request.query_params.get("verification_status")
        if verification_status:
            queryset = queryset.filter(verification_status=verification_status)

        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        if min_price or max_price:
            queryset = queryset.filter(units__price_per_month__isnull=False)
            if min_price:
                queryset = queryset.filter(units__price_per_month__gte=min_price)
            if max_price:
                queryset = queryset.filter(units__price_per_month__lte=max_price)

        beds = request.query_params.get("beds")
        if beds:
            try:
                beds = int(beds)
                queryset = queryset.filter(units__type__icontains=str(beds))
            except ValueError:
                pass

        property_type = request.query_params.get("property_type")
        if property_type:
            queryset = queryset.filter(units__type__icontains=property_type.lower())

        location = request.query_params.get("location")
        if location:
            queryset = queryset.filter(address__icontains=location)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        featured_apts = Apartment.objects.prefetch_related(
            "amenity_distances", "units"
        ).order_by("-created_at")[:6]
        serializer = self.get_serializer(featured_apts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="popular-locations")
    def popular_locations(self, request):
        from django.db.models import Count
        locations = (
            Apartment.objects.filter(is_approved=True)
            .values("name")
            .annotate(property_count=Count("id"))
            .order_by("-property_count")[:6]
        )
        return Response(locations)

    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby(self, request):
        try:
            lat = float(request.query_params.get("latitude"))
            lon = float(request.query_params.get("longitude"))
            radius_km = float(request.query_params.get("radius", 10))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Valid latitude, longitude, and optional radius (km) required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        apartments = Apartment.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        )

        if getattr(request.user, "role", "").upper() == "LANDLORD":
            apartments = apartments.filter(landlord=request.user)

        results = []
        for apt in apartments:
            try:
                dist = haversine_distance(lat, lon, float(apt.latitude), float(apt.longitude))
                if dist <= radius_km:
                    results.append((dist, apt))
            except (TypeError, ValueError):
                pass

        results.sort(key=lambda x: x[0])
        serializer = self.get_serializer([apt for _, apt in results], many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="amenity-distances")
    def list_amenity_distances(self, request, pk=None):
        apartment = self.get_object()
        distances = apartment.amenity_distances.all()
        serializer = ApartmentAmenityDistanceSerializer(distances, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="set-amenity-distances")
    def set_amenity_distances(self, request, pk=None):
        apartment = self.get_object()

        if apartment.landlord != request.user and getattr(request.user, "role", "").upper() != "ADMIN":
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        serializer = ApartmentAmenityDistanceCreateSerializer(data=request.data, many=True)
        if serializer.is_valid():
            with transaction.atomic():
                ApartmentAmenityDistance.objects.filter(apartment=apartment).delete()
                for item in serializer.validated_data:
                    ApartmentAmenityDistance.objects.create(
                        apartment=apartment,
                        amenity_type=item["amenity_type"],
                        distance_km=item["distance_km"],
                        nearest_name=item.get("nearest_name", "")
                    )
            return Response(
                ApartmentAmenityDistanceSerializer(apartment.amenity_distances.all(), many=True).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="upload-image")
    def upload_image(self, request, pk=None):
        apartment = self.get_object()
        
        if apartment.landlord != request.user and getattr(request.user, "role", "").upper() != "ADMIN":
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        
        image = request.FILES.get("image")
        if not image:
            return Response({"error": "No image provided"}, status=400)
        
        apartment.exterior_image = image
        apartment.save(update_fields=["exterior_image"])
        
        return Response({
            "message": "Image uploaded successfully",
            "image_url": apartment.exterior_image.url
        })

    @action(detail=True, methods=["post"], url_path="set-virtual-tour")
    def set_virtual_tour(self, request, pk=None):
        apartment = self.get_object()
        
        if apartment.landlord != request.user and getattr(request.user, "role", "").upper() != "ADMIN":
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        
        tour_url = request.data.get("virtual_tour_url")
        if not tour_url:
            return Response({"error": "virtual_tour_url is required"}, status=400)
        
        apartment.virtual_tour_url = tour_url
        apartment.save(update_fields=["virtual_tour_url"])
        
        return Response({"message": "Virtual tour URL set successfully"})

    def perform_create(self, serializer):
        user = self.request.user
        role = getattr(user, "role", "").upper()

        if role not in {"LANDLORD", "ADMIN"}:
            raise PermissionDenied("Only landlords or admins can create apartments.")

        if role == "LANDLORD":
            if not getattr(user, "email_verified", False):
                raise PermissionDenied("Please verify your email before creating an apartment.")
            if getattr(user, "status", "").upper() == "SUSPENDED":
                raise PermissionDenied("Your account is suspended.")
            if getattr(user, "verification_status", "").upper() != "VERIFIED":
                raise PermissionDenied("Your account must be verified before creating an apartment.")

            # Count existing apartments vs completed subscription payments
            #from wallet.models import WalletTransaction
            #completed_subscriptions = WalletTransaction.objects.filter(
            #    wallet__user=user,
            #    transaction_type="SUBSCRIPTION",
            #    status="COMPLETED",
            #).count()

            #existing_apartments = Apartment.objects.filter(landlord=user).count()

            #if completed_subscriptions <= existing_apartments:
            #    raise PermissionDenied(
            #        "You must complete a subscription payment before listing a new property."
            #    )

        serializer.save(landlord=user)

class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.select_related("apartment").all()
    serializer_class = UnitSerializer
    permission_classes = [IsLandlordOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        apt = self.request.query_params.get("apartment")
        if apt:
            qs = qs.filter(apartment__id=apt)
        if getattr(user, "role", "").upper() == "LANDLORD":
            qs = qs.filter(apartment__landlord=user)
        return qs

    def perform_create(self, serializer):
        apartment = serializer.validated_data.get("apartment")
        if getattr(self.request.user, "role", "").upper() == "LANDLORD" and apartment.landlord != self.request.user:
            raise PermissionError("You can only create units for your own apartments.")
        instance = serializer.save()
        instance.apartment.recalc_unit_counts()

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.apartment.recalc_unit_counts()

    @action(detail=True, methods=["patch"], url_path="set-status", permission_classes=[IsLandlordOrReadOnly])
    def set_status(self, request, pk=None):
        unit = self.get_object()
        status_value = request.data.get("status")
        if status_value not in dict(unit._meta.get_field("status").choices).keys():
            return Response({"detail": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            unit.status = status_value
            unit.save()
            unit.apartment.recalc_unit_counts()
        return Response(UnitSerializer(unit).data)

    @action(detail=True, methods=["post"], url_path="upload-images", permission_classes=[IsLandlordOrReadOnly])
    def upload_images(self, request, pk=None):
        unit = self.get_object()

        if unit.apartment.landlord != request.user and getattr(request.user, "role", "").upper() != "ADMIN":
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        image_files = request.FILES.getlist("images")
        if not image_files:
            return Response({"detail": "No images provided. Use form-data key 'images'."}, status=status.HTTP_400_BAD_REQUEST)

        image_type = request.data.get("image_type", "interior").strip().lower()
        if image_type not in {"interior", "exterior"}:
            return Response({"detail": "image_type must be either 'interior' or 'exterior'."}, status=status.HTTP_400_BAD_REQUEST)

        target_field = "interior_images" if image_type == "interior" else "exterior_images"
        existing_images = list(getattr(unit, target_field) or [])

        uploaded_urls = []
        for image in image_files:
            if not (image.content_type or "").startswith("image/"):
                return Response({"detail": f"Invalid file type for {image.name}. Only image files are allowed."}, status=status.HTTP_400_BAD_REQUEST)

            ext = os.path.splitext(image.name)[1] or ".jpg"
            file_name = f"units/{unit.id}/{uuid.uuid4().hex}{ext}"
            saved_path = default_storage.save(file_name, image)
            file_url = request.build_absolute_uri(default_storage.url(saved_path))
            uploaded_urls.append(file_url)

        existing_images.extend(uploaded_urls)
        setattr(unit, target_field, existing_images)
        unit.save(update_fields=[target_field, "updated_at"])

        return Response(
            {
                "message": f"{len(uploaded_urls)} image(s) uploaded successfully.",
                "image_type": image_type,
                target_field: existing_images,
                "uploaded": uploaded_urls,
            },
            status=status.HTTP_200_OK,
        )


class LeaseAgreementViewSet(viewsets.ModelViewSet):
    queryset = LeaseAgreement.objects.select_related("apartment").all()
    serializer_class = LeaseAgreementSerializer
    permission_classes = [IsLandlordOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        apt = self.request.query_params.get("apartment")
        if apt:
            qs = qs.filter(apartment__id=apt)
        if getattr(user, "role", "").upper() == "LANDLORD":
            qs = qs.filter(apartment__landlord=user)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'upload_lease'):
            return LeaseAgreementUploadSerializer
        return LeaseAgreementSerializer

    @action(detail=False, methods=['post'], url_path='upload', permission_classes=[IsLandlordOrReadOnly])
    def upload_lease(self, request, apartment_id=None):
        apartment_id = request.query_params.get('apartment_id') or self.kwargs.get('apartment_id')
        if not apartment_id:
            return Response({"detail": "apartment_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        apartment = get_object_or_404(Apartment, id=apartment_id)

        if apartment.landlord != request.user and getattr(request.user, "role", "").upper() != "ADMIN":
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            latest_version = LeaseAgreement.objects.filter(apartment=apartment).order_by('-version').first()
            new_version = (latest_version.version + 1) if latest_version else 1

            lease = LeaseAgreement.objects.create(
                apartment=apartment,
                document=serializer.validated_data['document'],
                version=new_version
            )
            apartment.lease_agreement = lease
            apartment.save(update_fields=['lease_agreement'])

            return Response(
                LeaseAgreementSerializer(lease).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='verify')
    def verify_document(self, request, pk=None):
        lease = self.get_object()
        data = {
            "id": lease.id,
            "version": lease.version,
            "file_hash": lease.file_hash,
            "created_at": lease.created_at,
            "verified": True
        }
        return Response(data)


class KeyAmenityViewSet(viewsets.ModelViewSet):
    queryset = KeyAmenity.objects.all()
    serializer_class = KeyAmenitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        amenity_type = self.request.query_params.get("amenity_type")
        if amenity_type:
            return KeyAmenity.objects.filter(amenity_type=amenity_type)
        return KeyAmenity.objects.all()


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Review.objects.select_related("apartment", "user").all()
        apartment_id = self.request.query_params.get("apartment")
        if apartment_id:
            queryset = queryset.filter(apartment_id=apartment_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TourViewSet(viewsets.ModelViewSet):
    queryset = Tour.objects.all()
    serializer_class = TourSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Tour.objects.select_related("apartment", "user").all()
        
        if getattr(user, "role", "").upper() == "LANDLORD":
            queryset = queryset.filter(apartment__landlord=user)
        else:
            queryset = queryset.filter(user=user)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["patch"], url_path="update-status")
    def update_status(self, request, pk=None):
        tour = self.get_object()
        new_status = request.data.get("status")
        if new_status not in dict(Tour.TOUR_STATUS_CHOICES).keys():
            return Response({"detail": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        
        if getattr(request.user, "role", "").upper() != "LANDLORD" and request.user != tour.user:
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        
        tour.status = new_status
        tour.save()
        return Response(TourSerializer(tour).data)
