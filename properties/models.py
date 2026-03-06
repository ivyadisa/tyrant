import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.core.validators import FileExtensionValidator

User = settings.AUTH_USER_MODEL


OCCUPANCY_STATUS_CHOICES = [
    ("VACANT", "Vacant"),
    ("OCCUPIED", "Occupied"),
    ("RESERVED", "Reserved"),
    ("MAINTENANCE", "Maintenance"),
]


class VerificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


# --------------------------------------------------
# Amenity Model
# --------------------------------------------------

class Amenity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    icon_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


# --------------------------------------------------
# Key Amenity Types
# --------------------------------------------------

class KeyAmenityType(models.TextChoices):
    SCHOOL = "SCHOOL", "School"
    MARKET = "MARKET", "Market"
    HOSPITAL = "HOSPITAL", "Hospital"
    ROAD = "ROAD", "Road"
    BUS_STOP = "BUS_STOP", "Bus Stop"
    PHARMACY = "PHARMACY", "Pharmacy"
    BANK = "BANK", "Bank"
    RESTAURANT = "RESTAURANT", "Restaurant"
    PARK = "PARK", "Park"
    GYM = "GYM", "Gym"
    UNIVERSITY = "UNIVERSITY", "University"
    SHOPPING_MALL = "SHOPPING_MALL", "Shopping Mall"


# --------------------------------------------------
# Key Amenity
# --------------------------------------------------

class KeyAmenity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amenity_type = models.CharField(max_length=20, choices=KeyAmenityType.choices)
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        unique_together = ("amenity_type", "name")
        verbose_name_plural = "Key Amenities"

    def __str__(self):
        return f"{self.name} ({self.amenity_type})"


# --------------------------------------------------
# Apartment Amenity Distance
# --------------------------------------------------

class ApartmentAmenityDistance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    apartment = models.ForeignKey(
        "Apartment",
        on_delete=models.CASCADE,
        related_name="amenity_distances"
    )

    amenity_type = models.CharField(
        max_length=20,
        choices=KeyAmenityType.choices
    )

    distance_km = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    nearest_name = models.CharField(
        max_length=255,
        blank=True
    )

    class Meta:
        unique_together = ("apartment", "amenity_type")
        ordering = ["amenity_type"]

    def __str__(self):
        return f"{self.apartment.name} - {self.amenity_type}: {self.distance_km}km"


# --------------------------------------------------
# Lease Agreement
# --------------------------------------------------

class LeaseAgreement(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    apartment = models.ForeignKey(
        "Apartment",
        on_delete=models.CASCADE,
        related_name="lease_agreements"
    )

    document = models.FileField(
        upload_to="lease_agreements/%Y/%m/%d/",
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])]
    )

    file_hash = models.CharField(max_length=64)

    version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version", "-created_at"]

    def __str__(self):
        return f"Lease Agreement v{self.version} - {self.apartment.name}"

    def compute_hash(self):
        hash_sha256 = hashlib.sha256()
        for chunk in self.document.chunks():
            hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def save(self, *args, **kwargs):

        if self.document:
            self.file_hash = self.compute_hash()

        super().save(*args, **kwargs)


# --------------------------------------------------
# Apartment Model
# --------------------------------------------------

class Apartment(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    landlord = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="apartments"
    )

    name = models.CharField(max_length=255)

    address = models.CharField(max_length=512, blank=True)

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    overview_description = models.TextField(blank=True)

    exterior_image_url = models.URLField(blank=True)

    lease_agreement = models.ForeignKey(
        LeaseAgreement,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="apartments_using"
    )

    rules_and_policies = models.TextField(blank=True)

    amenities = models.ManyToManyField(
        Amenity,
        blank=True,
        related_name="apartments"
    )

    # ✅ Verification workflow
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )

    is_approved = models.BooleanField(default=False)

    total_units = models.PositiveIntegerField(default=0)
    occupied_units = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["verification_status"]),
            models.Index(fields=["landlord"]),
        ]

    def __str__(self):
        return self.name

    def recalc_unit_counts(self):
        total = self.units.count()
        occupied = self.units.filter(status="OCCUPIED").count()

        self.total_units = total
        self.occupied_units = occupied

        self.save(update_fields=["total_units", "occupied_units"])

    def approve(self):

        if self.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("Apartment must be verified before approval.")

        self.is_approved = True
        self.save(update_fields=["is_approved"])

    def get_absolute_url(self):
        return reverse("properties:apartment-detail", args=[str(self.id)])


# --------------------------------------------------
# Unit Model
# --------------------------------------------------

class Unit(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.CASCADE,
        related_name="units"
    )

    unit_number_or_id = models.CharField(max_length=100)

    category = models.CharField(max_length=50, default="RESIDENTIAL")

    type = models.CharField(max_length=50, blank=True)

    size_sqft = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    price_per_month = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=OCCUPANCY_STATUS_CHOICES,
        default="VACANT"
    )

    interior_images = models.JSONField(default=list, blank=True)

    exterior_images = models.JSONField(default=list, blank=True)

    description = models.TextField(blank=True)

    last_status_updated = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("apartment", "unit_number_or_id")
        ordering = ["apartment", "unit_number_or_id"]

    def __str__(self):
        return f"{self.apartment.name} - {self.unit_number_or_id} ({self.status})"

    def get_absolute_url(self):
        return reverse("properties:unit-detail", args=[str(self.id)])