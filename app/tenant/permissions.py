from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


class TenantHeaderRequired(BasePermission):
    message = "X-Tenant-ID header is required."

    def has_permission(self, request, view):
        if request.tenant is None:
            raise PermissionDenied(self.message)
        return True
