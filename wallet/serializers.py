from rest_framework import serializers
from .models import Wallet, WalletTransaction


class PaymentRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    unit_id = serializers.CharField(max_length=50)


class WalletTransactionSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    unit_number = serializers.SerializerMethodField()
    apartment_name = serializers.SerializerMethodField()
    booking_confirmation_code = serializers.SerializerMethodField()
    mpesa_receipt_number = serializers.CharField(read_only=True)

    class Meta:
        model = WalletTransaction
        fields = "__all__"

    def get_user_name(self, obj):
        try:
            return obj.wallet.user.full_name or obj.wallet.user.username
        except:
            return "Unknown User"

    def get_user_email(self, obj):
        try:
            return obj.wallet.user.email
        except:
            return None

    def get_unit_number(self, obj):
        try:
            if obj.booking and obj.booking.unit:
                return obj.booking.unit.unit_number_or_id or str(obj.booking.unit)
            return None
        except:
            return None

    def get_apartment_name(self, obj):
        """Safe access to prevent RelatedObjectDoesNotExist"""
        try:
            if obj.booking and obj.booking.unit and getattr(obj.booking.unit, 'apartment_id', None):
                return obj.booking.unit.apartment.name
            return "N/A"
        except Exception:
            return "N/A"

    def get_booking_confirmation_code(self, obj):
        try:
            if obj.booking:
                return obj.booking.booking_confirmation_code
            return None
        except:
            return None


class WalletSerializer(serializers.ModelSerializer):
    transactions = WalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = "__all__"