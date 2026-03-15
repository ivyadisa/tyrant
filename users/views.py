from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
import random
from django.core.mail import send_mail
from properties.models import Lease, Payment, MaintenanceRequest, LeaseDocument
from properties.serializers import LeaseSerializer

from django.utils import timezone

from .models import User
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    LoginSerializer,
    AdminVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    LandlordDashboardSerializer,
    LandlordDocumentUploadSerializer,
)

from .permissions import (
    IsAdmin,
    IsVerifiedLandlord,
    IsVerifiedTenant,
    IsOwnerOrAdmin,
)

from .utils import send_otp_email, verify_user_otp


# =====================================================
# REGISTER NEW USER
# =====================================================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        import traceback
        try:
            user = serializer.save()
            print(f"[DEBUG] User {user.username} created successfully.")

            if User.objects.count() == 1:  # first user
                user.role = User.ROLE_ADMIN
                user.verification_status = User.VERIF_VERIFIED
                user.save()
                print(f"[DEBUG] First user set as admin: {user.username}")

            # generate email OTP
            user.email_otp = f"{random.randint(100000, 999999)}"
            user.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
            user.save()
            print(f"[DEBUG] OTP generated: {user.email_otp}")

            # Send email (might fail silently, so catch exception)
            try:
                send_mail(
                    'Verify your email',
                    f'Your OTP is: {user.email_otp}',
                    'no-reply@example.com',
                    [user.email]
                )
                print(f"[DEBUG] OTP email sent to {user.email}")
            except Exception as email_err:
                print("[ERROR] Failed to send OTP email:", email_err)
                traceback.print_exc()

        except Exception as e:
            print("[ERROR] RegisterView perform_create crashed:", e)
            traceback.print_exc()
            raise


# ----------------------------------------------------
# LIST ALL USERS (ADMIN ONLY)
# =====================================================
class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


# =====================================================
# LOGIN VIEW
# =====================================================
class CustomLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            #  Check email verification
            if not user.email_verified:
                return Response(
                    {"error": "Please verify your email first."},
                    status=403
                )

            #  Check admin verification
            if user.verification_status != User.VERIF_VERIFIED:
                return Response(
                    {"error": "Your account is pending admin verification."},
                    status=403
                )

            #  Check if account is suspended
            if user.status == User.STATUS_SUSPENDED:
                return Response(
                    {"error": "Your account is suspended."},
                    status=403
                )

            #  Generate authentication token
            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "verification_status": user.verification_status,
                "email_verified": user.email_verified
            })

        return Response(serializer.errors, status=400)

# =====================================================
# VIEW PROFILE
# =====================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# =====================================================
# UPDATE PROFILE
# =====================================================
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    serializer = UserSerializer(
        request.user, data=request.data, partial=True
    )
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


# =====================================================
# ADMIN OPERATIONS
# =====================================================
@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_list_users(request):
    role = request.GET.get("role")
    verification_status = request.GET.get("verification_status")

    users = User.objects.all()

    if role:
        users = users.filter(role=role)

    if verification_status:
        users = users.filter(verification_status=verification_status)

    return Response(UserSerializer(users, many=True).data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_list_pending_users(request):
    users = User.objects.filter(
        verification_status=User.VERIF_PENDING
    )
    return Response(UserSerializer(users, many=True).data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_verify_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    serializer = AdminVerificationSerializer(data=request.data)

    if serializer.is_valid():
        user.verification_status = User.VERIF_VERIFIED
        user.verification_notes = serializer.validated_data.get(
            "verification_notes", ""
        )
        user.verified_by_admin = request.user
        user.verification_date = timezone.now()
        user.save()

        return Response({"success": f"{user.role} verified successfully."})

    return Response(serializer.errors, status=400)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_reject_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    serializer = AdminVerificationSerializer(data=request.data)

    if serializer.is_valid():
        user.verification_status = User.VERIF_REJECTED
        user.verification_notes = serializer.validated_data.get(
            "verification_notes", ""
        )
        user.verified_by_admin = request.user
        user.verification_date = timezone.now()
        user.save()

        return Response({"success": f"{user.role} rejected successfully."})

    return Response(serializer.errors, status=400)


# =====================================================
# LANDLORD / TENANT DASHBOARDS
# =====================================================
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedLandlord])
def landlord_dashboard(request):
    serializer = LandlordDashboardSerializer(request.user)
    return Response({
        "message": f"Welcome {request.user.username}",
        "profile": serializer.data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedTenant])
