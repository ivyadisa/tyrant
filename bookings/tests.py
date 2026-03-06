from django.test import TestCase
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from properties.models import Apartment, Unit
from .models import Booking

User = get_user_model()


class BookingSignalTests(TestCase):
    """Test signal handlers for automatic unit status updates."""
    
    def setUp(self):
        """Set up test data."""
        self.landlord = User.objects.create_user(
            username="landlord_user",
            email="landlord@test.com",
            password="testpass123",
            role="LANDLORD"
        )
        self.tenant = User.objects.create_user(
            username="tenant_user",
            email="tenant@test.com",
            password="testpass123",
            role="TENANT"
        )
        
        self.apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Test Apartment",
            address="123 Main St",
        )
        
        self.unit = Unit.objects.create(
            apartment=self.apartment,
            unit_number_or_id="101",
            price_per_month=1000.00,
            status="VACANT"
        )
    
    def test_booking_creation_sets_unit_to_reserved(self):
        """Test that creating a booking sets unit status to RESERVED."""
        future_date = date.today() + timedelta(days=30)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
        )
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "RESERVED")
    
    def test_payment_confirmation_sets_unit_to_occupied_if_past_move_in(self):
        """Test that confirming payment sets unit to OCCUPIED if move_in_date has passed."""
        past_date = date.today() - timedelta(days=5)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=past_date,
            booking_amount=1000.00,
        )
        
        # Update payment status to COMPLETED
        booking.payment_status = "COMPLETED"
        booking.save()
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "OCCUPIED")
    
    def test_payment_confirmation_keeps_unit_reserved_if_future_move_in(self):
        """Test that confirming payment keeps unit RESERVED if move_in_date is in future."""
        future_date = date.today() + timedelta(days=30)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
        )
        
        # Update payment status to COMPLETED
        booking.payment_status = "COMPLETED"
        booking.save()
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "RESERVED")
    
    def test_booking_cancellation_sets_unit_to_vacant(self):
        """Test that cancelling booking sets unit status to VACANT."""
        future_date = date.today() + timedelta(days=30)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
        )
        
        # Verify unit is RESERVED
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "RESERVED")
        
        # Delete the booking (simulating cancellation)
        booking.delete()
        
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "VACANT")
    
    def test_apartment_counts_updated_on_booking_creation(self):
        """Test that apartment unit counts are recalculated on booking creation."""
        future_date = date.today() + timedelta(days=30)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
        )
        
        self.apartment.refresh_from_db()
        # Total units should be 1, occupied should be 0 (since status is RESERVED)
        self.assertEqual(self.apartment.total_units, 1)
        self.assertEqual(self.apartment.occupied_units, 0)
    
    def test_apartment_counts_updated_on_booking_payment(self):
        """Test that apartment unit counts are updated when booking payment is confirmed."""
        past_date = date.today() - timedelta(days=5)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=past_date,
            booking_amount=1000.00,
        )
        
        # Confirm payment
        booking.payment_status = "COMPLETED"
        booking.save()
        
        self.apartment.refresh_from_db()
        # Total units should be 1, occupied should be 1
        self.assertEqual(self.apartment.total_units, 1)
        self.assertEqual(self.apartment.occupied_units, 1)
    
    def test_delete_booking_resets_unit_to_vacant(self):
        """Test that deleting a booking resets unit to VACANT."""
        future_date = date.today() + timedelta(days=30)
        
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
        )
        
        # Verify unit is RESERVED
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "RESERVED")
        
        # Delete the booking
        booking.delete()
        
        # Unit should be VACANT since no other active bookings exist
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, "VACANT")
