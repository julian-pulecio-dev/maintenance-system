from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from tenant.permissions import TenantHeaderRequired
from .models import WorkOrder
from .serializers import WorkOrderSerializer
from .services import (
    WorkOrderAlreadyDeletedException,
    WorkOrderNotDeletedException,
    WorkOrderService,
)

User = get_user_model()


class WorkOrderListCreateView(generics.ListCreateAPIView):
    serializer_class = WorkOrderSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def get_queryset(self):
        qs = (
            WorkOrder.objects.for_tenant(self.request.tenant)
            .not_deleted()
            .select_related("asset", "work_order_type", "assigned_to", "created_by")
        )

        params = self.request.query_params
        if status_param := params.get("status"):
            qs = qs.filter(status=status_param)
        if priority_param := params.get("priority"):
            qs = qs.filter(priority=priority_param)
        if asset_param := params.get("asset"):
            qs = qs.filter(asset_id=asset_param)
        if assigned_to_param := params.get("assigned_to"):
            qs = qs.filter(assigned_to_id=assigned_to_param)

        return qs

    def perform_create(self, serializer):
        try:
            work_order = WorkOrderService.create_work_order(
                tenant=self.request.tenant,
                validated_data={
                    **serializer.validated_data,
                    "created_by": self.request.user,
                },
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        serializer.instance = work_order


class WorkOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkOrderSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return WorkOrder.objects.for_tenant(self.request.tenant).select_related(
            "asset", "work_order_type", "assigned_to", "created_by"
        )

    def perform_update(self, serializer):
        try:
            work_order = WorkOrderService.update_work_order(
                work_order=serializer.instance,
                validated_data=serializer.validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        serializer.instance = work_order

    def destroy(self, request, *args, **kwargs):
        work_order = self.get_object()
        try:
            WorkOrderService.delete_work_order(work_order=work_order)
        except WorkOrderAlreadyDeletedException:
            return Response(
                {"detail": "Work order is already deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class _WorkOrderActionView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def _get_active_work_order(self, request, pk):
        return (
            WorkOrder.objects.for_tenant(request.tenant)
            .not_deleted()
            .select_related("asset", "work_order_type", "assigned_to", "created_by")
            .filter(pk=pk)
            .first()
        )

    def _respond(self, request, work_order, service_fn, **kwargs):
        try:
            work_order = service_fn(work_order=work_order, **kwargs)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                {"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            WorkOrderSerializer(work_order, context={"request": request}).data
        )


class WorkOrderRestoreView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def post(self, request, pk):
        try:
            work_order = (
                WorkOrder.objects.for_tenant(request.tenant)
                .select_related("asset", "work_order_type", "assigned_to", "created_by")
                .get(pk=pk)
            )
        except WorkOrder.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            work_order = WorkOrderService.restore_work_order(work_order=work_order)
        except WorkOrderNotDeletedException:
            return Response(
                {"detail": "Work order is not deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                return Response(exc.message_dict, status=status.HTTP_409_CONFLICT)
            return Response(
                {"detail": exc.messages}, status=status.HTTP_409_CONFLICT
            )

        return Response(
            WorkOrderSerializer(work_order, context={"request": request}).data
        )


class WorkOrderStartView(_WorkOrderActionView):
    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return self._respond(request, work_order, WorkOrderService.start_work_order)


class WorkOrderHoldView(_WorkOrderActionView):
    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return self._respond(
            request, work_order, WorkOrderService.put_work_order_on_hold
        )


class WorkOrderCompleteView(_WorkOrderActionView):
    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return self._respond(
            request, work_order, WorkOrderService.complete_work_order
        )


class WorkOrderCancelView(_WorkOrderActionView):
    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return self._respond(
            request, work_order, WorkOrderService.cancel_work_order
        )


class WorkOrderAssignView(_WorkOrderActionView):
    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        user_id = request.data.get("assigned_to")
        if not user_id:
            return Response(
                {"assigned_to": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return Response(
                {"assigned_to": "Invalid user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(user, "tenant_id") and user.tenant_id != request.tenant.id:
            return Response(
                {"assigned_to": "Assigned user must belong to the same tenant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return self._respond(
            request, work_order, WorkOrderService.assign_to, user=user
        )
