from django.db import models
from django.conf import settings
from django.utils import timezone

class Verification(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    apartment = models.ForeignKey(
        "properties.Apartment",
        on_delete=models.CASCADE,
        related_name="verifications",
        db_index=True,
    )

    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_verifications",
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default = Status.PENDING,
        db_index=True,
    )

    report = models.TextField(blank=True, null=True)

    verification_date = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assigned_agent"]),
            models.Index(fields=["apartment"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["apartment"],
                condition=models.Q(
                    status__in=[
                        "PENDING",
                        "ASSIGNED",
                        "IN_PROGRESS",
                    ]
                ),
                name="unique_active_verification_per_apartment",
            )
        ]

    def __str__(self):
        return f"Verification #{self.id} - {self.apartment}"

    #form submission business logic
    def submit_report(self, report_text):
        self.report = report_text
        self.verification_date = timezone.now()

        if self.status == self.Status.VERIFIED:
            self.apartment.verification_status = "VERIFIED"
        elif self.status == self.Status.REJECTED:
            self.apartment.verification_status = "REJECTED"

        self.apartment.save(update_fields = ["verification_status"])
        self.save()

    def can_transition(self, new_status):
        allowed_transitions = {
            self.Status.PENDING: [self.Status.ASSIGNED],
            self.Status.ASSIGNED : [self.Status.IN_PROGRESS],
            self.Status.IN_PROGRESS : [
                self.Status.VERIFIED,
                self.Status.REJECTED,
            ],
            self.Status.VERIFIED : [],
            self.Status.REJECTED : [],

        }
        return new_status in allowed_transitions.get(self.status, [])

    def update_apartment_status(self):
        apartment = self.apartment

        if(self.status == self.Status.VERIFIED):
            apartment.verification_status = "VERIFIED"
        elif(self.status == self.Status.REJECTED):
            apartment.verification_status = "REJECTED"
        else:
            apartment.verification_status = "PENDING"

        apartment.save(update_fields = ["verification_status"])

    def save(self, *args, **kwargs):
        if self.pk:
            old = Verification.objects.get(pk=self.pk)
            if old.status != self.status:

                self.update_apartment_status()

                if not old.can_transition(self.status):
                    raise ValueError(
                        f"Invalid transition from {old.status} to {self.status}"
                    )
        super().save(*args, **kwargs)

#Verification images
class VerificationImage(models.Model):
    verification = models.ForeignKey(
        Verification,
        on_delete = models.CASCADE,
        related_name = "images",
    )
    image = models.ImageField(upload_to = "verification_images/")
    uploaded_at = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        return f"Image for verification #{self.verification.id}"

