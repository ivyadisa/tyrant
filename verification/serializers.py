from rest_framework import serializers
from .models import Verification, VerificationImage

class VerificationImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationImage
        fields = ["id","image","uploaded_at"]
        read_only_fields = ["id","uploaded_at"]

class VerificationSerializer(serializers.ModelSerializer):
    images = VerificationImageSerializer(many=True, read_only=True)

    class Meta:
        model = Verification
        fields = [
            "id",
            "apartment",
            "assigned_agent",
            "status",
            "report",
            "verification_date",
            "images",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "report",
            "verification_date",
            "created_at",
            "updated_at",
        ]

class SubmitReportSerializer(serializers.Serializer):
    report = serializers.CharField()
    status = serializers.ChoiceField(
        choices = [Verification.Status.VERIFIED, Verification.Status.REJECTED]
    )
    images = serializers.ListField(
        child = serializers.ImageField(),
        required = False,
        allow_empty = True,
    )