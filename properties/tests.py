from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from properties.models import Apartment, KeyAmenity, ApartmentAmenityDistance, KeyAmenityType, Unit

User = get_user_model()


class KeyAmenityDistanceAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.landlord = User.objects.create_user(
            email="landlord@test.com",
            password="password",
            username="landlord_test",
            role=User.ROLE_LANDLORD,
        )

        self.tenant = User.objects.create_user(
            email="tenant@test.com",
            password="password",
            username="tenant_test",
            role=User.ROLE_TENANT,
        )

        self.apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Test Apartment",
            latitude=-1.2921,
            longitude=36.8219,
        )

        self.unit = Unit.objects.create(
            apartment=self.apartment,
            unit_number_or_id="101",
            price_per_month=50000,
        )

    def test_list_amenity_distances(self):
        ApartmentAmenityDistance.objects.create(
            apartment=self.apartment,
            amenity_type=KeyAmenityType.SCHOOL,
            distance_km=0.5,
            nearest_name="Test School"
        )
        ApartmentAmenityDistance.objects.create(
            apartment=self.apartment,
            amenity_type=KeyAmenityType.MARKET,
            distance_km=1.2,
            nearest_name="Test Market"
        )

        self.client.force_authenticate(self.tenant)

        response = self.client.get(f"/api/properties/apartments/{self.apartment.id}/amenity-distances/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_landlord_set_amenity_distances(self):
        self.client.force_authenticate(self.landlord)

        response = self.client.post(
            f"/api/properties/apartments/{self.apartment.id}/set-amenity-distances/",
            [
                {"amenity_type": "SCHOOL", "distance_km": "0.5", "nearest_name": "Primary School"},
                {"amenity_type": "MARKET", "distance_km": "1.0", "nearest_name": "City Market"},
                {"amenity_type": "HOSPITAL", "distance_km": "2.5", "nearest_name": "General Hospital"},
            ],
            format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ApartmentAmenityDistance.objects.filter(apartment=self.apartment).count(), 3)

    def test_tenant_cannot_set_amenity_distances(self):
        self.client.force_authenticate(self.tenant)

        response = self.client.post(
            f"/api/properties/apartments/{self.apartment.id}/set-amenity-distances/",
            [
                {"amenity_type": "SCHOOL", "distance_km": "0.5", "nearest_name": "Primary School"},
            ],
            format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_apartment_serializer_includes_distances(self):
        ApartmentAmenityDistance.objects.create(
            apartment=self.apartment,
            amenity_type=KeyAmenityType.SCHOOL,
            distance_km=0.5,
            nearest_name="Test School"
        )

        self.client.force_authenticate(self.tenant)

        response = self.client.get(f"/api/properties/apartments/{self.apartment.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("amenity_distances", response.data)
        self.assertEqual(len(response.data["amenity_distances"]), 1)

    def test_search_with_distance_filter(self):
        apartment2 = Apartment.objects.create(
            landlord=self.landlord,
            name="Far Apartment",
            latitude=-1.3,
            longitude=36.9,
        )
        Unit.objects.create(
            apartment=apartment2,
            unit_number_or_id="102",
            price_per_month=60000,
        )

        ApartmentAmenityDistance.objects.create(
            apartment=self.apartment,
            amenity_type=KeyAmenityType.SCHOOL,
            distance_km=0.5,
            nearest_name="Close School"
        )
        ApartmentAmenityDistance.objects.create(
            apartment=apartment2,
            amenity_type=KeyAmenityType.SCHOOL,
            distance_km=5.0,
            nearest_name="Far School"
        )

        self.client.force_authenticate(self.landlord)

        response = self.client.get("/api/properties/apartments/search/", {
            "amenity_type": "SCHOOL",
            "max_distance": "3.0"
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Test Apartment")

    def test_nearby_apartments(self):
        apartment2 = Apartment.objects.create(
            landlord=self.landlord,
            name="Far Apartment",
            latitude=-1.5,
            longitude=37.0,
        )
        Unit.objects.create(
            apartment=apartment2,
            unit_number_or_id="103",
            price_per_month=70000,
        )

        self.client.force_authenticate(self.tenant)

        response = self.client.get("/api/properties/apartments/nearby/", {
            "latitude": "-1.2921",
            "longitude": "36.8219",
            "radius": "50"
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)


class KeyAmenityModelTestCase(TestCase):
    def setUp(self):
        self.landlord = User.objects.create_user(
            email="landlord@test.com",
            password="password",
            username="landlord_test",
            role=User.ROLE_LANDLORD,
        )

    def test_key_amenity_unique_together(self):
        KeyAmenity.objects.create(
            amenity_type=KeyAmenityType.SCHOOL,
            name="Test School",
            latitude=-1.2921,
            longitude=36.8219
        )

        with self.assertRaises(Exception):
            KeyAmenity.objects.create(
                amenity_type=KeyAmenityType.SCHOOL,
                name="Test School",
                latitude=-1.3,
                longitude=36.9
            )

    def test_apartment_amenity_distance_unique_together(self):
        apartment = Apartment.objects.create(
            landlord=self.landlord,
            name="Test Apartment"
        )

        ApartmentAmenityDistance.objects.create(
            apartment=apartment,
            amenity_type=KeyAmenityType.SCHOOL,
            distance_km=0.5
        )

        with self.assertRaises(Exception):
            ApartmentAmenityDistance.objects.create(
                apartment=apartment,
                amenity_type=KeyAmenityType.SCHOOL,
                distance_km=1.0
            )


class KeyAmenityAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="password",
            username="admin_test",
            role=User.ROLE_ADMIN,
            is_staff=True,
        )

    def test_create_key_amenity(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post("/api/properties/key-amenities/", {
            "amenity_type": "SCHOOL",
            "name": "Central Primary School",
            "latitude": "-1.2921",
            "longitude": "36.8219"
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(KeyAmenity.objects.count(), 1)

    def test_list_key_amenities(self):
        KeyAmenity.objects.create(
            amenity_type=KeyAmenityType.SCHOOL,
            name="School 1",
            latitude=-1.2921,
            longitude=36.8219
        )
        KeyAmenity.objects.create(
            amenity_type=KeyAmenityType.MARKET,
            name="Market 1",
            latitude=-1.2930,
            longitude=36.8220
        )

        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/properties/key-amenities/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_filter_key_amenities_by_type(self):
        KeyAmenity.objects.create(
            amenity_type=KeyAmenityType.SCHOOL,
            name="School 1",
            latitude=-1.2921,
            longitude=36.8219
        )
        KeyAmenity.objects.create(
            amenity_type=KeyAmenityType.MARKET,
            name="Market 1",
            latitude=-1.2930,
            longitude=36.8220
        )

        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/properties/key-amenities/", {"amenity_type": "SCHOOL"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["amenity_type"], "SCHOOL")
