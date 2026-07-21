import logging

from rest_framework import serializers
from .models import Booking

logger = logging.getLogger(__name__)


class BookingSerializer(serializers.ModelSerializer):
    unit_number = serializers.SerializerMethodField()
    apartment_name = serializers.SerializerMethodField()
    apartment_address = serializers.SerializerMethodField()
    price_per_month = serializers.SerializerMethodField()
    tenant_name = serializers.SerializerMethodField()
    tenant_email = serializers.SerializerMethodField()
    tenant_phone = serializers.SerializerMethodField()
    landlord_name = serializers.SerializerMethodField()
    landlord_email = serializers.SerializerMethodField()
    landlord_phone = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = "__all__"
        read_only_fields = [
            "id",
            "tenant",
            "landlord",
            "booking_confirmation_code",
            "booking_status",
            "payment_status",
            "created_at",
            "updated_at",
            "lease_agreement",
        ]

    def get_unit_number(self, obj):
        try:
            if obj.unit is not None:
                return obj.unit.unit_number_or_id
            return None
        except AttributeError:
            logger.warning("Booking %s: unit relation missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_unit_number", obj.id)
            return None

    def get_apartment_name(self, obj):
        try:
            if obj.unit is not None and getattr(obj.unit, 'apartment', None) is not None:
                return obj.unit.apartment.name
            return None
        except AttributeError:
            logger.warning("Booking %s: unit.apartment relation missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_apartment_name", obj.id)
            return None

    def get_apartment_address(self, obj):
        try:
            if obj.unit is not None and getattr(obj.unit, 'apartment', None) is not None:
                return obj.unit.apartment.address
            return None
        except AttributeError:
            logger.warning("Booking %s: unit.apartment address missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_apartment_address", obj.id)
            return None

    def get_price_per_month(self, obj):
        try:
            if obj.unit is not None:
                return obj.unit.price_per_month
            return None
        except AttributeError:
            logger.warning("Booking %s: unit.price_per_month missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_price_per_month", obj.id)
            return None

    def get_tenant_name(self, obj):
        try:
            if obj.tenant is None:
                return None
            return obj.tenant.full_name or obj.tenant.username
        except AttributeError:
            logger.warning("Booking %s: tenant relation missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_tenant_name", obj.id)
            return None

    def get_tenant_email(self, obj):
        try:
            return obj.tenant.email if obj.tenant else None
        except AttributeError:
            logger.warning("Booking %s: tenant email missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_tenant_email", obj.id)
            return None

    def get_tenant_phone(self, obj):
        try:
            return obj.tenant.phone_number if obj.tenant else None
        except AttributeError:
            logger.warning("Booking %s: tenant phone missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_tenant_phone", obj.id)
            return None

    def get_landlord_name(self, obj):
        try:
            if obj.landlord is None:
                return None
            return obj.landlord.full_name or obj.landlord.username
        except AttributeError:
            logger.warning("Booking %s: landlord relation missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_landlord_name", obj.id)
            return None

    def get_landlord_email(self, obj):
        try:
            return obj.landlord.email if obj.landlord else None
        except AttributeError:
            logger.warning("Booking %s: landlord email missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_landlord_email", obj.id)
            return None

    def get_landlord_phone(self, obj):
        try:
            return obj.landlord.phone_number if obj.landlord else None
        except AttributeError:
            logger.warning("Booking %s: landlord phone missing", obj.id)
            return None
        except Exception:
            logger.exception("Booking %s: unexpected error in get_landlord_phone", obj.id)
            return None
