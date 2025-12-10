from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'email', 'phone_number', 'national_id',
            'national_id_image_url', 'profile_picture_url', 'bio', 'role', 'status',
            'verification_status', 'verification_notes', 'verification_date',
            'verified_by_admin', 'created_at', 'updated_at',
            # new fields for landlord dashboard
            'physical_address', 'proof_of_ownership_url', 'kra_pin_url',
            'bank_name', 'bank_account_number', 'bank_account_name', 'bank_branch_code',
            'terms_accepted'
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2', 'full_name',
            'phone_number', 'role', 'national_id', 'national_id_image_url'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        role = validated_data.get('role')

        if role == 'LANDLORD':
            if not validated_data.get('national_id') or not validated_data.get('national_id_image_url'):
                raise serializers.ValidationError(
                    {"error": "Landlords must provide both National ID and ID image."}
                )

        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            full_name=validated_data.get('full_name', ''),
            phone_number=validated_data['phone_number'],
            national_id=validated_data.get('national_id'),
            national_id_image_url=validated_data.get('national_id_image_url'),
            role=role,
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password")

        user = authenticate(username=user_obj.username, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password")

        if not user.is_active:
            raise serializers.ValidationError("This account is inactive")

        attrs['user'] = user
        return attrs


class AdminVerificationSerializer(serializers.Serializer):
    verification_notes = serializers.CharField(required=False, allow_blank=True)


# -------------------------
# Password Reset / OTP
# -------------------------
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
