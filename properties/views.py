from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response

from verification.models import Verification
from .models import Apartment, Unit, Amenity, LeaseAgreement
from .serializers import ApartmentSerializer, UnitSerializer, AmenitySerializer, LeaseAgreementSerializer, LeaseAgreementUploadSerializer
from django.shortcuts import get_object_or_404
from rest_framework.routers import DefaultRouter
from django.db import transaction
from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated

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
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
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
        if getattr(user, "role", "").upper() == "LANDLORD":
            return Apartment.objects.filter(landlord=user)
        return Apartment.objects.all()

    def perform_create(self, serializer):
        if not self.request.user.is_staff:
            raise PermissionDenied("Only admins can create verification tasks.")

        apartment = serializer.validated_data["apartment"]

        if apartment.verification_status == "VERIFIED":
            raise ValidationError("Apartment already verified.")

        serializer.save(landlord=self.request.user, status = Verification.Status.ASSIGNED)


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
