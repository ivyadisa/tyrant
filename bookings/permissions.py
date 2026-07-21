# bookings/permissions.py
import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class IsAdminRole(BasePermission):
    """
    Allows access only to users with role='ADMIN' or Django's is_staff/is_superuser flag.
    """
    message = "Only admin users can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning("IsAdminRole denied: user not authenticated")
            return False

        user_role = getattr(request.user, "role", None)
        is_admin = (
            (user_role and user_role.upper() == "ADMIN")
            or request.user.is_staff
            or request.user.is_superuser
        )

        if not is_admin:
            logger.warning(
                "IsAdminRole denied for user %s (role=%s, is_staff=%s, is_superuser=%s)",
                request.user.id,
                user_role,
                request.user.is_staff,
                request.user.is_superuser,
            )

        return is_admin


class IsLandlordOfBooking(BasePermission):
    """
    Object-level permission — allows access only to the landlord on the booking.
    """
    message = "Only the landlord assigned to this booking can perform this action."

    def has_object_permission(self, request, view, obj):
        return request.user == obj.landlord


class IsTenantOrLandlordOfBooking(BasePermission):
    """
    Object-level permission — allows access to the tenant or landlord on the booking.
    """
    message = "Only the tenant or landlord on this booking can perform this action."

    def has_object_permission(self, request, view, obj):
        return request.user in (obj.tenant, obj.landlord)
