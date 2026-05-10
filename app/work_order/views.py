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

from tenant.permissions import TenantHeaderRequired
from .models import WorkOrder
from .serializers import WorkOrderSerializer
from .services import (
    WorkOrderAlreadyDeletedException,
    WorkOrderNotDeletedException,
    WorkOrderService,
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        summary="List work orders",
        description=(
            "Returns all non-deleted work orders for the current tenant, "
            "ordered by creation date (newest first).\n\n"
            "**Query parameters:**\n"
            "- `status` — Filter by status value: `open`, `in_progress`, "
            "`on_hold`, `completed`, `cancelled`.\n"
            "- `priority` — Filter by priority: `low`, `medium`, `high`, "
            "`critical`.\n"
            "- `asset` — Filter by asset UUID.\n"
            "- `assigned_to` — Filter by assigned user UUID.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                description="Filter by work order status.",
                required=False,
                type=str,
                enum=["open", "in_progress", "on_hold", "completed", "cancelled"],
            ),
            OpenApiParameter(
                name="priority",
                description="Filter by priority.",
                required=False,
                type=str,
                enum=["low", "medium", "high", "critical"],
            ),
            OpenApiParameter(
                name="asset",
                description="Filter by asset UUID.",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="assigned_to",
                description="Filter by assigned user UUID.",
                required=False,
                type=str,
            ),
        ],
    ),
    create=extend_schema(
        summary="Create a work order",
        description=(
            "Creates a new work order under the current tenant. "
            "`created_by` is set automatically from the authenticated user "
            "and cannot be overridden.\n\n"
            "**Required fields:**\n"
            "- `asset` — UUID of an asset belonging to this tenant.\n"
            "- `work_order_type` — UUID of a work order type belonging to "
            "this tenant.\n"
            "- `assigned_to` — UUID of a user belonging to this tenant.\n"
            "- `title` — Short description of the work to be done.\n"
            "- `priority` — One of `low`, `medium`, `high`, `critical`.\n\n"
            "**Optional fields:**\n"
            "- `description` — Extended description.\n"
            "- `scheduled_date` — Planned start date.\n"
            "- `due_date` — Must be on or after `scheduled_date`.\n"
            "- `notes` — Initial notes.\n"
            "- `estimated_hours` — Estimated duration in hours.\n\n"
            "**Errors:**\n"
            "- `400` — Validation error (e.g., asset belongs to another "
            "tenant, `due_date` before `scheduled_date`).\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header."
        ),
    ),
)
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


