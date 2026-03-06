from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsAdminOrAssignedAgent(BasePermission):
    def has_object_permission(self, request, view, obj):

        #admin has full access
        if request.user.is_staff or getattr(request.user, "role", "") == "ADMIN":
            return True

        #Field agent can only access assigned tasks
        return obj.assigned_agent == request.user