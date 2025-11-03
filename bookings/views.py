from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Booking
from .serializers import BookingSerializer


class BookingCreateView(generics.CreateAPIView):
    """
    Create a new booking for a unit.
    Automatically assigns the logged-in user as the tenant,
    and the landlord from the related apartment.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        unit = serializer.validated_data["unit"]
        tenant = self.request.user
        landlord = unit.apartment.landlord  # assumes Unit → Apartment → Landlord relationship

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
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    queryset = Booking.objects.all()
    lookup_field = "pk"


class BookingCancelView(generics.UpdateAPIView):
    """
    Cancel a booking — updates its status to CANCELLED and marks payment as REFUNDED.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    queryset = Booking.objects.all()

    def update(self, request, *args, **kwargs):
        booking = self.get_object()
        if booking.booking_status in ["CANCELLED", "COMPLETED"]:
            return Response(
                {"error": "Booking already cancelled or completed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking.booking_status = "CANCELLED"
        booking.payment_status = "REFUNDED"
        booking.save()

        return Response(
            {"message": "Booking cancelled successfully."},
            status=status.HTTP_200_OK
        )
