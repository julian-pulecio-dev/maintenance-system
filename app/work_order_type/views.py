from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import TenantHeaderRequired
from .models import WorkOrderType
from .serializers import WorkOrderTypeSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List work order types",
        description=(
            "Returns all work order types for the current tenant. Work order "
            "types are used to classify work orders (e.g., Preventive, "
            "Corrective, Inspection).\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
    ),
    create=extend_schema(
        summary="Create a work order type",
        description=(
            "Creates a new work order type under the current tenant. Names "
            "must be unique within the tenant but can be reused across "
            "different tenants.\n\n"
            "**Required fields:**\n"
            "- `name` — Display name for the type. Must be unique within "
            "this tenant.\n\n"
            "**Optional fields:**\n"
            "- `description` — Extended description of when this type applies.\n\n"
            "**Errors:**\n"
            "- `400` — `name` not provided, or a work order type with the "
            "same name already exists in this tenant.\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
    ),
)
class WorkOrderTypeListCreateView(generics.ListCreateAPIView):
    serializer_class = WorkOrderTypeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def get_queryset(self):
        return WorkOrderType.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        try:
            serializer.save(tenant=self.request.tenant)
        except IntegrityError:
            raise serializers.ValidationError(
                {"name": "A work order type with this name already exists."}
            )


@extend_schema_view(
    retrieve=extend_schema(
        summary="Retrieve a work order type",
        description=(
            "Returns the detail of a single work order type.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Work order type not found or belongs to a different "
            "tenant."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update a work order type",
        description=(
            "Updates the `name` and/or `description` of a work order type. "
            "All fields are optional — only sent fields are modified.\n\n"
            "**Editable fields:** `name`, `description`.\n\n"
            "**Constraints:**\n"
            "- `name` must remain unique within this tenant.\n\n"
            "**Errors:**\n"
            "- `400` — A work order type with the new name already exists in "
            "this tenant.\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Work order type not found or belongs to a different "
            "tenant."
        ),
    ),
    destroy=extend_schema(
        summary="Delete a work order type",
        description=(
            "Permanently deletes a work order type. This is a hard delete — "
            "the record is removed from the database.\n\n"
            "Deletion is blocked if any work orders reference this type, to "
            "prevent orphaned records. Reassign or close those work orders "
            "before attempting deletion.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Work order type not found or belongs to a different "
            "tenant.\n"
            "- `409` — One or more work orders are still referencing this "
            "type."
        ),
        responses={
            204: OpenApiResponse(description="Work order type deleted."),
            409: OpenApiResponse(
                description="Work orders exist for this type."
            ),
        },
    ),
)
class WorkOrderTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkOrderTypeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return WorkOrderType.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"name": "A work order type with this name already exists."}
            )

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "detail": "Cannot delete work order type with existing work orders."
                },
                status=status.HTTP_409_CONFLICT,
            )
