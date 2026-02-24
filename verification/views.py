from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Verification, VerificationImage
from .serializers import VerificationSerializer, SubmitReportSerializer
from .permissions import IsAdminOrAssignedAgent


class VerificationViewSet(viewsets.ModelViewSet):
    serializer_class = VerificationSerializer
    permission_classes = [IsAdminOrAssignedAgent]

    def get_queryset(self):
        qs = (
            Verification.objects
            .select_related("apartment", "assigned_agent")
            .prefetch_related("images")
        )

        user = self.request.user
        if user.is_staff or getattr(user, "is_admin", False):
            return qs

        return qs.filter(assigned_agent=user)

    # CREATE (admins only)
    def perform_create(self, serializer):
        if not self.request.user.is_admin:
            raise PermissionDenied("Only admins can create verification tasks.")
        serializer.save()

    # UPDATE (admins only)
    def perform_update(self, serializer):
        if not self.request.user.is_admin:
            raise PermissionDenied("Only admins can modify verification records.")
        serializer.save()

    # SUBMIT REPORT (agent only)
    @action(
        detail=True,
        methods=["post"],
        url_path="submit-report",
        permission_classes=[IsAuthenticated],
    )
    def submit_report(self, request, pk=None):
        try:
            verification = (
                Verification.objects
                .select_related("apartment", "assigned_agent")
                .get(pk=pk)
            )
        except Verification.DoesNotExist:
            raise Http404

        if verification.assigned_agent != request.user:
            return Response(
                {"detail": "You are not assigned to this task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent re-submission
        if verification.status == Verification.Status.VERIFIED:
            return Response(
                {"detail": "Report already submitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubmitReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            verification.report = data["report"]
            verification.status = data["status"]
            verification.verification_date = timezone.now()
            verification.save()

            apartment = verification.apartment
            apartment.verification_status = data["status"]
            apartment.save(update_fields=["verification_status"])

            VerificationImage.objects.bulk_create(
                [
                    VerificationImage(
                        verification=verification,
                        image=image,
                    )
                    for image in data.get("images", [])
                ]
            )

        return Response(
            {"detail": "Verification report submitted successfully."},
            status=status.HTTP_200_OK,
        )