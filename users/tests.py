from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class UserPublicProfileTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.request_user = User.objects.create_user(
            username="tenant_test",
            email="tenant@test.com",
            password="password",
            role=User.ROLE_TENANT,
        )
        self.landlord = User.objects.create_user(
            username="landlord_test",
            email="landlord@test.com",
            password="password",
            role=User.ROLE_LANDLORD,
            full_name="Landlord Name",
            phone_number="0712345678",
        )

    def test_authenticated_user_can_get_public_profile(self):
        self.client.force_authenticate(self.request_user)

        response = self.client.get(f"/api/users/{self.landlord.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.landlord.id))
        self.assertEqual(response.data["full_name"], "Landlord Name")

    def test_unauthenticated_user_cannot_get_public_profile(self):
        response = self.client.get(f"/api/users/{self.landlord.id}")
        self.assertEqual(response.status_code, 401)
