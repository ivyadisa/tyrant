import logging

from rest_framework import serializers
from .models import Wallet, WalletTransaction

logger = logging.getLogger(__name__)


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
        except AttributeError:
            logger.warning("WalletTransaction %s: missing wallet or user relation", obj.id)
            return "Unknown User"
        except Exception:
            logger.exception("WalletTransaction %s: unexpected error in get_user_name", obj.id)
            return "Unknown User"

    def get_user_email(self, obj):
        try:
            return obj.wallet.user.email
        except AttributeError:
            logger.warning("WalletTransaction %s: missing wallet or user email", obj.id)
            return None
        except Exception:
            logger.exception("WalletTransaction %s: unexpected error in get_user_email", obj.id)
            return None

    def get_unit_number(self, obj):
        try:
            if obj.booking is not None and obj.booking.unit is not None:
                unit = obj.booking.unit
                return unit.unit_number_or_id or str(unit.id)[:8]
            return None
        except AttributeError:
            logger.warning("WalletTransaction %s: booking/unit relation missing", obj.id)
            return None
        except Exception:
            logger.exception("WalletTransaction %s: unexpected error in get_unit_number", obj.id)
            return None

    def get_apartment_name(self, obj):
        """
        Return the apartment name if this transaction is linked to a booking.
        Returns None when there is no booking — the frontend decides what
        fallback to display.
        """
        try:
            if obj.booking is None:
                return None  # No booking linked (e.g. subscription, deposit, withdrawal)
            booking = obj.booking
            if booking.unit is None:
                logger.warning("WalletTransaction %s: booking %s has no unit", obj.id, booking.id)
                return None
            try:
                apartment = booking.unit.apartment
            except AttributeError:
                logger.warning("WalletTransaction %s: unit.apartment not loaded for booking %s", obj.id, booking.id)
                return None
            return apartment.name if apartment else None
        except AttributeError:
            logger.warning("WalletTransaction %s: attribute error resolving apartment_name", obj.id)
            return None
        except Exception:
            logger.exception("WalletTransaction %s: unexpected error in get_apartment_name", obj.id)
            return None

    def get_booking_confirmation_code(self, obj):
        try:
            if obj.booking is not None:
                return obj.booking.booking_confirmation_code
            return None
        except AttributeError:
            logger.warning("WalletTransaction %s: booking relation missing", obj.id)
            return None
        except Exception:
            logger.exception("WalletTransaction %s: unexpected error in get_booking_confirmation_code", obj.id)
            return None


class WalletSerializer(serializers.ModelSerializer):
    transactions = WalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = "__all__"