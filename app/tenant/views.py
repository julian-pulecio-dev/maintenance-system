from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Tenant
from .serializers import TenantSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List all tenants",
        description=(
            "Returns all tenants in the system. Only accessible by "
            "superusers (`is_staff=True`). Regular tenant users cannot "
            "access this endpoint.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Authenticated user is not a superuser."
        ),
    ),
    create=extend_schema(
        summary="Create a tenant",
        description=(
            "Creates a new tenant. Only accessible by superusers.\n\n"
            "**Required fields:**\n"
            "- `name` — Display name for the tenant.\n\n"
            "After creating a tenant, use `POST /api/user/create/` with the "
            "new tenant's ID in the `X-Tenant-ID` header to register the "
            "first user.\n\n"
            "**Errors:**\n"
            "- `400` — `name` not provided or missing required fields.\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Authenticated user is not a superuser."
        ),
    ),
)
class TenantListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = Tenant.objects.all()


@extend_schema_view(
    retrieve=extend_schema(
        summary="Retrieve a tenant",
        description=(
            "Returns the detail of a single tenant. Only accessible by "
            "superusers.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Authenticated user is not a superuser.\n"
            "- `404` — Tenant not found."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update a tenant",
        description=(
            "Updates one or more fields of a tenant. Only accessible by "
            "superusers.\n\n"
            "**Editable fields:** `name`.\n\n"
            "**Errors:**\n"
            "- `400` — Validation error.\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Authenticated user is not a superuser.\n"
            "- `404` — Tenant not found."
        ),
    ),
    destroy=extend_schema(
        summary="Delete a tenant",
        description=(
            "Permanently deletes a tenant and all its associated data. "
            "Only accessible by superusers.\n\n"
            "Deletion is blocked if any users still belong to this tenant. "
            "Delete or reassign all tenant users before attempting to delete "
            "the tenant.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Authenticated user is not a superuser.\n"
            "- `404` — Tenant not found.\n"
            "- `409` — One or more users still belong to this tenant."
        ),
        responses={
            204: OpenApiResponse(description="Tenant deleted."),
            409: OpenApiResponse(description="Users exist in this tenant."),
        },
    ),
)
class TenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TenantSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = Tenant.objects.all()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete tenant with existing users."},
                status=status.HTTP_409_CONFLICT,
            )
