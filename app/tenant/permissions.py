from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission


class TenantHeaderRequired(BasePermission):
    message = "X-Tenant-ID header is required."

    def has_permission(self, request, view):
        if request.tenant is None:
            raise PermissionDenied(self.message)
        return True


class IsStaffOrSuperuser(BasePermission):
    message = "Only staff or superuser accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsStaffOrAssetSupervisor(BasePermission):
    """
    Staff/superusers pass unconditionally.
    Regular users:
      - Safe methods (GET): always allowed.
      - Create (POST on list view, no pk): denied.
      - DELETE: denied.
      - PATCH / POST action (sensor-alert): allowed only if supervisor.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        if request.method == "POST" and not view.kwargs.get("pk"):
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return False
        return obj.supervisor == request.user


class IsStaffOrWorkOrderAssignee(BasePermission):
    """
    Staff/superusers pass unconditionally.
    Regular users:
      - Safe methods (GET): always allowed.
      - Create (POST on list view, no pk): denied.
      - DELETE: denied.
      - PATCH / POST action (start, hold, complete, cancel): allowed only if
        assigned_to.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        if request.method == "POST" and not view.kwargs.get("pk"):
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True
        if request.method in SAFE_METHODS:
            return True
        if request.method == "DELETE":
            return False
        return obj.assigned_to == request.user
