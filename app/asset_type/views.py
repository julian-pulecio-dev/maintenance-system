from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import TenantHeaderRequired
from .models import AssetType
from .serializers import AssetTypeSerializer


@extend_schema_view(
    list=extend_schema(
        summary="List asset types",
        description=(
            "Returns all asset types for the current tenant. Asset types are "
            "used to classify assets (e.g., Pump, Motor, Compressor) and "
            "group related assets for reporting and filtering.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
    ),
    create=extend_schema(
        summary="Create an asset type",
        description=(
            "Creates a new asset type under the current tenant. Names must "
            "be unique within the tenant but can be reused across different "
            "tenants.\n\n"
            "**Required fields:**\n"
            "- `name` — Display name for the asset type. Must be unique "
            "within this tenant.\n\n"
            "**Optional fields:**\n"
            "- `description` — Extended description of assets that belong "
            "to this type.\n\n"
            "**Errors:**\n"
            "- `400` — `name` not provided, or an asset type with the same "
            "name already exists in this tenant.\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
    ),
)
class AssetTypeListCreateView(generics.ListCreateAPIView):
    serializer_class = AssetTypeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def get_queryset(self):
        return AssetType.objects.filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        try:
            serializer.save(tenant=self.request.tenant)
        except IntegrityError:
            raise serializers.ValidationError(
                {"name": "An asset type with this name already exists."}
            )


@extend_schema_view(
    retrieve=extend_schema(
        summary="Retrieve an asset type",
        description=(
            "Returns the detail of a single asset type.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Asset type not found or belongs to a different tenant."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update an asset type",
        description=(
            "Updates the `name` and/or `description` of an asset type. "
            "All fields are optional — only sent fields are modified.\n\n"
            "**Editable fields:** `name`, `description`.\n\n"
            "**Constraints:**\n"
            "- `name` must remain unique within this tenant.\n\n"
            "**Errors:**\n"
            "- `400` — An asset type with the new name already exists in "
            "this tenant.\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Asset type not found or belongs to a different tenant."
        ),
    ),
    destroy=extend_schema(
        summary="Delete an asset type",
        description=(
            "Permanently deletes an asset type. This is a hard delete — "
            "the record is removed from the database.\n\n"
            "Deletion is blocked if any assets are still referencing this "
            "type. Reassign those assets to a different type or delete them "
            "before attempting to delete the type.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Asset type not found or belongs to a different tenant.\n"
            "- `409` — One or more assets are still referencing this type."
        ),
        responses={
            204: OpenApiResponse(description="Asset type deleted."),
            409: OpenApiResponse(description="Assets exist for this type."),
        },
    ),
)
class AssetTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssetTypeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return AssetType.objects.filter(tenant=self.request.tenant)

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"name": "An asset type with this name already exists."}
            )

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete asset type with existing assets."},
                status=status.HTTP_409_CONFLICT,
            )
