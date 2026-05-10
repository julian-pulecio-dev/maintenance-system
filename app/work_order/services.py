from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from outbox.models import OutboxEvent
from .models import WorkOrder


class WorkOrderAlreadyDeletedException(Exception):
    pass


class WorkOrderNotDeletedException(Exception):
    pass


def _serialize_assigned_to(work_order: WorkOrder) -> Dict[str, Any]:
    user = work_order.assigned_to

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
    }


def _serialize_created_by(work_order: WorkOrder) -> Dict[str, Any]:
    user = work_order.created_by

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
    }


def _serialize_asset(work_order: WorkOrder) -> Dict[str, Any]:
    asset = work_order.asset

    return {
        "id": str(asset.id),
        "name": asset.name,
        "serial_number": asset.serial_number,
        "status": asset.status,
    }


def _serialize_work_order_type(work_order: WorkOrder) -> Dict[str, Any]:
    work_order_type = work_order.work_order_type

    return {
        "id": str(work_order_type.id),
        "name": work_order_type.name,
    }


def _build_payload(work_order: WorkOrder) -> Dict[str, Any]:
    return {
        "version": 1,
        "data": {
            "id": str(work_order.id),
            "tenant_id": str(work_order.tenant_id),
            "asset": _serialize_asset(work_order),
            "work_order_type": _serialize_work_order_type(work_order),
            "assigned_to": _serialize_assigned_to(work_order),
            "created_by": _serialize_created_by(work_order),
            "title": work_order.title,
            "description": work_order.description,
            "status": work_order.status,
            "priority": work_order.priority,
            "scheduled_date": (
                work_order.scheduled_date.isoformat()
                if work_order.scheduled_date
                else None
            ),
            "due_date": (
                work_order.due_date.isoformat()
                if work_order.due_date
                else None
            ),
            "completed_date": (
                work_order.completed_date.isoformat()
                if work_order.completed_date
                else None
            ),
            "notes": work_order.notes,
            "created_at": work_order.created_at.isoformat(),
            "updated_at": work_order.updated_at.isoformat(),
            "deleted_at": (
                work_order.deleted_at.isoformat()
                if work_order.deleted_at
                else None
            ),
        },
    }


def _publish_event(
    *,
    work_order: WorkOrder,
    event_type: str,
    changed_fields: Optional[List[str]] = None,
) -> OutboxEvent:
    payload = _build_payload(work_order)

    if changed_fields:
        payload["changed_fields"] = changed_fields

    return OutboxEvent.objects.create(
        tenant=work_order.tenant,
        event_type=event_type,
        aggregate_type="work_order",
        aggregate_id=work_order.id,
        payload=payload,
        source_service="work_order",
    )


class WorkOrderService:

    @staticmethod
    @transaction.atomic
    def create_work_order(
        *,
        tenant,
        validated_data: Dict[str, Any],
    ) -> WorkOrder:
        work_order = WorkOrder.objects.create(
            tenant=tenant,
            **validated_data,
        )

        _publish_event(
            work_order=work_order,
            event_type="work_order.created",
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def update_work_order(
        *,
        work_order: WorkOrder,
        validated_data: Dict[str, Any],
    ) -> WorkOrder:
        # select_for_update() ensures no other worker can modify
        # this work order until the transaction completes.
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        changed_fields: List[str] = []

        for field, value in validated_data.items():
            if getattr(work_order, field) != value:
                setattr(work_order, field, value)
                changed_fields.append(field)

        if not changed_fields:
            return work_order

        # Explicitly set updated_at so Django respects it even when
        # using update_fields (auto_now is not reliable in that case).
        work_order.updated_at = timezone.now()
        changed_fields.append("updated_at")

        work_order.save(update_fields=changed_fields)

        _publish_event(
            work_order=work_order,
            event_type="work_order.updated",
            changed_fields=changed_fields,
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def delete_work_order(*, work_order: WorkOrder) -> WorkOrder:
        # select_for_update() prevents race conditions between workers
        # attempting to delete the same work order concurrently.
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        if work_order.deleted_at is not None:
            raise WorkOrderAlreadyDeletedException(
                f"WorkOrder {work_order.id} already deleted "
                f"at {work_order.deleted_at}."
            )

        work_order.soft_delete()

        _publish_event(
            work_order=work_order,
            event_type="work_order.deleted",
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def restore_work_order(*, work_order: WorkOrder, notes: str) -> WorkOrder:
        # select_for_update() prevents race conditions between workers
        # attempting to restore the same work order concurrently.
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        if work_order.deleted_at is None:
            raise WorkOrderNotDeletedException(
                f"WorkOrder {work_order.id} is not deleted "
                f"and cannot be restored."
            )

        work_order.restore(notes)

        _publish_event(
            work_order=work_order,
            event_type="work_order.restored",
            changed_fields=["deleted_at", "notes"],
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def assign_to(*, work_order: WorkOrder, user, notes: str) -> WorkOrder:
        # select_for_update() prevents race conditions between workers
        # attempting to reassign the same work order concurrently.
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        work_order.assign_to(user, notes)

        _publish_event(
            work_order=work_order,
            event_type="work_order.assigned",
            changed_fields=["assigned_to", "notes"],
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def start_work_order(*, work_order: WorkOrder, notes: str) -> WorkOrder:
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        work_order.start(notes)

        _publish_event(
            work_order=work_order,
            event_type="work_order.started",
            changed_fields=["status", "completed_date", "notes"],
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def put_work_order_on_hold(
        *, work_order: WorkOrder, notes: str
    ) -> WorkOrder:
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        work_order.put_on_hold(notes)

        _publish_event(
            work_order=work_order,
            event_type="work_order.put_on_hold",
            changed_fields=["status", "completed_date", "notes"],
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def complete_work_order(
        *, work_order: WorkOrder, notes: str, estimated_hours
    ) -> WorkOrder:
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        work_order.complete(notes, estimated_hours)

        asset = work_order.asset
        asset.last_maintenance_date = work_order.completed_date
        asset.save(update_fields=["last_maintenance_date", "updated_at"])

        _publish_event(
            work_order=work_order,
            event_type="work_order.completed",
            changed_fields=[
                "status",
                "completed_date",
                "estimated_hours",
                "notes",
            ],
        )

        return work_order

    @staticmethod
    @transaction.atomic
    def cancel_work_order(*, work_order: WorkOrder, notes: str) -> WorkOrder:
        work_order = WorkOrder.objects.select_for_update().get(
            pk=work_order.pk,
        )

        work_order.cancel(notes)

        _publish_event(
            work_order=work_order,
            event_type="work_order.cancelled",
            changed_fields=["status", "completed_date", "notes"],
        )

        return work_order
