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
    NOT_REQUESTED = "NOT_REQUESTED", "Not Requested"
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class Amenity(models.Model):
    """Lookup table for amenities."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    icon_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


class LeaseAgreement(models.Model):
    """Stores lease agreement documents with version tracking and integrity verification."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name="lease_agreements")
    document = models.FileField(
        upload_to='lease_agreements/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    file_hash = models.CharField(max_length=64, help_text="SHA-256 hash of the document")
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-version", "-created_at"]
        indexes = [
            models.Index(fields=["apartment", "-version"]),
        ]

    def __str__(self):
        return f"Lease Agreement v{self.version} - {self.apartment.name}"

    def compute_hash(self):
        """Compute SHA-256 hash of the document."""
        hash_sha256 = hashlib.sha256()
        for chunk in self.document.chunks():
            hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def save(self, *args, **kwargs):
        if self.document:
            self.file_hash = self.compute_hash()
        super().save(*args, **kwargs)


class Apartment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name="apartments")
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=512, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    overview_description = models.TextField(blank=True)
    exterior_image_url = models.URLField(blank=True)
    lease_agreement = models.ForeignKey(LeaseAgreement, on_delete=models.SET_NULL, null=True, blank=True, related_name="apartments_using", help_text="Latest lease agreement document")
    rules_and_policies = models.TextField(blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="apartments")

    verification_status = models.CharField(
        max_length = 20,
        choices = VerificationStatus.choices,
        default = VerificationStatus.NOT_REQUESTED,
        db_index = True,
    )

    total_units = models.PositiveIntegerField(default=0)
    occupied_units = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["verification_status"]),
            models.Index(fields=["landlord"]),
        ]

    def __str__(self):
        return self.name

    def recalc_unit_counts(self):
        """Utility to recalc total and occupied units."""
        total = self.units.count()
        occupied = self.units.filter(status="OCCUPIED").count()
        self.total_units = total
        self.occupied_units = occupied
        self.save(update_fields=["total_units", "occupied_units", "updated_at"])

    # ✅ Added for sitemap
    def get_absolute_url(self):
        return reverse("properties:apartment-detail", args=[str(self.id)])

    def approve(self):
        if self.verification_status != VerificationStatus.VERIFIED:
            raise ValueError("Apartment must be verified before approval.")
        self.is_approved = True
        self.save(update_fields=["is_approved"])

class Unit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="units")
    unit_number_or_id = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default="RESIDENTIAL")
    type = models.CharField(max_length=50, blank=True)  
    size_sqft = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_month = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=OCCUPANCY_STATUS_CHOICES, default="VACANT")
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

    # ✅ Added for sitemap
    def get_absolute_url(self):
        return reverse("properties:unit-detail", args=[str(self.id)])
