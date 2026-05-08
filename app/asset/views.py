from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Asset
from .serializers import AssetSerializer


class AssetListCreateView(generics.ListCreateAPIView):
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Asset.objects.for_tenant(self.request.user.tenant).not_deleted()

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class AssetDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AssetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Asset.objects.for_tenant(self.request.user.tenant)

    def destroy(self, request, *args, **kwargs):
        asset = self.get_object()
        asset.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetRestoreView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            asset = Asset.objects.for_tenant(request.user.tenant).get(pk=pk)
        except Asset.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if not asset.is_deleted:
            return Response(
                {"detail": "Asset is not deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            asset.restore()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                return Response(exc.message_dict, status=status.HTTP_409_CONFLICT)
            return Response(
                {"detail": exc.messages}, status=status.HTTP_409_CONFLICT
            )

        serializer = AssetSerializer(asset, context={"request": request})
        return Response(serializer.data)
