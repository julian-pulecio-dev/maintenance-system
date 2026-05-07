from rest_framework import generics, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Tenant
from .serializers import TenantSerializer


class TenantListCreateView(generics.ListCreateAPIView):
    serializer_class = TenantSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = Tenant.objects.all()


class TenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TenantSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    queryset = Tenant.objects.all()
