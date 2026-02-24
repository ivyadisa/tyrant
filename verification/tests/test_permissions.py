from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.test import APIClient
from verification.models import Verification
from django.contrib.auth import get_user_model
from properties.models import Apartment, VerificationStatus

User = get_user_model()

class VerificationPermissionTest(APITestCase):
    def setUp(self):
        self.client = APIClient()

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
            name="Test Apartment",
            landlord=self.landlord,
            verification_status=VerificationStatus.NOT_REQUESTED,
        )

        self.apartment1 = Apartment.objects.create(
            landlord=self.landlord,
            name="Apartment One",
            verification_status=VerificationStatus.NOT_REQUESTED,
        )

        self.apartment2 = Apartment.objects.create(
            landlord=self.landlord,
            name="Apartment Two",
            verification_status=VerificationStatus.NOT_REQUESTED,
        )

        Verification.objects.create(
            apartment=self.apartment1,
            assigned_agent=self.agent,
            status=Verification.Status.ASSIGNED,
        )

        Verification.objects.create(
            apartment=self.apartment2,
            assigned_agent=self.agent,
            status=Verification.Status.IN_PROGRESS,
        )

    def test_agent_sees_only_assigned_tasks(self):
        self.client.force_authenticate(self.agent)
        url = reverse('verification-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 2. Check total count (should NOT include other agent's tasks)
        # Assuming we created 2 for self.agent and 1 for someone else:
        self.assertEqual(len(response.data), 2)

        for item in response.data:
            self.assertEqual(str(item["assigned_agent"]), str(self.agent.id))

    def test_agent_cannot_create_tasks(self):
        self.client.force_authenticate(self.agent)
        url = reverse('verification-list')
        response = self.client.post(
            "/api/verification/",
            {
                "apartment": self.apartment.id,
                "assigned_agent": self.agent.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
