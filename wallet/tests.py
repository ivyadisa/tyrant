from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from bookings.models import Booking
from properties.models import Apartment, Unit
from .models import Wallet, WalletTransaction
from .tasks import process_mpesa_callback

User = get_user_model()


class MpesaCallbackBookingSyncTests(TestCase):
    def setUp(self):
        self.landlord = User.objects.create_user(
            email="wallet-landlord@test.com",
            password="password",
            username="wallet_landlord",
            role=User.ROLE_LANDLORD,
        )
        self.tenant = User.objects.create_user(
            email="wallet-tenant@test.com",
            password="password",
            username="wallet_tenant",
            role=User.ROLE_TENANT,
        )
        apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Wallet Apartment",
            address="Nairobi",
        )
        unit = Unit.objects.create(
            apartment=apartment,
            unit_number_or_id="A1",
            price_per_month=12000,
            status="VACANT",
        )
        self.booking = Booking.objects.create(
            unit=unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=date.today() + timedelta(days=10),
            booking_amount=1,
        )
        self.wallet = Wallet.objects.create(user=self.tenant, wallet_type="PLATFORM")

    def test_success_callback_marks_booking_paid(self):
        txn = WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type="DEPOSIT",
            amount=1,
            status="PENDING",
            checkout_request_id="checkout-success",
            booking=self.booking,
        )
        process_mpesa_callback({"CheckoutRequestID": txn.checkout_request_id, "ResultCode": 0})
        self.booking.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(txn.status, "COMPLETED")
        self.assertEqual(self.booking.payment_status, "COMPLETED")
        self.assertEqual(self.booking.booking_status, "PAID")

    def test_failed_callback_cancels_booking(self):
        txn = WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type="DEPOSIT",
            amount=1,
            status="PENDING",
            checkout_request_id="checkout-failed",
            booking=self.booking,
        )
        process_mpesa_callback({"CheckoutRequestID": txn.checkout_request_id, "ResultCode": 1032})
        self.booking.refresh_from_db()
        txn.refresh_from_db()
        self.assertEqual(txn.status, "FAILED")
        self.assertEqual(self.booking.payment_status, "FAILED")
        self.assertEqual(self.booking.booking_status, "CANCELLED")
