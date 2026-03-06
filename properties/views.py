import math
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Apartment,
    Unit,
    Amenity,
    LeaseAgreement,
    KeyAmenity,
)

from .serializers import (
    ApartmentSerializer,
    UnitSerializer,
    AmenitySerializer,
    LeaseAgreementSerializer,
    LeaseAgreementUploadSerializer,
    KeyAmenitySerializer,
)


# --------------------------------------------------
# Utility: Haversine Distance
# --------------------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# --------------------------------------------------
# Occupancy Statistics API
# --------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def occupancy_stats(request):

    total = Unit.objects.count()
    occupied = Unit.objects.filter(status="OCCUPIED").count()
    vacant = Unit.objects.filter(status="VACANT").count()
    reserved = Unit.objects.filter(status="RESERVED").count()
    maintenance = Unit.objects.filter(status="MAINTENANCE").count()

    occupancy_rate = (occupied / total * 100) if total > 0 else 0

    return Response({
        "total_units": total,
        "occupied": occupied,
        "vacant": vacant,
        "reserved": reserved,
        "maintenance": maintenance,
        "occupancy_rate": round(occupancy_rate, 2)
    })


# --------------------------------------------------
# Permissions
# --------------------------------------------------

class IsLandlordOrReadOnly(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):

        if request.method in permissions.SAFE_METHODS:
            return True

        if hasattr(obj, "landlord"):
            return obj.landlord == request.user or getattr(request.user, "role", "") == "ADMIN"

        if hasattr(obj, "apartment"):
            return obj.apartment.landlord == request.user or getattr(request.user, "role", "") == "ADMIN"

        return False


# --------------------------------------------------
# Apartment ViewSet
# --------------------------------------------------

