from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15)
    
    ROLE_CHOICES = [
        ("ADMIN","Admin"),
        ("LANDLORD","Landlord"),
        ("TENANT","Tenant")
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    STATUS_CHOICES = [
        ("ACTIVE","Active"),
        ("INACTIVE","Inactive"),
        ("SUSPENDED","Suspended")
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="ACTIVE")
    
    verification_status = models.CharField(
        max_length=10,
        choices=[("PENDING","Pending"),("VERIFIED","Verified"),("REJECTED","Rejected")],
        default="PENDING"
    )

    def __str__(self):
        return f"{self.username} ({self.role})"
