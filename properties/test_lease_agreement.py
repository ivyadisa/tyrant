import os
from io import BytesIO
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from .models import Apartment, LeaseAgreement
from bookings.models import Booking
from properties.models import Unit
from datetime import date, timedelta

User = get_user_model()


class LeaseAgreementModelTests(TestCase):
    """Test LeaseAgreement model."""

    def setUp(self):
        self.landlord = User.objects.create_user(
            username="landlord_user",
            email="landlord@test.com",
            password="testpass123",
            role="LANDLORD"
        )
        self.apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Test Apartment",
            address="123 Main St",
        )

    def test_lease_agreement_creation(self):
        """Test creating a lease agreement with proper attributes."""
        pdf_content = b"%PDF-1.4\n%Mock PDF content"
        pdf_file = SimpleUploadedFile(
            "lease.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        lease = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file,
            version=1
        )
        self.assertEqual(lease.version, 1)
        self.assertIsNotNone(lease.file_hash)
        self.assertEqual(len(lease.file_hash), 64)  # SHA-256 hex is 64 chars

    def test_lease_agreement_version_tracking(self):
        """Test that multiple versions of lease agreements are tracked."""
        pdf_content = b"%PDF-1.4\n%Mock PDF content"
        pdf_file1 = SimpleUploadedFile("lease1.pdf", pdf_content, content_type="application/pdf")
        pdf_file2 = SimpleUploadedFile("lease2.pdf", pdf_content + b" updated", content_type="application/pdf")

        lease1 = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file1,
            version=1
        )
        lease2 = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file2,
            version=2
        )

        self.assertEqual(lease1.version, 1)
        self.assertEqual(lease2.version, 2)
        self.assertNotEqual(lease1.file_hash, lease2.file_hash)

    def test_lease_agreement_hash_integrity(self):
        """Test that file hash is computed and stored correctly."""
        pdf_content = b"%PDF-1.4\n%Mock PDF content"
        pdf_file = SimpleUploadedFile("lease.pdf", pdf_content, content_type="application/pdf")
        lease = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file,
            version=1
        )
        lease.refresh_from_db()
        self.assertIsNotNone(lease.file_hash)
        self.assertTrue(len(lease.file_hash) == 64)


class LeaseAgreementAPITests(APITestCase):
    """Test LeaseAgreement API endpoints."""

    def setUp(self):
        self.client = APIClient()
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
        self.admin = User.objects.create_superuser(
            username="admin_user",
            email="admin@test.com",
            password="testpass123"
        )
        self.apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Test Apartment",
            address="123 Main St",
        )

    def create_pdf_file(self, filename="lease.pdf", content=None):
        """Helper to create a mock PDF file."""
        if content is None:
            content = b"%PDF-1.4\n%Mock PDF content"
        return SimpleUploadedFile(filename, content, content_type="application/pdf")

    def test_landlord_can_upload_lease_agreement(self):
        """Test that landlords can upload lease agreements."""
        self.client.force_authenticate(user=self.landlord)
        pdf_file = self.create_pdf_file()
        
        response = self.client.post(
            f'/api/properties/lease-agreements/upload/?apartment_id={self.apartment.id}',
            {'document': pdf_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('file_hash', response.data)
        self.assertEqual(response.data['version'], 1)

    def test_tenant_cannot_upload_lease_agreement(self):
        """Test that tenants cannot upload lease agreements."""
        self.client.force_authenticate(user=self.tenant)
        pdf_file = self.create_pdf_file()
        
        response = self.client.post(
            f'/api/properties/lease-agreements/upload/?apartment_id={self.apartment.id}',
            {'document': pdf_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_cannot_upload(self):
        """Test that unauthenticated users cannot upload."""
        pdf_file = self.create_pdf_file()
        
        response = self.client.post(
            f'/api/properties/lease-agreements/upload/?apartment_id={self.apartment.id}',
            {'document': pdf_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lease_agreement_version_increments_on_new_upload(self):
        """Test that versions increment when new lease agreements are uploaded."""
        self.client.force_authenticate(user=self.landlord)
        
        # Upload first version
        pdf_file1 = self.create_pdf_file()
        response1 = self.client.post(
            f'/api/properties/lease-agreements/upload/?apartment_id={self.apartment.id}',
            {'document': pdf_file1},
            format='multipart'
        )
        self.assertEqual(response1.data['version'], 1)
        
        # Upload second version
        pdf_file2 = self.create_pdf_file()
        response2 = self.client.post(
            f'/api/properties/lease-agreements/upload/?apartment_id={self.apartment.id}',
            {'document': pdf_file2},
            format='multipart'
        )
        self.assertEqual(response2.data['version'], 2)

    def test_file_size_validation(self):
        """Test that files larger than 10MB are rejected."""
        self.client.force_authenticate(user=self.landlord)
        # Create a file larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)
        pdf_file = SimpleUploadedFile("large.pdf", large_content, content_type="application/pdf")
        
        response = self.client.post(
            f'/api/properties/lease-agreements/upload/?apartment_id={self.apartment.id}',
            {'document': pdf_file},
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_can_view_lease_agreement(self):
        """Test that tenants can view the apartment's lease agreement."""
        # Create and upload a lease agreement
        pdf_file = self.create_pdf_file()
        lease = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file,
            version=1
        )
        
        self.client.force_authenticate(user=self.tenant)
        response = self.client.get(f'/api/properties/lease-agreements/{lease.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['version'], 1)
        self.assertIn('file_hash', response.data)

    def test_get_lease_agreements_for_apartment(self):
        """Test filtering lease agreements by apartment."""
        pdf_file = self.create_pdf_file()
        lease = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file,
            version=1
        )
        
        self.client.force_authenticate(user=self.tenant)
        response = self.client.get(f'/api/properties/lease-agreements/?apartment={self.apartment.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results can be paginated or a list depending on configuration
        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.assertEqual(len(results), 1)


class BookingLeaseAgreementIntegrationTests(APITestCase):
    """Test lease agreement integration with booking workflow."""

    def setUp(self):
        self.client = APIClient()
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
        pdf_file = SimpleUploadedFile("lease.pdf", b"%PDF-1.4\n%Mock PDF content", content_type="application/pdf")
        self.lease = LeaseAgreement.objects.create(
            apartment=self.apartment,
            document=pdf_file,
            version=1
        )

    def test_booking_includes_lease_agreement_field(self):
        """Test that booking model includes lease_agreement_acknowledged field."""
        future_date = date.today() + timedelta(days=30)
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
            lease_agreement=self.lease,
            lease_agreement_acknowledged=True
        )
        
        self.assertTrue(booking.lease_agreement_acknowledged)
        self.assertEqual(booking.lease_agreement, self.lease)

    def test_booking_without_lease_acknowledgment(self):
        """Test that booking can be created without lease acknowledgment (default False)."""
        future_date = date.today() + timedelta(days=30)
        booking = Booking.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            landlord=self.landlord,
            move_in_date=future_date,
            booking_amount=1000.00,
        )
        
        self.assertFalse(booking.lease_agreement_acknowledged)
        self.assertIsNone(booking.lease_agreement)
