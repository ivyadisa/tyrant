from rest_framework import viewsets, status, permissions
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from .models import Apartment, Unit, Amenity
from .serializers import ApartmentSerializer, UnitSerializer, AmenitySerializer
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
        serializer.save(landlord=self.request.user)


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
