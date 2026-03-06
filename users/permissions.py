from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """
    Allow access only to users with role == ADMIN.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, "role", None) == "ADMIN")


class IsVerifiedLandlord(BasePermission):
    """
    Allow access only to verified landlords.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and
            user.is_authenticated and
            getattr(user, "role", None) == "LANDLORD" and
            getattr(user, "verification_status", None) == "VERIFIED"
        )


class IsVerifiedTenant(BasePermission):
    """
    Allow access only to verified tenants.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and
            user.is_authenticated and
            getattr(user, "role", None) == "TENANT" and
            getattr(user, "verification_status", None) == "VERIFIED"
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Allow users to update only their own profile, but admin can update anyone.
    Works as object permission.
    """
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "role", None) == "ADMIN":
            return True
        # obj is expected to be a User instance
        return getattr(obj, "id", None) == getattr(request.user, "id", None)
