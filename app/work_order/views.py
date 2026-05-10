from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema, inline_serializer
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
            .select_related(
                "asset", "work_order_type", "assigned_to", "created_by"
            )
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
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
            )
        serializer.instance = work_order


class WorkOrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WorkOrderSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return WorkOrder.objects.for_tenant(
            self.request.tenant
        ).select_related(
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
                exc.message_dict
                if hasattr(exc, "message_dict")
                else exc.messages
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
    target_status = None

    def _get_active_work_order(self, request, pk):
        return (
            WorkOrder.objects.for_tenant(request.tenant)
            .not_deleted()
            .select_related(
                "asset", "work_order_type", "assigned_to", "created_by"
            )
            .filter(pk=pk)
            .first()
        )

    def _check_transition(self, work_order):
        allowed = WorkOrder.VALID_STATUS_TRANSITIONS.get(
            work_order.status, set()
        )
        if self.target_status not in allowed:
            return Response(
                {
                    "status": (
                        f"Cannot transition from '{work_order.status}' "
                        f"to '{self.target_status}'."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return None

    def _require_notes(self, request):
        notes = request.data.get("notes")
        if not notes:
            return None, Response(
                {"notes": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return notes, None

    def _respond(self, request, work_order, service_fn, **kwargs):
        try:
            work_order = service_fn(work_order=work_order, **kwargs)
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                return Response(
                    exc.message_dict, status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            WorkOrderSerializer(work_order, context={"request": request}).data
        )


_notes_schema = inline_serializer(
    "NotesRequest",
    fields={"notes": serializers.CharField()},
)

_assign_schema = inline_serializer(
    "AssignRequest",
    fields={
        "assigned_to": serializers.UUIDField(),
        "notes": serializers.CharField(),
    },
)

_complete_schema = inline_serializer(
    "CompleteRequest",
    fields={
        "notes": serializers.CharField(),
        "estimated_hours": serializers.DecimalField(
            max_digits=6, decimal_places=1
        ),
    },
)


@extend_schema(request=_notes_schema, responses=WorkOrderSerializer)
class WorkOrderRestoreView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, TenantHeaderRequired]

    def post(self, request, pk):
        try:
            work_order = (
                WorkOrder.objects.for_tenant(request.tenant)
                .select_related(
                    "asset", "work_order_type", "assigned_to", "created_by"
                )
                .get(pk=pk)
            )
        except WorkOrder.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        notes = request.data.get("notes")
        if not notes:
            return Response(
                {"notes": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            work_order = WorkOrderService.restore_work_order(
                work_order=work_order, notes=notes
            )
        except WorkOrderNotDeletedException:
            return Response(
                {"detail": "Work order is not deleted."},
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

        return Response(
            WorkOrderSerializer(work_order, context={"request": request}).data
        )


@extend_schema(request=_notes_schema, responses=WorkOrderSerializer)
class WorkOrderStartView(_WorkOrderActionView):
    target_status = WorkOrder.WorkOrderStatus.IN_PROGRESS

    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if err := self._check_transition(work_order):
            return err
        notes, err = self._require_notes(request)
        if err:
            return err
        return self._respond(
            request, work_order, WorkOrderService.start_work_order, notes=notes
        )


@extend_schema(request=_notes_schema, responses=WorkOrderSerializer)
class WorkOrderHoldView(_WorkOrderActionView):
    target_status = WorkOrder.WorkOrderStatus.ON_HOLD

    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if err := self._check_transition(work_order):
            return err
        notes, err = self._require_notes(request)
        if err:
            return err
        return self._respond(
            request,
            work_order,
            WorkOrderService.put_work_order_on_hold,
            notes=notes,
        )


@extend_schema(request=_complete_schema, responses=WorkOrderSerializer)
class WorkOrderCompleteView(_WorkOrderActionView):
    target_status = WorkOrder.WorkOrderStatus.COMPLETED

    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if err := self._check_transition(work_order):
            return err
        notes, err = self._require_notes(request)
        if err:
            return err
        estimated_hours = request.data.get("estimated_hours")
        if not estimated_hours:
            return Response(
                {"estimated_hours": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._respond(
            request,
            work_order,
            WorkOrderService.complete_work_order,
            notes=notes,
            estimated_hours=estimated_hours,
        )


@extend_schema(request=_notes_schema, responses=WorkOrderSerializer)
class WorkOrderCancelView(_WorkOrderActionView):
    target_status = WorkOrder.WorkOrderStatus.CANCELLED

    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if err := self._check_transition(work_order):
            return err
        notes, err = self._require_notes(request)
        if err:
            return err
        return self._respond(
            request,
            work_order,
            WorkOrderService.cancel_work_order,
            notes=notes,
        )


@extend_schema(request=_assign_schema, responses=WorkOrderSerializer)
class WorkOrderAssignView(_WorkOrderActionView):
    # assign is not a status transition — reuse _check_transition
    # by treating it as "must not be completed or cancelled"
    _ASSIGNABLE_STATUSES = {
        WorkOrder.WorkOrderStatus.OPEN,
        WorkOrder.WorkOrderStatus.IN_PROGRESS,
        WorkOrder.WorkOrderStatus.ON_HOLD,
    }

    def _check_transition(self, work_order):
        if work_order.status not in self._ASSIGNABLE_STATUSES:
            return Response(
                {
                    "status": "Cannot assign a completed or cancelled work order."
                },
                status=status.HTTP_409_CONFLICT,
            )
        return None

    def post(self, request, pk):
        work_order = self._get_active_work_order(request, pk)
        if work_order is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if err := self._check_transition(work_order):
            return err

        errors = {}

        user_id = request.data.get("assigned_to")
        if not user_id:
            errors["assigned_to"] = "This field is required."

        notes = request.data.get("notes")
        if not notes:
            errors["notes"] = "This field is required."

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return Response(
                {"assigned_to": "Invalid user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if hasattr(user, "tenant_id") and user.tenant_id != request.tenant.id:
            return Response(
                {
                    "assigned_to": "Assigned user must belong to the same tenant."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return self._respond(
            request,
            work_order,
            WorkOrderService.assign_to,
            user=user,
            notes=notes,
        )