class ApartmentViewSet(viewsets.ModelViewSet):

    queryset = Apartment.objects.all()
    serializer_class = ApartmentSerializer
    permission_classes = [IsLandlordOrReadOnly]

    def get_queryset(self):

        user = self.request.user

        qs = Apartment.objects.all().prefetch_related(
            "units",
            "amenities"
        )

        if getattr(user, "role", "").upper() == "LANDLORD":
            return qs.filter(landlord=user)

        if getattr(user, "role", "").upper() == "ADMIN" or user.is_staff:
            return qs

        return qs.filter(
            verification_status="VERIFIED",
            is_approved=True
        )

    def perform_create(self, serializer):

        serializer.save(
            landlord=self.request.user,
            verification_status="PENDING",
            is_approved=False
        )

    # ----------------------------
    # Admin Pending Apartments
    # ----------------------------

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAdminUser]
    )
    def pending(self, request):

        apartments = Apartment.objects.filter(
            verification_status="PENDING"
        )

        serializer = self.get_serializer(apartments, many=True)

        return Response(serializer.data)

    # ----------------------------
    # Approve Apartment
    # ----------------------------

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAdminUser]
    )
    def approve(self, request, pk=None):

        apartment = self.get_object()

        apartment.verification_status = "VERIFIED"
        apartment.is_approved = True
        apartment.save()

        return Response({
            "message": "Apartment approved successfully"
        })

    # ----------------------------
    # Reject Apartment
    # ----------------------------

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[permissions.IsAdminUser]
    )
    def reject(self, request, pk=None):

        apartment = self.get_object()

        apartment.verification_status = "REJECTED"
        apartment.is_approved = False
        apartment.save()

        return Response({
            "message": "Apartment rejected"
        })

    # ----------------------------
    # Apartment Search
    # ----------------------------

    @action(detail=False, methods=["get"])
    def search(self, request):

        queryset = self.get_queryset()

        name = request.query_params.get("name")

        if name:
            queryset = queryset.filter(name__icontains=name)

        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")

        if min_price:
            queryset = queryset.filter(units__price_per_month__gte=min_price)

        if max_price:
            queryset = queryset.filter(units__price_per_month__lte=max_price)

        serializer = self.get_serializer(queryset.distinct(), many=True)

        return Response(serializer.data)

    # ----------------------------
    # Nearby Apartments
    # ----------------------------

    @action(detail=False, methods=["get"])
    def nearby(self, request):

        try:
            lat = float(request.query_params.get("latitude"))
            lon = float(request.query_params.get("longitude"))
            radius = float(request.query_params.get("radius", 10))

        except (TypeError, ValueError):

            return Response(
                {"detail": "latitude and longitude required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        apartments = self.get_queryset().filter(
            latitude__isnull=False,
            longitude__isnull=False
        )

        results = []

        for apt in apartments:

            dist = haversine_distance(
                lat,
                lon,
                float(apt.latitude),
                float(apt.longitude)
            )

            if dist <= radius:
                results.append((dist, apt))

        results.sort(key=lambda x: x[0])

        serializer = self.get_serializer(
            [apt for _, apt in results],
            many=True
        )

        return Response(serializer.data)


# --------------------------------------------------
# Unit ViewSet
# --------------------------------------------------

class UnitViewSet(viewsets.ModelViewSet):

    queryset = Unit.objects.select_related("apartment").all()
    serializer_class = UnitSerializer
    permission_classes = [IsLandlordOrReadOnly]

    def get_queryset(self):

        user = self.request.user
        qs = self.queryset

        apartment = self.request.query_params.get("apartment")

        if apartment:
            qs = qs.filter(apartment__id=apartment)

        if getattr(user, "role", "").upper() == "LANDLORD":
            qs = qs.filter(apartment__landlord=user)

        return qs

    def perform_create(self, serializer):

        apartment = serializer.validated_data.get("apartment")

        if getattr(self.request.user, "role", "").upper() == "LANDLORD":
            if apartment.landlord != self.request.user:
                raise PermissionDenied("You can only create units for your own apartment")

        unit = serializer.save()

        unit.apartment.recalc_unit_counts()

    def perform_update(self, serializer):

        unit = serializer.save()

        unit.apartment.recalc_unit_counts()


# --------------------------------------------------
# Lease Agreement ViewSet
# --------------------------------------------------

class LeaseAgreementViewSet(viewsets.ModelViewSet):

    queryset = LeaseAgreement.objects.select_related("apartment").all()
    serializer_class = LeaseAgreementSerializer
    permission_classes = [IsLandlordOrReadOnly]

    def get_queryset(self):

        user = self.request.user
        qs = self.queryset

        apartment = self.request.query_params.get("apartment")

        if apartment:
            qs = qs.filter(apartment__id=apartment)

        if getattr(user, "role", "").upper() == "LANDLORD":
            qs = qs.filter(apartment__landlord=user)

        return qs

    def get_serializer_class(self):

        if self.action in ["create", "upload"]:
            return LeaseAgreementUploadSerializer

        return LeaseAgreementSerializer

    @action(detail=False, methods=["post"])
    def upload(self, request):

        apartment_id = request.query_params.get("apartment_id")

        if not apartment_id:
            return Response(
                {"detail": "apartment_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        apartment = get_object_or_404(Apartment, id=apartment_id)

        if apartment.landlord != request.user and getattr(request.user, "role", "") != "ADMIN":

            return Response(
                {"detail": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():

            latest = LeaseAgreement.objects.filter(
                apartment=apartment
            ).order_by("-version").first()

            new_version = latest.version + 1 if latest else 1

            lease = LeaseAgreement.objects.create(
                apartment=apartment,
                document=serializer.validated_data["document"],
                version=new_version
            )

            apartment.lease_agreement = lease
            apartment.save(update_fields=["lease_agreement"])

            return Response(
                LeaseAgreementSerializer(lease).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------------------------------------
# Key Amenity ViewSet
# --------------------------------------------------

class KeyAmenityViewSet(viewsets.ModelViewSet):

    queryset = KeyAmenity.objects.all()
    serializer_class = KeyAmenitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        amenity_type = self.request.query_params.get("amenity_type")

        if amenity_type:
            return KeyAmenity.objects.filter(amenity_type=amenity_type)

        return KeyAmenity.objects.all()