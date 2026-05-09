from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import TenantHeaderRequired
from .models import Asset
from .serializers import AssetSerializer
from .services import (
    AssetAlreadyDeletedException,
    AssetNotDeletedException,
    AssetService,
)

User = get_user_model()


class AssetListCreateView(generics.ListCreateAPIView):
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

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


class AssetDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]
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


class AssetRestoreView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

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


class AssetSupervisorView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

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
