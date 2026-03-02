from django.test import TestCase
from rest_framework.test import APIClient
from django.db import IntegrityError

from django.contrib.auth import get_user_model
from verification.models import Verification
from properties.models import Apartment, VerificationStatus
from django.db import transaction

User = get_user_model()

class VerificationAPITestCase(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="password",
            username="admin_test",
            role=User.ROLE_ADMIN,
            is_staff=True,
        )

        self.agent = User.objects.create_user(
            email="agent@test.com",
            password="password",
            username="agent_test",
            role=User.ROLE_AGENT,
        )

        self.landlord = User.objects.create_user(
            email="landlord@test.com",
            password="password",
            username="landlord_test",
            role=User.ROLE_LANDLORD,
        )

        self.apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Test Apartment",
            verification_status=VerificationStatus.NOT_REQUESTED,
        )

        self.verification = Verification.objects.create(
            apartment=self.apartment,
            assigned_agent=self.agent,
            status=Verification.Status.IN_PROGRESS,
        )

    def test_agent_submit_report(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/verification/{self.verification.id}/submit-report/",
            {
                "report": "Everything checked",
                "status": Verification.Status.VERIFIED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

    def test_admin_creates_verification(self):
        self.client.force_authenticate(self.admin)

        new_apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Admin Create Apartment",
            verification_status=VerificationStatus.NOT_REQUESTED,
        )

        response = self.client.post("/api/verification/", {
            "apartment": new_apartment.id,
            "assigned_agent": self.agent.id,
        })
        self.assertEqual(response.status_code, 201)

    def test_unassigned_agent_cannot_submit_report(self):
        other_agent = User.objects.create_user(
            email="unassigned@test.com",
            password="password",
            username = "unassigned_agent",
            role=User.ROLE_AGENT,
        )

        self.client.force_authenticate(other_agent)

        response = self.client.post(
            f"/api/verification/{self.verification.id}/submit-report/",
            {
                "report": "Fake report",
                "status": Verification.Status.VERIFIED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_cannot_create_duplicate_active_verification(self):
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Verification.objects.create(
                    apartment=self.apartment,
                    assigned_agent=self.agent,
                    status=Verification.Status.IN_PROGRESS,
                )

    def test_cannot_approve_unverified_apartment(self):
        with self.assertRaises(ValueError):
            self.apartment.approve()