@extend_schema_view(
    retrieve=extend_schema(
        summary="Retrieve a work order",
        description=(
            "Returns the full detail of a single work order, including "
            "nested representations of the asset, work order type, "
            "assigned user, and creating user.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Work order not found or belongs to a different tenant."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update a work order",
        description=(
            "Updates one or more editable fields of a work order. "
            "All fields are optional — only sent fields are modified.\n\n"
            "**Editable fields:** `title`, `description`, `priority`, "
            "`asset`, `work_order_type`, `assigned_to`, `scheduled_date`, "
            "`due_date`, `estimated_hours`.\n\n"
            "**Read-only fields (ignored if sent):** `status`, "
            "`completed_date`, `created_by`, `created_at`, `updated_at`.\n\n"
            "Use the dedicated action endpoints (`/start`, `/hold`, "
            "`/complete`, `/cancel`) to change `status`.\n\n"
            "**Errors:**\n"
            "- `400` — Validation error (e.g., `due_date` before "
            "`scheduled_date`, cross-tenant relation).\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Work order not found or belongs to a different tenant."
        ),
    ),
    destroy=extend_schema(
        summary="Soft-delete a work order",
        description=(
            "Marks the work order as deleted by setting `deleted_at` to the "
            "current timestamp. The record is preserved in the database and "
            "can be restored via `POST /{id}/restore/`.\n\n"
            "Deleted work orders no longer appear in list or detail "
            "responses until restored.\n\n"
            "**Errors:**\n"
            "- `401` — Missing or invalid JWT token.\n"
            "- `403` — Missing `X-Tenant-ID` header.\n"
            "- `404` — Work order not found or belongs to a different tenant.\n"
            "- `409` — Work order is already deleted."
        ),
        responses={
            204: OpenApiResponse(description="Work order soft-deleted."),
            409: OpenApiResponse(description="Work order already deleted."),
        },
    ),
)
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


@extend_schema(
    request=_notes_schema,
    responses={200: WorkOrderSerializer},
    summary="Restore a soft-deleted work order",
    description=(
        "Removes the `deleted_at` timestamp, making the work order visible "
        "again in list and detail endpoints. The status is not changed — "
        "the work order returns to whichever status it had before deletion.\n\n"
        "**Required fields:**\n"
        "- `notes` — Reason for the restoration. Appended to the work "
        "order's notes history with a UTC timestamp.\n\n"
        "**Errors:**\n"
        "- `400` — `notes` not provided, or work order is not currently "
        "deleted.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Work order not found or belongs to a different tenant.\n"
        "- `409` — The related asset is also deleted; restore the asset first."
    ),
)
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


@extend_schema(
    request=_notes_schema,
    responses={200: WorkOrderSerializer},
    summary="Start a work order",
    description=(
        "Transitions the work order from `open` or `on_hold` to "
        "`in_progress`.\n\n"
        "**Required fields:**\n"
        "- `notes` — Reason for starting. Prepended to the notes history "
        "with a UTC timestamp.\n\n"
        "**Valid source statuses:** `open`, `on_hold`.\n\n"
        "**Errors:**\n"
        "- `400` — `notes` not provided.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Work order not found, deleted, or belongs to a different "
        "tenant.\n"
        "- `409` — Current status does not allow transitioning to "
        "`in_progress` (e.g., already completed or cancelled)."
    ),
)
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


@extend_schema(
    request=_notes_schema,
    responses={200: WorkOrderSerializer},
    summary="Put a work order on hold",
    description=(
        "Transitions the work order to `on_hold`, pausing active work "
        "without cancelling it.\n\n"
        "**Required fields:**\n"
        "- `notes` — Reason for the hold (e.g., waiting for parts). "
        "Prepended to the notes history with a UTC timestamp.\n\n"
        "**Valid source statuses:** `open`, `in_progress`.\n\n"
        "**Errors:**\n"
        "- `400` — `notes` not provided.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Work order not found, deleted, or belongs to a different "
        "tenant.\n"
        "- `409` — Current status does not allow transitioning to `on_hold` "
        "(e.g., already completed or cancelled)."
    ),
)
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


@extend_schema(
    request=_complete_schema,
    responses={200: WorkOrderSerializer},
    summary="Complete a work order",
    description=(
        "Transitions the work order from `in_progress` to `completed`. "
        "Also updates `asset.last_maintenance_date` to today's date in "
        "the same atomic transaction.\n\n"
        "**Required fields:**\n"
        "- `notes` — Summary of the work performed. Prepended to the notes "
        "history with a UTC timestamp.\n"
        "- `estimated_hours` — Total hours spent (decimal, e.g., `3.5`). "
        "Stored on the work order as `estimated_hours`.\n\n"
        "**Side effects on success:**\n"
        "- `status` → `completed`.\n"
        "- `completed_date` → today (UTC).\n"
        "- `asset.last_maintenance_date` → today (UTC).\n\n"
        "**Valid source statuses:** `in_progress`.\n\n"
        "**Errors:**\n"
        "- `400` — `notes` or `estimated_hours` not provided.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Work order not found, deleted, or belongs to a different "
        "tenant.\n"
        "- `409` — Current status does not allow completion (only "
        "`in_progress` can be completed)."
    ),
)
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


@extend_schema(
    request=_notes_schema,
    responses={200: WorkOrderSerializer},
    summary="Cancel a work order",
    description=(
        "Transitions the work order to `cancelled`. This is a terminal "
        "state — a cancelled work order cannot be reactivated through "
        "status transitions. It can be soft-deleted and restored if needed.\n\n"
        "**Required fields:**\n"
        "- `notes` — Reason for cancellation. Prepended to the notes "
        "history with a UTC timestamp.\n\n"
        "**Valid source statuses:** `open`, `in_progress`, `on_hold`.\n\n"
        "**Errors:**\n"
        "- `400` — `notes` not provided.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Work order not found, deleted, or belongs to a different "
        "tenant.\n"
        "- `409` — Work order is already completed or cancelled."
    ),
)
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


@extend_schema(
    request=_assign_schema,
    responses={200: WorkOrderSerializer},
    summary="Reassign a work order",
    description=(
        "Changes the `assigned_to` user on a work order. The new user must "
        "belong to the same tenant. Assignment is only allowed while the "
        "work order is active (not completed or cancelled).\n\n"
        "**Required fields:**\n"
        "- `assigned_to` — UUID of the user to assign. Must belong to the "
        "current tenant.\n"
        "- `notes` — Reason for the reassignment. Prepended to the notes "
        "history with a UTC timestamp.\n\n"
        "**Assignable statuses:** `open`, `in_progress`, `on_hold`.\n\n"
        "**Errors:**\n"
        "- `400` — `assigned_to` or `notes` not provided, user UUID not "
        "found, or user belongs to a different tenant.\n"
        "- `401` — Missing or invalid JWT token.\n"
        "- `403` — Missing `X-Tenant-ID` header.\n"
        "- `404` — Work order not found, deleted, or belongs to a different "
        "tenant.\n"
        "- `409` — Work order is completed or cancelled and cannot be "
        "reassigned."
    ),
)
class WorkOrderAssignView(_WorkOrderActionView):
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
