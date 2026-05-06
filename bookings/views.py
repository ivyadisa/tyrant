# bookings/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from .models import Booking
from .serializers import BookingSerializer
from .permissions import IsAdminRole, IsLandlordOfBooking, IsTenantOrLandlordOfBooking


class BookingCreateView(generics.CreateAPIView):
    """
    Create a new booking for a unit.
    Automatically assigns the logged-in user as the tenant,
    and the landlord from the related apartment.
    """
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

        serializer.save(
            tenant=tenant,
            landlord=landlord,
            booking_status="PENDING",
            payment_status="UNPAID",
        )


class TenantBookingListView(generics.ListAPIView):
    """
    List all bookings for the authenticated tenant.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(tenant=self.request.user).order_by("-created_at")


class LandlordBookingListView(generics.ListAPIView):
    """
    List all bookings for the authenticated landlord.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(landlord=self.request.user).order_by("-created_at")


class BookingDetailView(generics.RetrieveAPIView):
    """
    Retrieve details of a specific booking by its UUID.
    Accessible by the tenant, landlord, or an admin.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    queryset = Booking.objects.all()
    lookup_field = "pk"

    def get_object(self):
        booking = super().get_object()
        user = self.request.user

        # Admins and staff can view any booking
        is_admin = getattr(user, "role", None) == "ADMIN" or user.is_staff or user.is_superuser
        if not is_admin and user not in (booking.tenant, booking.landlord):
            self.permission_denied(
                self.request,
                message="You do not have permission to view this booking.",
            )
        return booking


class BookingCancelView(generics.UpdateAPIView):
    """
    Cancel a booking — updates status to CANCELLED and payment to REFUNDED.
    Only the tenant or landlord on the booking can cancel it.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsTenantOrLandlordOfBooking]
    queryset = Booking.objects.all()

    def update(self, request, *args, **kwargs):
        booking = self.get_object()  # triggers has_object_permission

        if booking.booking_status in ["CANCELLED", "COMPLETED"]:
            return Response(
                {"error": "Booking already cancelled or completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.booking_status = "CANCELLED"
        booking.payment_status = "REFUNDED"
        booking.save()

        return Response(
            {"message": "Booking cancelled successfully."},
            status=status.HTTP_200_OK,
        )


class BookingConfirmView(generics.UpdateAPIView):
    """
    Confirm a booking — landlord moves it from PENDING → CONFIRMED.
    Only the landlord assigned to the booking can confirm it.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsLandlordOfBooking]
    queryset = Booking.objects.all()

    def update(self, request, *args, **kwargs):
        booking = self.get_object()  # triggers has_object_permission

        if booking.booking_status != "PENDING":
            return Response(
                {"error": f"Cannot confirm a booking with status '{booking.booking_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.booking_status = "CONFIRMED"
        booking.save()

        return Response(
            {
                "message": "Booking confirmed successfully.",
                "booking_status": booking.booking_status,
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminBookingListView(generics.ListAPIView):
    """
    List ALL bookings across the platform.
    Restricted to users with role='ADMIN' or is_staff/is_superuser.
    Supports filtering via query params:
      ?booking_status=PENDING
      ?payment_status=UNPAID
      ?tenant=<uuid>
      ?landlord=<uuid>
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["booking_status", "payment_status", "tenant", "landlord"]
    ordering_fields = ["created_at", "move_in_date", "booking_amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Booking.objects.select_related("tenant", "landlord", "unit")
            .all()
            .order_by("-created_at")
        )