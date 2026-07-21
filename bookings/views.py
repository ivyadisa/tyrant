from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db import transaction

from .models import Booking
from .serializers import BookingSerializer
from .permissions import IsAdminRole, IsLandlordOfBooking, IsTenantOrLandlordOfBooking
from notifications.services import notify, notify_admin_dashboard
from notifications.models import NotificationType


class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        unit = serializer.validated_data["unit"]
        has_active_booking = Booking.objects.filter(
            unit=unit,
            booking_status__in=["PENDING", "CONFIRMED", "PAID", "COMPLETED"],
            payment_status__in=["UNPAID", "PENDING", "COMPLETED"],
        ).exists()
        if has_active_booking:
            return Response(
                {"error": "This unit is already reserved and cannot be booked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        unit = serializer.validated_data["unit"]
        tenant = self.request.user
        landlord = unit.apartment.landlord
        booking = serializer.save(
            tenant=tenant,
            landlord=landlord,
            booking_status="PENDING",
            payment_status="UNPAID",
        )

        message = f"{tenant.get_full_name() or tenant.username} requested to book Unit {unit.unit_number_or_id} at {unit.apartment.name}."

        notify(
            recipient=landlord,
            notification_type=NotificationType.BOOKING_REQUEST,
            title="New Booking Request",
            message=message,
            related_object_type="Booking",
            related_object_id=booking.id,
        )

        notify_admin_dashboard(
            notification_type=NotificationType.BOOKING_REQUEST,
            title="New Booking Request",
            message=message,
            related_object_type="Booking",
            related_object_id=booking.id,
        )


class TenantBookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects
            .select_related("tenant", "landlord", "unit", "unit__apartment")
            .filter(tenant=self.request.user)
            .order_by("-created_at")
        )


class LandlordBookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects
            .select_related("tenant", "landlord", "unit", "unit__apartment")
            .filter(landlord=self.request.user)
            .order_by("-created_at")
        )


class SuperAdminBookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["booking_status", "payment_status", "tenant", "landlord"]
    ordering_fields = ["created_at", "move_in_date", "booking_amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Booking.objects
            .select_related("tenant", "landlord", "unit", "unit__apartment")
            .all()
            .order_by("-created_at")
        )


class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    queryset = Booking.objects.all()
    lookup_field = "pk"

    def get_object(self):
        booking = super().get_object()
        user = self.request.user
        is_admin = getattr(user, "role", None) == "ADMIN" or user.is_staff or user.is_superuser
        if not is_admin and user not in (booking.tenant, booking.landlord):
            self.permission_denied(
                self.request,
                message="You do not have permission to view this booking.",
            )
        return booking


class BookingCancelView(generics.UpdateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsTenantOrLandlordOfBooking]
    queryset = Booking.objects.all()

    def update(self, request, *args, **kwargs):
        booking = self.get_object()

        if booking.booking_status in ["CANCELLED", "COMPLETED"]:
            return Response(
                {"error": "Booking already cancelled or completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cancelling_user = request.user
        other_party = booking.landlord if cancelling_user == booking.tenant else booking.tenant

        with transaction.atomic():
            booking.booking_status = "CANCELLED"
            booking.payment_status = "REFUNDED"
            booking.save(update_fields=["booking_status", "payment_status", "updated_at"])

            booking.unit.status = "VACANT"
            booking.unit.save(update_fields=["status", "last_status_updated"])
            booking.unit.apartment.recalc_unit_counts()

        message = f"The booking for Unit {booking.unit.unit_number_or_id} at {booking.unit.apartment.name} has been cancelled by {cancelling_user.get_full_name() or cancelling_user.username}."

        notify(
            recipient=other_party,
            notification_type=NotificationType.BOOKING_CANCELLED,
            title="Booking Cancelled",
            message=message,
            related_object_type="Booking",
            related_object_id=booking.id,
        )

        notify_admin_dashboard(
            notification_type=NotificationType.BOOKING_CANCELLED,
            title="Booking Cancelled",
            message=message,
            related_object_type="Booking",
            related_object_id=booking.id,
        )

        return Response(
            {"message": "Booking cancelled successfully."},
            status=status.HTTP_200_OK,
        )


class BookingConfirmView(generics.UpdateAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsLandlordOfBooking]
    queryset = Booking.objects.all()

    def update(self, request, *args, **kwargs):
        booking = self.get_object()

        if booking.booking_status != "PENDING":
            return Response(
                {"error": f"Cannot confirm a booking with status '{booking.booking_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            booking.booking_status = "CONFIRMED"
            booking.save(update_fields=["booking_status", "updated_at"])

            booking.unit.status = "OCCUPIED"
            booking.unit.save(update_fields=["status", "last_status_updated"])
            booking.unit.apartment.recalc_unit_counts()

        message = f"Your booking for Unit {booking.unit.unit_number_or_id} at {booking.unit.apartment.name} has been confirmed by the landlord."

        notify(
            recipient=booking.tenant,
            notification_type=NotificationType.BOOKING_CONFIRMED,
            title="Booking Confirmed",
            message=message,
            related_object_type="Booking",
            related_object_id=booking.id,
        )

        notify_admin_dashboard(
            notification_type=NotificationType.BOOKING_CONFIRMED,
            title="Booking Confirmed",
            message=f"Booking for Unit {booking.unit.unit_number_or_id} at {booking.unit.apartment.name} confirmed by landlord {booking.landlord.get_full_name() or booking.landlord.username}.",
            related_object_type="Booking",
            related_object_id=booking.id,
        )

        return Response(
            {
                "message": "Booking confirmed successfully.",
                "booking_status": booking.booking_status,
            },
            status=status.HTTP_200_OK,
        )