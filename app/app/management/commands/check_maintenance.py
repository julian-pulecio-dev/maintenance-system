import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from asset.models import Asset
from outbox.models import OutboxEvent
from work_order.models import WorkOrder

logger = logging.getLogger(__name__)

WARNING_DAYS = 7

ASSET_SOURCE_SERVICE = "asset-service"
ASSET_AGGREGATE_TYPE = "Asset"

EVENT_MAINTENANCE_UPCOMING = "asset.maintenance.upcoming"
EVENT_MAINTENANCE_OVERDUE = "asset.maintenance.overdue"

WO_SOURCE_SERVICE = "work-order-service"
WO_AGGREGATE_TYPE = "WorkOrder"

EVENT_WO_DUE_UPCOMING = "work_order.due_date.upcoming"
EVENT_WO_DUE_OVERDUE = "work_order.due_date.overdue"

_WO_ACTIVE_STATUSES = {
    WorkOrder.WorkOrderStatus.OPEN,
    WorkOrder.WorkOrderStatus.IN_PROGRESS,
    WorkOrder.WorkOrderStatus.ON_HOLD,
}


def _build_idempotency_key(*, event_type: str, aggregate_id, ref_date) -> str:
    return f"{event_type}:{aggregate_id}:{ref_date.isoformat()}"


def _try_create_outbox_event(
    *,
    tenant_id,
    event_type: str,
    aggregate_type: str,
    aggregate_id,
    source_service: str,
    idempotency_key: str,
    payload: dict,
) -> bool:
    try:
        OutboxEvent.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            tenant_id=tenant_id,
            payload=payload,
            event_version=1,
            source_service=source_service,
            idempotency_key=idempotency_key,
        )
        logger.info(
            "Outbox event created event_type=%s aggregate_id=%s",
            event_type,
            aggregate_id,
        )
        return True
    except IntegrityError:
        logger.debug(
            "Notification already exists event_type=%s aggregate_id=%s",
            event_type,
            aggregate_id,
        )
        return False


def _publish_maintenance_upcoming(
    *, asset: Asset, maintenance_date, days_left: int
) -> bool:
    return _try_create_outbox_event(
        tenant_id=asset.tenant_id,
        event_type=EVENT_MAINTENANCE_UPCOMING,
        aggregate_type=ASSET_AGGREGATE_TYPE,
        aggregate_id=asset.id,
        source_service=ASSET_SOURCE_SERVICE,
        idempotency_key=_build_idempotency_key(
            event_type=EVENT_MAINTENANCE_UPCOMING,
            aggregate_id=asset.id,
            ref_date=maintenance_date,
        ),
        payload={
            "data": {
                "id": str(asset.id),
                "name": asset.name,
                "serial_number": asset.serial_number,
                "asset_type": {"name": asset.asset_type.name},
                "status": asset.status,
                "location": asset.location,
                "description": asset.description,
                "installation_date": (
                    asset.installation_date.isoformat()
                    if asset.installation_date
                    else None
                ),
                "last_maintenance_date": (
                    asset.last_maintenance_date.isoformat()
                    if asset.last_maintenance_date
                    else None
                ),
                "recommended_maintenance_interval_days": (
                    asset.recommended_maintenance_interval_days
                ),
                "next_maintenance_date": maintenance_date.isoformat(),
                "days_left": days_left,
                "supervisor": {
                    "email": asset.supervisor.email,
                    "name": asset.supervisor.name,
                },
                "created_at": asset.created_at.isoformat(),
                "updated_at": asset.updated_at.isoformat(),
            },
        },
    )


def _publish_maintenance_overdue(
    *, asset: Asset, maintenance_date, days_overdue: int
) -> bool:
    return _try_create_outbox_event(
        tenant_id=asset.tenant_id,
        event_type=EVENT_MAINTENANCE_OVERDUE,
        aggregate_type=ASSET_AGGREGATE_TYPE,
        aggregate_id=asset.id,
        source_service=ASSET_SOURCE_SERVICE,
        idempotency_key=_build_idempotency_key(
            event_type=EVENT_MAINTENANCE_OVERDUE,
            aggregate_id=asset.id,
            ref_date=maintenance_date,
        ),
        payload={
            "data": {
                "id": str(asset.id),
                "name": asset.name,
                "serial_number": asset.serial_number,
                "asset_type": {"name": asset.asset_type.name},
                "status": asset.status,
                "location": asset.location,
                "description": asset.description,
                "installation_date": (
                    asset.installation_date.isoformat()
                    if asset.installation_date
                    else None
                ),
                "last_maintenance_date": (
                    asset.last_maintenance_date.isoformat()
                    if asset.last_maintenance_date
                    else None
                ),
                "recommended_maintenance_interval_days": (
                    asset.recommended_maintenance_interval_days
                ),
                "next_maintenance_date": maintenance_date.isoformat(),
                "days_overdue": days_overdue,
                "supervisor": {
                    "email": asset.supervisor.email,
                    "name": asset.supervisor.name,
                },
                "created_at": asset.created_at.isoformat(),
                "updated_at": asset.updated_at.isoformat(),
            },
        },
    )


