from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100) 
    phone_number = models.CharField(max_length=15)
    national_id = models.CharField(max_length=20, unique=False, null=True, blank=True)
    national_id_image_url = models.URLField(max_length=500, null=True, blank=True)  
    profile_picture_url = models.URLField(max_length=500, null=True, blank=True)  
    bio = models.TextField(null=True, blank=True)  

    ROLE_CHOICES = [
        ("ADMIN", "Admin"),
        ("LANDLORD", "Landlord"),
        ("TENANT", "Tenant"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("SUSPENDED", "Suspended"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ACTIVE")

    VERIFICATION_CHOICES = [
        ("PENDING", "Pending"),
        ("VERIFIED", "Verified"),
        ("REJECTED", "Rejected"),
    ]
    verification_status = models.CharField(max_length=10, choices=VERIFICATION_CHOICES, default="PENDING")

    verification_notes = models.TextField(null=True, blank=True)  
    verification_date = models.DateTimeField(null=True, blank=True)  
    verified_by_admin = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_landlords',
    )  

    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  

    def __str__(self):
        return f"{self.full_name} ({self.role})"
