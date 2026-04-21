from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import User, NewsletterSubscription, ContactInquiry


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'email', 'phone_number', 'national_id',
            'national_id_image', 'profile_picture', 'bio', 'role', 'status',
            'verification_status', 'verification_notes', 'verification_date',
            'verified_by_admin', 'created_at', 'updated_at', 'email_verified',
            'email_otp', 'otp_expiry'
        ]


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email", "phone_number", "role"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2', 'full_name',
            'phone_number', 'role', 'national_id', 'national_id_image'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        
        role = attrs.get('role')
        
        allowed_roles = [User.ROLE_TENANT, User.ROLE_LANDLORD]
        if role not in allowed_roles:
            raise serializers.ValidationError(
                {"role": "Invalid role. Only TENANT and LANDLORD roles can self-register."}
            )
        
        if role == User.ROLE_LANDLORD:
            if not attrs.get('national_id'):
                raise serializers.ValidationError(
                    {"national_id": "Landlords must provide their National ID"}
                )
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            full_name=validated_data.get('full_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            national_id=validated_data.get('national_id'),
            national_id_image=validated_data.get('national_id_image'),
            role=validated_data.get('role', User.ROLE_TENANT),
            verification_status=User.VERIF_PENDING,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    login = serializers.CharField(required=False, allow_blank=False)
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, allow_blank=False)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        login = attrs.get('login')
        email = attrs.get('email')
        username = attrs.get('username')
        password = attrs.get('password')

        identifier = login or email or username
        if not identifier:
            raise serializers.ValidationError(
                "Provide login, email, or username with your password."
            )

        user_obj = None

        if email:
            user_obj = User.objects.filter(email=email).first()

        if not user_obj and username:
            user_obj = User.objects.filter(username=username).first()

        # If only login is provided, decide whether it is email or username.
        if not user_obj and login:
            if "@" in login:
                user_obj = User.objects.filter(email=login).first()
            else:
                user_obj = User.objects.filter(username=login).first()

        if not user_obj:
            raise serializers.ValidationError("Invalid credentials")

        user = authenticate(username=user_obj.username, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive")

        attrs['user'] = user
        return attrs


class AdminVerificationSerializer(serializers.Serializer):
    verification_notes = serializers.CharField(required=False, allow_blank=True)


class AdminLandlordVerificationSerializer(serializers.ModelSerializer):
    national_id_image_url = serializers.SerializerMethodField()
    proof_of_ownership_url = serializers.SerializerMethodField()
    kra_pin_url = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    verified_by_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "email",
            "phone_number",
            "role",
            "status",
            "verification_status",
            "verification_notes",
            "verification_date",
            "email_verified",
            "national_id",
            "national_id_image_url",
            "proof_of_ownership_url",
            "kra_pin_url",
            "profile_picture_url",
            "verified_by_admin",
            "created_at",
            "updated_at",
        ]

    def _build_file_url(self, file_field):
        if not file_field:
            return None
        request = self.context.get("request")
        file_url = file_field.url
        return request.build_absolute_uri(file_url) if request else file_url

    def get_national_id_image_url(self, obj):
        return self._build_file_url(obj.national_id_image)

    def get_proof_of_ownership_url(self, obj):
        # Field may not exist in current schema on some deployments.
        file_field = getattr(obj, "proof_of_ownership", None)
        return self._build_file_url(file_field)

    def get_kra_pin_url(self, obj):
        # Field may not exist in current schema on some deployments.
        file_field = getattr(obj, "kra_pin", None)
        return self._build_file_url(file_field)

    def get_profile_picture_url(self, obj):
        return self._build_file_url(obj.profile_picture)

    def get_verified_by_admin(self, obj):
        if obj.verified_by_admin:
            return obj.verified_by_admin.full_name or obj.verified_by_admin.email
        return None


# -------------------------
# Password Reset / OTP
# -------------------------
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)


class ResendOtpSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class VerifyStatusSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

# --- New serializer for landlord dashboard ---
class LandlordDashboardSerializer(UserSerializer):
    verified_by_admin = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields

    def get_verified_by_admin(self, obj):
        if obj.verified_by_admin:
            return obj.verified_by_admin.full_name or obj.verified_by_admin.email
        return None


# --- Landlord document upload ---
class LandlordDocumentUploadSerializer(serializers.ModelSerializer):
    national_id_image = serializers.ImageField(required=False)
    proof_of_ownership = serializers.ImageField(required=False)
    kra_pin = serializers.ImageField(required=False)

    class Meta:
        model = User
        fields = [
            'national_id_image',
            'proof_of_ownership',
            'kra_pin'
        ]


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscription
        fields = ['email', 'is_active', 'subscribed_at']
        read_only_fields = ['is_active', 'subscribed_at']


class ContactInquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInquiry
        fields = ['id', 'name', 'email', 'phone', 'subject', 'message', 'is_resolved', 'created_at']
        read_only_fields = ['is_resolved', 'created_at']