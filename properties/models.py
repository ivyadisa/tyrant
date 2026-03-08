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


class KeyAmenity(models.Model):
    """Lookup table for key amenities near apartments."""
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


class ApartmentAmenityDistance(models.Model):
    """Stores distance from apartment to key amenities."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name="amenity_distances")
    amenity_type = models.CharField(max_length=20, choices=KeyAmenityType.choices)
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, help_text="Distance in kilometers")
    nearest_name = models.CharField(max_length=255, blank=True, help_text="Name of the nearest amenity of this type")

    class Meta:
        unique_together = ("apartment", "amenity_type")
        ordering = ["amenity_type"]

    def __str__(self):
        return f"{self.apartment.name} - {self.amenity_type}: {self.distance_km}km"


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
    exterior_image = models.ImageField(upload_to='apartments/exterior/', blank=True, null=True)
    exterior_image_url = models.URLField(blank=True)
    virtual_tour_url = models.URLField(blank=True, help_text="360 tour URL")
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

    def get_absolute_url(self):
        return reverse("properties:unit-detail", args=[str(self.id)])


class Review(models.Model):
    """Reviews and ratings for apartments."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)], help_text="1-5 stars")
    comment = models.TextField(blank=True)
    is_verified_tenant = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("apartment", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review for {self.apartment.name} by {self.user.username}"


class Tour(models.Model):
    """Tour scheduling for apartments."""
    TOUR_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    TOUR_TYPE_CHOICES = [
        ("IN_PERSON", "In Person"),
        ("VIDEO_CALL", "Video Call"),
        ("SELF_GUIDED", "Self Guided"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="tours")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tours")
    tour_type = models.CharField(max_length=20, choices=TOUR_TYPE_CHOICES, default="IN_PERSON")
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=20, choices=TOUR_STATUS_CHOICES, default="PENDING")
    notes = models.TextField(blank=True)
    contact_phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_date", "-scheduled_time"]

    def __str__(self):
        return f"Tour for {self.apartment.name} on {self.scheduled_date}"
