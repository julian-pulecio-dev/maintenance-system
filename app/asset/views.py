from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import (
    IsStaffOrAssetSupervisor,
    IsStaffOrSuperuser,
    TenantHeaderRequired,
)
from .models import Asset
from .serializers import AssetSerializer
from .services import (
    AssetAlreadyDeletedException,
    AssetNotDeletedException,
    AssetService,
)


class SensorAlertSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=False, default="", allow_blank=True
    )
    severity = serializers.ChoiceField(
        choices=["warning", "critical"], default="warning"
    )


User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        summary="List assets",
        description=(
            "Returns all non-deleted assets for the current tenant.\n\n"
            "**Query parameters:**\n"
            "- `supervisor` — Filter by supervisor user UUID.\n\n"
            "Each asset includes computed fields:\n"
            "- `next_maintenance_date` — `last_maintenance_date` + "
            "`recommended_maintenance_interval_days`.\n"
            "- `is_maintenance_overdue` — `true` if today is past "
            "`next_maintenance_date`.\n"
            "- `is_deleted` — Always `false` in this list (deleted assets "
            "are excluded).\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
        parameters=[
            OpenApiParameter(
                name="supervisor",
                description="Filter by supervisor user UUID.",
                required=False,
                type=str,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create an asset",
        description=(
            "Creates a new asset under the current tenant.\n\n"
            "**Required fields:**\n"
            "- `name` — Human-readable asset name.\n"
            "- `serial_number` — Manufacturer serial number. Must be unique "
            "among active (non-deleted) assets in the tenant.\n"
            "- `asset_type` — UUID of an asset type belonging to this "
            "tenant.\n"
            "- `supervisor` — UUID of a user belonging to this tenant.\n"
            "- `location` — Physical location of the asset.\n"
            "- `installation_date` — Date the asset was installed (cannot "
            "be in the future).\n"
            "- `recommended_maintenance_interval_days` — Positive integer; "
            "used to calculate `next_maintenance_date`.\n\n"
            "**Optional fields:**\n"
            "- `description` — Extended notes about the asset.\n"
            "- `status` — One of `active` (default), `inactive`, "
            "`maintenance`, `failed`.\n"
            "- `last_maintenance_date` — Defaults to `installation_date` if "
            "not provided. Must not be before `installation_date`.\n"
            "- `metadata` — Free-form JSON object for additional attributes.\n\n"
            "**Errors:**\n"
            "- `400` — Validation error (e.g., `serial_number` already in "
            "use within this tenant, `asset_type` belongs to another tenant, "
            "`installation_date` in the future).\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
    ),
)
class AssetListCreateView(generics.ListCreateAPIView):
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsAuthenticated,
        IsStaffOrAssetSupervisor,
        TenantHeaderRequired,
    ]

    def get_queryset(self):
        qs = Asset.objects.for_tenant(self.request.tenant).not_deleted()
        supervisor_param = self.request.query_params.get("supervisor")
        if supervisor_param:
            qs = qs.filter(supervisor_id=supervisor_param)
        return qs

    def perform_create(self, serializer):
        try:
            asset = AssetService.create_asset(
                tenant=self.request.tenant,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
        serializer.instance = asset


@extend_schema_view(
    retrieve=extend_schema(
        summary="Retrieve an asset",
        description=(
            "Returns the full detail of a single asset, including computed "
            "fields (`next_maintenance_date`, `is_maintenance_overdue`, "
            "`is_operational`, `is_deleted`).\n\n"
            "Soft-deleted assets are still returned by this endpoint — "
            "check `is_deleted` in the response if needed.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Asset not found or belongs to a different tenant."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update an asset",
        description=(
            "Updates one or more fields of an asset. All fields are "
            "optional — only sent fields are modified.\n\n"
            "**Editable fields:** `name`, `serial_number`, `asset_type`, "
            "`supervisor`, `location`, `status`, `description`, "
            "`installation_date`, `last_maintenance_date`, "
            "`recommended_maintenance_interval_days`, `metadata`.\n\n"
            "**Constraints:**\n"
            "- `serial_number` must remain unique among active assets in "
            "the tenant.\n"
            "- `last_maintenance_date` cannot be before `installation_date`.\n"
            "- `asset_type` and `supervisor` must belong to this tenant.\n\n"
            "**Errors:**\n"
            "- `400` — Validation error (duplicate serial number, date "
            "constraint violation, cross-tenant relation).\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Asset not found or belongs to a different tenant."
        ),
    ),
    destroy=extend_schema(
        summary="Soft-delete an asset",
        description=(
            "Marks the asset as deleted by setting `deleted_at` to the "
            "current timestamp. The record is preserved in the database and "
            "can be restored via `POST /{id}/restore/`.\n\n"
            "Soft-deleted assets are excluded from the list endpoint and "
            "their `serial_number` is freed for reuse by other active "
            "assets in the tenant.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Asset not found or belongs to a different tenant.\n"
            "- `409` — Asset is already deleted."
        ),
        responses={
            204: OpenApiResponse(description="Asset soft-deleted."),
            409: OpenApiResponse(description="Asset already deleted."),
        },
    ),
)
class AssetDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsAuthenticated,
        IsStaffOrAssetSupervisor,
        TenantHeaderRequired,
    ]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Asset.objects.for_tenant(self.request.tenant)

    def perform_update(self, serializer):
        try:
            asset = AssetService.update_asset(
                asset=serializer.instance,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
        serializer.instance = asset

    def destroy(self, request, *args, **kwargs):
        asset = self.get_object()
        try:
            AssetService.delete_asset(asset=asset)
        except AssetAlreadyDeletedException:
            return Response(
                {"detail": "Asset is already deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    request=inline_serializer("AssetRestoreRequest", fields={}),
    responses={200: AssetSerializer},
    summary="Restore a soft-deleted asset",
    description=(
        "Removes the `deleted_at` timestamp, making the asset visible again "
        "in list and detail endpoints. The asset's status is not changed.\n\n"
        "If another active asset in the same tenant has taken the same "
        "`serial_number` since the deletion, the restore will fail with a "
        "validation error — the serial number conflict must be resolved "
        "first.\n\n"
        "**Errors:**\n"
        "- `400` — Asset is not currently deleted, or `serial_number` "
        "conflict with another active asset.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Asset not found or belongs to a different tenant.\n"
        "- `409` — Integrity constraint prevented the restore."
    ),
)
class AssetRestoreView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsAuthenticated,
        IsStaffOrSuperuser,
        TenantHeaderRequired,
    ]

    def post(self, request, pk):
        try:
            asset = Asset.objects.for_tenant(request.tenant).get(pk=pk)
        except Asset.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            asset = AssetService.restore_asset(asset=asset)
        except AssetNotDeletedException:
            return Response(
                {"detail": "Asset is not deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                return Response(
                    exc.message_dict, status=status.HTTP_409_CONFLICT
                )
            return Response(
                {"detail": exc.messages}, status=status.HTTP_409_CONFLICT
            )

        serializer = AssetSerializer(asset, context={"request": request})
        return Response(serializer.data)


@extend_schema(
    request=inline_serializer(
        "AssetSupervisorRequest",
        fields={"supervisor": serializers.UUIDField()},
    ),
    responses={200: AssetSerializer},
    summary="Assign a supervisor to an asset",
    description=(
        "Sets the `supervisor` field on the asset. The new supervisor must "
        "belong to the same tenant as the asset.\n\n"
        "This endpoint is a convenience alternative to "
        "`PATCH /{id}/` with only the `supervisor` field — it uses the same "
        "service method and publishes an `asset.supervisor_assigned` event.\n\n"
        "**Required fields:**\n"
        "- `supervisor` — UUID of the user to assign as supervisor.\n\n"
        "**Errors:**\n"
        "- `400` — `supervisor` not provided, user UUID not found, or user "
        "belongs to a different tenant.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Asset not found, deleted, or belongs to a different tenant."
    ),
)
class AssetSupervisorView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsAuthenticated,
        IsStaffOrSuperuser,
        TenantHeaderRequired,
    ]

    def _get_asset(self, request, pk):
        return (
            Asset.objects.for_tenant(request.tenant)
            .not_deleted()
            .filter(pk=pk)
            .first()
        )

    def post(self, request, pk):
        asset = self._get_asset(request, pk)
        if asset is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        supervisor_id = request.data.get("supervisor")
        if not supervisor_id:
            return Response(
                {"supervisor": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            supervisor = User.objects.get(pk=supervisor_id)
        except (User.DoesNotExist, ValueError):
            return Response(
                {"supervisor": "Invalid supervisor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            hasattr(supervisor, "tenant_id")
            and supervisor.tenant_id != request.tenant.id
        ):
            return Response(
                {
                    "supervisor": "The supervisor must belong to the same tenant."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        asset = AssetService.assign_supervisor(
            asset=asset, supervisor=supervisor
        )
        return Response(
            AssetSerializer(asset, context={"request": request}).data
        )


@extend_schema(
    request=SensorAlertSerializer,
    responses={202: None},
    summary="Report an alert for an asset",
    description=(
        "Signals that something is wrong with the asset and publishes an "
        "`asset.sensor_alert` outbox event. The asset's supervisor will be "
        "notified via email by the downstream Lambda worker.\n\n"
        "**Optional fields:**\n"
        "- `message` — Free-text description of the problem.\n"
        "- `severity` — `warning` (default) or `critical`.\n\n"
        "**Errors:**\n"
        "- `400` — Invalid `severity` value.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Asset not found, deleted, or belongs to a different "
        "tenant."
    ),
)
class AssetSensorAlertView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [
        permissions.IsAuthenticated,
        IsStaffOrAssetSupervisor,
        TenantHeaderRequired,
    ]

    def post(self, request, pk):
        try:
            asset = (
                Asset.objects.for_tenant(request.tenant)
                .not_deleted()
                .select_related("supervisor", "asset_type")
                .get(pk=pk)
            )
        except Asset.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, asset)

        serializer = SensorAlertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AssetService.report_sensor_alert(
            asset=asset,
            alert_data=serializer.validated_data,
        )

        return Response(status=status.HTTP_202_ACCEPTED)
