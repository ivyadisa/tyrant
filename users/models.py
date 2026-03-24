import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

# ================= CUSTOM USER MANAGER =================
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.ROLE_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", User.STATUS_ACTIVE)
        return self.create_user(email, password, **extra_fields)


# ================= CUSTOM USER MODEL =================
class User(AbstractBaseUser, PermissionsMixin):
    # ================= ID =================
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ================= BASIC INFO =================
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, blank=True)
    full_name = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    national_id = models.CharField(max_length=20, null=True, blank=True)
    physical_address = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to="uploads/profile_pics/", null=True, blank=True)
    national_id_image = models.ImageField(upload_to="uploads/national_ids/", null=True, blank=True)

    # ================= LANDLORD DOCUMENTS =================
    proof_of_ownership = models.ImageField(upload_to="uploads/proof_of_ownership/", null=True, blank=True)
    kra_pin = models.ImageField(upload_to="uploads/kra_pins/", null=True, blank=True)

    # ================= BANK DETAILS =================
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_number = models.CharField(max_length=30, blank=True, null=True)
    bank_account_name = models.CharField(max_length=100, blank=True, null=True)
    bank_branch_code = models.CharField(max_length=20, blank=True, null=True)

    # ================= TERMS =================
    terms_accepted = models.BooleanField(default=False)

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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True, default=ROLE_TENANT)

    # ================= STATUS =================
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)

    # ================= ADMIN VERIFICATION =================
    VERIF_PENDING = "PENDING"
    VERIF_VERIFIED = "VERIFIED"
    VERIF_REJECTED = "REJECTED"
    VERIFICATION_CHOICES = [
        (VERIF_PENDING, "Pending"),
        (VERIF_VERIFIED, "Verified"),
        (VERIF_REJECTED, "Rejected"),
    ]
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default=VERIF_PENDING)
    verification_notes = models.TextField(blank=True, null=True)
    verification_date = models.DateTimeField(blank=True, null=True)
    verified_by_admin = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_users")

    # ================= EMAIL VERIFICATION =================
    email_verified = models.BooleanField(default=False)
    email_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)

    # ================= PERMISSIONS =================
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # ================= TIMESTAMPS =================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ================= MANAGER & USERNAME FIELD =================
    objects = UserManager()
    USERNAME_FIELD = "email"  # this makes email the login field
    REQUIRED_FIELDS = []

    # ================= HELPERS =================
    @property
    def is_verified(self):
        return self.verification_status == self.VERIF_VERIFIED

    @property
    def is_suspended(self):
        return self.status == self.STATUS_SUSPENDED

    def __str__(self):
        return f"{self.email} ({self.role} - {self.verification_status})"