def tenant_dashboard(request):
    tenant = request.user
    # Get all active leases
    active_leases = Lease.objects.filter(tenant=tenant, is_active=True)
    serializer = LeaseSerializer(active_leases, many=True)

    return Response({
        "message": f"Welcome {tenant.username}",
        "current_leases": serializer.data
    })


# =====================================================
# LANDLORD DOCUMENT UPLOAD
# =====================================================
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsVerifiedLandlord])
def upload_landlord_documents(request):
    serializer = LandlordDocumentUploadSerializer(
        request.user,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        serializer.save()
        return Response({"success": "Documents uploaded successfully."})

    return Response(serializer.errors, status=400)


# =====================================================
# ADMIN EXTRA FEATURES
# =====================================================
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_promote_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.role = User.ROLE_ADMIN
        user.save()
        return Response({"success": "User promoted"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_demote_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.role = User.ROLE_TENANT
        user.save()
        return Response({"success": "User demoted"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_suspend_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.status = User.STATUS_SUSPENDED
        user.save()
        return Response({"success": "User suspended"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_unsuspend_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.status = User.STATUS_ACTIVE
        user.save()
        return Response({"success": "User unsuspended"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)


# =====================================================
# ADMIN ANALYTICS
# =====================================================
@api_view(["GET"])
@permission_classes([IsAdmin])
def admin_dashboard_analytics(request):
    return Response({
        "total_tenants": User.objects.filter(role=User.ROLE_TENANT).count(),
        "total_landlords": User.objects.filter(role=User.ROLE_LANDLORD).count(),
        "pending_verifications": User.objects.filter(
            verification_status=User.VERIF_PENDING
        ).count(),
    })


# =====================================================
# PASSWORD RESET
# =====================================================
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)

    if serializer.is_valid():
        try:
            user = User.objects.get(email=serializer.validated_data["email"])
            send_otp_email(user, subject="Password Reset OTP")
            return Response({"success": "OTP sent."})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

    return Response(serializer.errors, status=400)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def confirm_password_reset(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)

    if serializer.is_valid():
        try:
            user = User.objects.get(email=serializer.validated_data["email"])
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        is_valid, message = verify_user_otp(
            user,
            serializer.validated_data["otp"],
        )

        if not is_valid:
            return Response({"error": message}, status=400)

        user.set_password(serializer.validated_data["new_password"])
        user.email_otp = None
        user.otp_expiry = None
        user.save()

        return Response({"success": "Password reset successfully."})

    return Response(serializer.errors, status=400)


# =====================================================
# EMAIL VERIFICATION
# =====================================================
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def verify_email(request):
    email = request.data.get("email")
    otp = request.data.get("otp")

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)

    if user.email_verified:
        return Response({"message": "Email already verified."})

    is_valid, message = verify_user_otp(user, otp)

    if not is_valid:
        return Response({"error": message}, status=400)

    user.email_verified = True
    user.email_otp = None
    user.otp_expiry = None
    user.save()

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        "message": "Email verified successfully.",
        "token": token.key,
    })


# =====================================================
# RESEND OTP
# =====================================================
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def resend_otp(request):
    try:
        user = User.objects.get(email=request.data.get("email"))

        if user.email_verified:
            return Response({"message": "Email already verified."})

        send_otp_email(user, subject="Your New OTP Code")

        return Response({"success": "OTP resent successfully."})

    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)


# =====================================================
# VERIFY STATUS
# =====================================================
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def verify_status(request):
    try:
        user = User.objects.get(email=request.GET.get("email"))
        return Response({"email_verified": user.email_verified})
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)
