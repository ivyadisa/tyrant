# bookings/permissions.py
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """
    Allows access only to users with role='ADMIN' or Django's is_staff/is_superuser flag.
    """
    message = "Only admin users can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                getattr(request.user, "role", None) == "ADMIN"
                or request.user.is_staff
                or request.user.is_superuser
            )
        )


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