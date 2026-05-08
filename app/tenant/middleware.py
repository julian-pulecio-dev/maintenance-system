from django.core.exceptions import ValidationError
from django.http import JsonResponse
from .models import Tenant


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant_id = request.headers.get("X-Tenant-ID")

        if tenant_id:
            try:
                request.tenant = Tenant.objects.get(pk=tenant_id)
            except (Tenant.DoesNotExist, ValueError, ValidationError):
                return JsonResponse(
                    {"detail": "Invalid or unknown tenant."}, status=400
                )
        else:
            request.tenant = None

        return self.get_response(request)
