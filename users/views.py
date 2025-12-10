from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from .models import User
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    LoginSerializer,
    AdminVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .permissions import IsAdmin, IsVerifiedLandlord, IsVerifiedTenant, IsOwnerOrAdmin
from rest_framework.views import APIView
from django.utils import timezone
from django.core.mail import send_mail
import random

# ----------------------------------------------------
# REGISTER NEW USER
# ----------------------------------------------------
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    # AUTO-ASSIGN FIRST USER AS ADMIN
    def perform_create(self, serializer):
        user = serializer.save()
        if User.objects.count() == 1:  # first user
            user.role = User.ROLE_ADMIN
            user.verification_status = User.VERIF_VERIFIED
            user.save()

        # generate email OTP
        user.email_otp = f"{random.randint(100000, 999999)}"
        user.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
        user.save()
        send_mail(
            'Verify your email',
            f'Your OTP is: {user.email_otp}',
            'no-reply@example.com',
            [user.email]
        )

# ----------------------------------------------------
# LIST ALL USERS (ADMIN ONLY)
# ----------------------------------------------------
class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

# ----------------------------------------------------
# LOGIN VIEW
# ----------------------------------------------------
class CustomLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            if user.status == User.STATUS_SUSPENDED:
                return Response({"error": "Your account is suspended."}, status=403)

            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                'token': token.key,
                'user_id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'status': user.status,
                'verification_status': user.verification_status,
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ----------------------------------------------------
# VIEW / UPDATE PROFILE
# ----------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# =====================================================================
# ADMIN OPERATIONS
# =====================================================================
@api_view(['GET'])
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

@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_list_pending_users(request):
    pending_users = User.objects.filter(verification_status=User.VERIF_PENDING)
    serializer = UserSerializer(pending_users, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_verify_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    serializer = AdminVerificationSerializer(data=request.data)
    if serializer.is_valid():
        user.verification_status = User.VERIF_VERIFIED
        user.verification_notes = serializer.validated_data.get("verification_notes", "")
        user.verified_by_admin = request.user
        user.verification_date = timezone.now()
        user.save()
        return Response({"success": f"{user.role} verified successfully."})
    return Response(serializer.errors, status=400)

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_reject_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    serializer = AdminVerificationSerializer(data=request.data)
    if serializer.is_valid():
        user.verification_status = User.VERIF_REJECTED
        user.verification_notes = serializer.validated_data.get("verification_notes", "")
        user.verified_by_admin = request.user
        user.verification_date = timezone.now()
        user.save()
        return Response({"success": f"{user.role} has been rejected."})
    return Response(serializer.errors, status=400)

# =====================================================================
# LANDLORD / TENANT ROUTES
# =====================================================================
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsVerifiedLandlord])
def landlord_dashboard(request):
    user = request.user
    data = UserSerializer(user).data  # includes all personal info, docs, bank details
    return Response({
        "message": f"Welcome to your landlord dashboard, {user.full_name or user.username}",
        "profile": data
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsVerifiedTenant])
def tenant_dashboard(request):
    user = request.user
    return Response({"message": f"Welcome to your tenant dashboard, {user.full_name or user.username}"})

# =====================================================================
# EXTRA ADMIN FEATURES
# =====================================================================
@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_promote_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.role = User.ROLE_ADMIN
        user.save()
        return Response({"success": "User promoted to admin"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_demote_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.role = User.ROLE_TENANT
        user.save()
        return Response({"success": "Admin demoted to normal user"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_suspend_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.status = User.STATUS_SUSPENDED
        user.save()
        return Response({"success": "User account suspended"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_unsuspend_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.status = User.STATUS_ACTIVE
        user.save()
        return Response({"success": "User account unsuspended"})
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

# =====================================================================
# ADMIN DASHBOARD ANALYTICS
# =====================================================================
@api_view(['GET'])
@permission_classes([IsAdmin])
def admin_dashboard_analytics(request):
    tenants = User.objects.filter(role=User.ROLE_TENANT).count()
    landlords = User.objects.filter(role=User.ROLE_LANDLORD).count()
    pending = User.objects.filter(verification_status=User.VERIF_PENDING).count()
    return Response({
        "total_tenants": tenants,
        "total_landlords": landlords,
        "pending_verifications": pending
    })

# =====================================================================
# PASSWORD RESET VIA EMAIL OTP
# =====================================================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            user.email_otp = f"{random.randint(100000, 999999)}"
            user.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
            user.save()
            send_mail(
                'Password Reset OTP',
                f'Your OTP is: {user.email_otp}',
                'no-reply@example.com',
                [user.email]
            )
            return Response({"success": "OTP sent to your email."})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
    return Response(serializer.errors, status=400)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def confirm_password_reset(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = User.objects.get(email=serializer.validated_data['email'])
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)
        if user.email_otp != serializer.validated_data['otp'] or timezone.now() > user.otp_expiry:
            return Response({"error": "Invalid or expired OTP"}, status=400)
        user.set_password(serializer.validated_data['new_password'])
        user.email_otp = None
        user.otp_expiry = None
        user.save()
        return Response({"success": "Password reset successfully."})
    return Response(serializer.errors, status=400)
