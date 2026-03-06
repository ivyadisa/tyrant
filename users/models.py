import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model with roles, verification, and OTP support.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ================= BASIC INFO =================
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    national_id = models.CharField(max_length=20, null=True, blank=True)

    bio = models.TextField(null=True, blank=True)

    profile_picture = models.ImageField(upload_to="uploads/profile_pics/", null=True, blank=True)
    national_id_image = models.ImageField(upload_to="uploads/national_ids/", null=True, blank=True)

    # ================= ROLES =================
    ROLE_ADMIN = "ADMIN"
    ROLE_LANDLORD = "LANDLORD"
    ROLE_TENANT = "TENANT"
    ROLE_AGENT = "AGENT"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_LANDLORD, "Landlord"),
        (ROLE_TENANT, "Tenant"),
        (ROLE_AGENT, "Agent"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # ================= STATUS =================
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    # ================= ADMIN VERIFICATION =================
    VERIF_PENDING = "PENDING"
    VERIF_VERIFIED = "VERIFIED"
    VERIF_REJECTED = "REJECTED"

    VERIFICATION_CHOICES = [
        (VERIF_PENDING, "Pending"),
        (VERIF_VERIFIED, "Verified"),
        (VERIF_REJECTED, "Rejected"),
    ]

    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_CHOICES,
        default=VERIF_PENDING
    )

    verification_notes = models.TextField(blank=True, null=True)
    verification_date = models.DateTimeField(blank=True, null=True)

    verified_by_admin = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_users"
    )

    # ================= EMAIL VERIFICATION =================
    email_verified = models.BooleanField(default=False)

    email_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)

    # ================= TIMESTAMPS =================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.role})"
