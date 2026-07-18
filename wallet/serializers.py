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

    class Meta:
        model = WalletTransaction
        fields = "__all__"

    def get_user_name(self, obj):
        user = obj.wallet.user
        return user.full_name or user.username

    def get_user_email(self, obj):
        return obj.wallet.user.email

    def get_unit_number(self, obj):
        if obj.booking and obj.booking.unit:
            return obj.booking.unit.unit_number_or_id
        return None

    def get_apartment_name(self, obj):
        # Use apartment_id first — checking obj.apartment truthiness
        # directly raises RelatedObjectDoesNotExist when the FK is null
        if obj.booking and obj.booking.unit and obj.booking.unit.apartment_id:
            return obj.booking.unit.apartment.name
        return None

    def get_booking_confirmation_code(self, obj):
        if obj.booking:
            return obj.booking.booking_confirmation_code
        return None


class WalletSerializer(serializers.ModelSerializer):
    transactions = WalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = "__all__"