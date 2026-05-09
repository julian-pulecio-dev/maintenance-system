from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import TenantHeaderRequired
from .models import AssetType
from .serializers import AssetTypeSerializer


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
