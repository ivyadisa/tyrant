import uuid
from django.db import models
from django.conf import settings
from bookings.models import Booking  # Import Booking model

User = settings.AUTH_USER_MODEL

class Wallet(models.Model):
    WALLET_TYPE_CHOICES = [
        ("LANDLORD", "Landlord"),
        ("PLATFORM", "Platform"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallets")
    wallet_type = models.CharField(
        max_length=20,
        choices=WALLET_TYPE_CHOICES,
        default="PLATFORM"
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=5, default="KES")

    bank_account_name = models.CharField(max_length=255, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    swift_code = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.full_name}'s {self.wallet_type} Wallet"

    def deposit(self, amount):
        self.balance += amount
        self.save()

    def withdraw(self, amount):
        if self.balance < amount:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        self.save()


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("DEPOSIT", "Deposit"),
        ("WITHDRAWAL", "Withdrawal"),
        ("COMMISSION_DEDUCTION", "Commission Deduction"),
        ("REFUND", "Refund"),
        ("SUBSCRIPTION", "Subscription"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    reference_id = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    mpesa_receipt_number = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True)

    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class PendingPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    unit = models.ForeignKey('properties.Unit', on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    checkout_request_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    merchant_request_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class Subscription(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    apartment = models.ForeignKey(
        "properties.Apartment", 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name="subscriptions"
    )
    transaction = models.OneToOneField(
        WalletTransaction, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="subscription"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.landlord.full_name} - {self.apartment.name} ({self.status})"

    def is_active(self):
        from django.utils import timezone
        return self.status == "ACTIVE" and (
            self.expires_at is None or self.expires_at > timezone.now()
        )