def check_maintenance_dates():
    today = timezone.now().date()
    warning_cutoff = today + timedelta(days=WARNING_DAYS)

    assets = (
        Asset.objects.not_deleted()
        .select_related("supervisor", "asset_type")
        .filter(last_maintenance_date__isnull=False)
    )

    upcoming_count = 0
    overdue_count = 0
    skipped_count = 0

    for asset in assets.iterator(chunk_size=1000):
        maintenance_date = asset.next_maintenance_date

        try:
            if maintenance_date < today:
                days_overdue = (today - maintenance_date).days
                created = _publish_maintenance_overdue(
                    asset=asset,
                    maintenance_date=maintenance_date,
                    days_overdue=days_overdue,
                )
                if created:
                    overdue_count += 1
                else:
                    skipped_count += 1

            elif maintenance_date <= warning_cutoff:
                days_left = (maintenance_date - today).days
                created = _publish_maintenance_upcoming(
                    asset=asset,
                    maintenance_date=maintenance_date,
                    days_left=days_left,
                )
                if created:
                    upcoming_count += 1
                else:
                    skipped_count += 1

            else:
                skipped_count += 1

        except Exception:
            logger.exception(
                "Failed to process maintenance notification asset_id=%s",
                asset.id,
            )

    logger.info(
        "Maintenance check complete upcoming=%d overdue=%d skipped=%d",
        upcoming_count,
        overdue_count,
        skipped_count,
    )

    return upcoming_count, overdue_count, skipped_count


def _wo_payload(*, work_order: WorkOrder, extra: dict) -> dict:
    asset = work_order.asset
    assigned_to = work_order.assigned_to
    return {
        "data": {
            "id": str(work_order.id),
            "title": work_order.title,
            "status": work_order.status,
            "priority": work_order.priority,
            "due_date": (
                work_order.due_date.isoformat() if work_order.due_date else None
            ),
            "scheduled_date": (
                work_order.scheduled_date.isoformat()
                if work_order.scheduled_date
                else None
            ),
            "description": work_order.description,
            "notes": work_order.notes,
            "asset": {
                "id": str(asset.id),
                "name": asset.name,
                "serial_number": asset.serial_number,
                "location": asset.location,
            },
            "assigned_to": {
                "id": str(assigned_to.id),
                "email": assigned_to.email,
                "name": assigned_to.name,
            },
            "created_at": work_order.created_at.isoformat(),
            "updated_at": work_order.updated_at.isoformat(),
            **extra,
        },
    }


def _publish_wo_due_upcoming(
    *, work_order: WorkOrder, days_left: int
) -> bool:
    return _try_create_outbox_event(
        tenant_id=work_order.tenant_id,
        event_type=EVENT_WO_DUE_UPCOMING,
        aggregate_type=WO_AGGREGATE_TYPE,
        aggregate_id=work_order.id,
        source_service=WO_SOURCE_SERVICE,
        idempotency_key=_build_idempotency_key(
            event_type=EVENT_WO_DUE_UPCOMING,
            aggregate_id=work_order.id,
            ref_date=work_order.due_date,
        ),
        payload=_wo_payload(
            work_order=work_order, extra={"days_left": days_left}
        ),
    )


def _publish_wo_due_overdue(
    *, work_order: WorkOrder, days_overdue: int
) -> bool:
    return _try_create_outbox_event(
        tenant_id=work_order.tenant_id,
        event_type=EVENT_WO_DUE_OVERDUE,
        aggregate_type=WO_AGGREGATE_TYPE,
        aggregate_id=work_order.id,
        source_service=WO_SOURCE_SERVICE,
        idempotency_key=_build_idempotency_key(
            event_type=EVENT_WO_DUE_OVERDUE,
            aggregate_id=work_order.id,
            ref_date=work_order.due_date,
        ),
        payload=_wo_payload(
            work_order=work_order, extra={"days_overdue": days_overdue}
        ),
    )


def check_work_order_due_dates():
    today = timezone.now().date()
    warning_cutoff = today + timedelta(days=WARNING_DAYS)

    work_orders = (
        WorkOrder.objects.not_deleted()
        .select_related("asset", "assigned_to")
        .filter(
            status__in=_WO_ACTIVE_STATUSES,
            due_date__isnull=False,
            due_date__lte=warning_cutoff,
        )
    )

    upcoming_count = 0
    overdue_count = 0
    skipped_count = 0

    for wo in work_orders.iterator(chunk_size=1000):
        try:
            if wo.due_date < today:
                days_overdue = (today - wo.due_date).days
                created = _publish_wo_due_overdue(
                    work_order=wo, days_overdue=days_overdue
                )
                if created:
                    overdue_count += 1
                else:
                    skipped_count += 1

            else:
                days_left = (wo.due_date - today).days
                created = _publish_wo_due_upcoming(
                    work_order=wo, days_left=days_left
                )
                if created:
                    upcoming_count += 1
                else:
                    skipped_count += 1

        except Exception:
            logger.exception(
                "Failed to process due-date notification work_order_id=%s",
                wo.id,
            )

    logger.info(
        "Work order due-date check complete "
        "upcoming=%d overdue=%d skipped=%d",
        upcoming_count,
        overdue_count,
        skipped_count,
    )

    return upcoming_count, overdue_count, skipped_count


class Command(BaseCommand):

    help = (
        "Checks assets with upcoming or overdue maintenance dates and "
        "work orders with upcoming or overdue due dates, then publishes "
        "transactional outbox events for each."
    )

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting maintenance and due-date check...")

        m_upcoming, m_overdue, m_skipped = check_maintenance_dates()
        wo_upcoming, wo_overdue, wo_skipped = check_work_order_due_dates()

        self.stdout.write(
            self.style.SUCCESS(
                "Asset maintenance — "
                f"upcoming={m_upcoming} "
                f"overdue={m_overdue} "
                f"skipped={m_skipped}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Work order due dates — "
                f"upcoming={wo_upcoming} "
                f"overdue={wo_overdue} "
                f"skipped={wo_skipped}"
            )
        )
