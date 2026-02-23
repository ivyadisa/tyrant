from django.test import TestCase
from verification.models import Verification
from properties.models import Apartment
from django.contrib.auth import get_user_model

User = get_user_model()

class VerificationModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email = "agent@test.com",
            password= "pass",
            username =  "agent_test"
        )
        self.apartment = Apartment.objects.create(
            landlord = self.user,
            name = "Test Apartment"
        )
        self.verification = Verification.objects.create(
            apartment = self.apartment,
            assigned_agent= self.user,
            status= Verification.Status.PENDING
        )
    def test_valid_transition(self):
        self.verification.status = Verification.Status.ASSIGNED
        self.verification.save()
        self.assertEqual(self.verification.status, "ASSIGNED")

    def test_invalid_transition(self):
        self.verification.status = Verification.Status.VERIFIED

        with self.assertRaises(ValueError):
            self.verification.save()

    def test_apartment_status_sync(self):
        self.verification.status = Verification.Status.ASSIGNED
        self.verification.save()

        self.verification.status = Verification.Status.IN_PROGRESS
        self.verification.save()

        self.verification.status = Verification.Status.VERIFIED
        self.verification.save()

        self.apartment.refresh_from_db()
        self.assertEqual(
            self.apartment.verification_status,
            "VERIFIED"
        )

