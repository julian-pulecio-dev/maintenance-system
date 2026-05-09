from rest_framework import generics, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import TenantHeaderRequired
from .models import OutboxEvent
from .serializers import OutboxEventSerializer


class OutboxEventListView(generics.ListAPIView):
    serializer_class = OutboxEventSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def get_queryset(self):
        qs = OutboxEvent.objects.for_tenant(self.request.tenant)

        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)

        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        aggregate_type = self.request.query_params.get("aggregate_type")
        if aggregate_type:
            qs = qs.filter(aggregate_type=aggregate_type)

        aggregate_id = self.request.query_params.get("aggregate_id")
        if aggregate_id:
            qs = qs.filter(aggregate_id=aggregate_id)

        return qs


class OutboxEventDetailView(generics.RetrieveAPIView):
    serializer_class = OutboxEventSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def get_queryset(self):
        return OutboxEvent.objects.for_tenant(self.request.tenant)
