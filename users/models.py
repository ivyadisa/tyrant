import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom user model extending AbstractUser.
    Uses role-based fields and verification workflow.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    national_id = models.CharField(max_length=20, unique=False, null=True, blank=True)
    national_id_image_url = models.URLField(max_length=500, null=True, blank=True)
    profile_picture_url = models.URLField(max_length=500, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)

    ROLE_ADMIN = "ADMIN"
    ROLE_LANDLORD = "LANDLORD"
    ROLE_TENANT = "TENANT"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_LANDLORD, "Landlord"),
        (ROLE_TENANT, "Tenant"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_TENANT)

    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_SUSPENDED, "Suspended"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    VERIF_PENDING = "PENDING"
    VERIF_VERIFIED = "VERIFIED"
    VERIF_REJECTED = "REJECTED"
    VERIFICATION_CHOICES = [
        (VERIF_PENDING, "Pending"),
        (VERIF_VERIFIED, "Verified"),
        (VERIF_REJECTED, "Rejected"),
    ]
    verification_status = models.CharField(max_length=10, choices=VERIFICATION_CHOICES, default=VERIF_PENDING)
    verification_notes = models.TextField(null=True, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)

    verified_by_admin = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_users'
    )

    # OTP fields for email verification / password reset
    email_otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # convenience helpers
    @property
    def is_verified(self):
        return self.verification_status == self.VERIF_VERIFIED

    @property
    def is_landlord(self):
        return self.role == self.ROLE_LANDLORD

    @property
    def is_tenant(self):
        return self.role == self.ROLE_TENANT

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    def __str__(self):
        return f"{self.full_name or self.username} ({self.role})"
