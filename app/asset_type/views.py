from django.db.models.deletion import ProtectedError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import AssetType
from .serializers import AssetTypeSerializer


class AssetTypeListCreateView(generics.ListCreateAPIView):
    serializer_class = AssetTypeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AssetType.objects.filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class AssetTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssetTypeSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return AssetType.objects.filter(tenant=self.request.user.tenant)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete asset type with existing assets."},
                status=status.HTTP_409_CONFLICT,
            )
