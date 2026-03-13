from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from django.core.mail import send_mail
import random

from django.utils import timezone
from datetime import timedelta

from .models import User, NewsletterSubscription, ContactInquiry
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    LoginSerializer,
    AdminVerificationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    VerifyEmailSerializer,
    ResendOtpSerializer,
    VerifyStatusSerializer,
    LandlordDashboardSerializer,
    LandlordDocumentUploadSerializer,
    NewsletterSubscriptionSerializer,
    ContactInquirySerializer,
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
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data["user"]

            if not user.email_verified:
                return Response(
                    {"error": "Please verify your email before logging in."},
                    status=403,
                )

            if user.status == User.STATUS_SUSPENDED:
                return Response(
                    {"error": "Your account is suspended."},
                    status=403,
                )

            token, _ = Token.objects.get_or_create(user=user)

            return Response({
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "status": user.status,
                "verification_status": user.verification_status,
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
    from properties.models import Apartment, Unit
    from wallet.models import Wallet
    from bookings.models import Booking
    
    user = request.user
    apartments = Apartment.objects.filter(landlord=user)
    total_units = Unit.objects.filter(apartment__landlord=user).count()
    occupied_units = Unit.objects.filter(apartment__landlord=user, status="OCCUPIED").count()
    
    pending_bookings = Booking.objects.filter(
        apartment__landlord=user,
        booking_status="PENDING"
    ).count()
    
    wallet, _ = Wallet.objects.get_or_create(user=user)
    
    serializer = LandlordDashboardSerializer(user)
    return Response({
        "message": f"Welcome {user.username}",
        "profile": serializer.data,
        "stats": {
            "total_apartments": apartments.count(),
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": total_units - occupied_units,
            "occupancy_rate": round((occupied_units / total_units * 100) if total_units > 0 else 0, 1),
            "pending_bookings": pending_bookings,
            "wallet_balance": str(wallet.balance),
        }
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsVerifiedTenant])
def tenant_dashboard(request):
    from bookings.models import Booking
    from wallet.models import Wallet
    
    user = request.user
    
    active_bookings = Booking.objects.filter(
        tenant=user,
        booking_status__in=["CONFIRMED", "PAID"]
    ).count()
    
    pending_bookings = Booking.objects.filter(
        tenant=user,
        booking_status="PENDING"
    ).count()
    
    past_bookings = Booking.objects.filter(
        tenant=user,
        booking_status__in=["COMPLETED", "CANCELLED"]
    ).count()
    
    wallet, _ = Wallet.objects.get_or_create(user=user)
    
    return Response({
        "message": f"Welcome {user.username}",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "role": user.role,
            "verification_status": user.verification_status,
        },
        "stats": {
            "active_bookings": active_bookings,
            "pending_bookings": pending_bookings,
            "past_bookings": past_bookings,
            "wallet_balance": str(wallet.balance),
        }
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
@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={200: {"description": "OTP sent successfully"}}
)
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


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses={200: {"description": "Password reset successfully"}}
)
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
@extend_schema(
    request=VerifyEmailSerializer,
    responses={200: {"description": "Email verified successfully"}}
)
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
    user.email_otp_used = True
    user.save()

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        "message": "Email verified successfully.",
        "token": token.key,
    })


# =====================================================
# RESEND OTP
# =====================================================
@extend_schema(
    request=ResendOtpSerializer,
    responses={200: {"description": "OTP resent successfully"}}
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def resend_otp(request):
    try:
        user = User.objects.get(email=request.data.get("email"))

        if user.email_verified:
            return Response({"message": "Email already verified."})

        now = timezone.now()
        window_start = user.otp_request_window
        if not window_start or now > window_start + timedelta(hours=1):
            user.otp_request_count = 1
            user.otp_request_window = now
        else:
            if user.otp_request_count >= 3:
                return Response(
                    {"error": "Too many OTP requests. Please try again later."},
                    status=429
                )
            user.otp_request_count += 1

        user.save()
        send_otp_email(user, subject="Your New OTP Code")

        return Response({"success": "OTP resent successfully."})

    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)


# =====================================================
# VERIFY STATUS
# =====================================================
@extend_schema(
    parameters=[OpenApiParameter(name='email', description='User email', type=str, required=True)],
    responses={200: {"description": "Email verification status"}}
)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def verify_status(request):
    try:
        user = User.objects.get(email=request.GET.get("email"))
        return Response({"email_verified": user.email_verified})
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)


# =====================================================
# NEWSLETTER SUBSCRIPTION
# =====================================================
class NewsletterSubscribeView(generics.CreateAPIView):
    queryset = NewsletterSubscription.objects.all()
    serializer_class = NewsletterSubscriptionSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required"}, status=400)
        
        subscription, created = NewsletterSubscription.objects.get_or_create(
            email=email,
            defaults={"is_active": True}
        )
        
        if not created and not subscription.is_active:
            subscription.is_active = True
            subscription.unsubscribed_at = None
            subscription.save()
            return Response({"message": "Successfully re-subscribed to newsletter"})
        
        return Response({"message": "Successfully subscribed to newsletter"}, status=201)


class NewsletterUnsubscribeView(generics.UpdateAPIView):
    queryset = NewsletterSubscription.objects.all()
    serializer_class = NewsletterSubscriptionSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "email"

    def update(self, request, *args, **kwargs):
        try:
            subscription = NewsletterSubscription.objects.get(email=kwargs["email"])
            subscription.is_active = False
            subscription.save()
            return Response({"message": "Successfully unsubscribed from newsletter"})
        except NewsletterSubscription.DoesNotExist:
            return Response({"error": "Email not found"}, status=404)


# =====================================================
# CONTACT INQUIRY
# =====================================================
class ContactInquiryView(generics.CreateAPIView):
    queryset = ContactInquiry.objects.all()
    serializer_class = ContactInquirySerializer
    permission_classes = [permissions.AllowAny]


class ContactInquiryListView(generics.ListAPIView):
    queryset = ContactInquiry.objects.all()
    serializer_class = ContactInquirySerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return ContactInquiry.objects.filter(is_resolved=False).order_by("-created_at")
