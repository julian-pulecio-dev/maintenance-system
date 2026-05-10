import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from asset.models import Asset
from outbox.models import OutboxEvent

logger = logging.getLogger(__name__)

MAINTENANCE_WARNING_DAYS = 7

SOURCE_SERVICE = "asset-service"
AGGREGATE_TYPE = "Asset"

EVENT_UPCOMING = "asset.maintenance.upcoming"
EVENT_OVERDUE = "asset.maintenance.overdue"


def _build_idempotency_key(
    *,
    event_type: str,
    asset_id,
    maintenance_date,
) -> str:
    """
    Generates a deterministic idempotency key for a
    maintenance notification cycle.

    Same asset + same event type + same maintenance date
    = same logical event.
    """
    return (
        f"{event_type}:"
        f"{asset_id}:"
        f"{maintenance_date.isoformat()}"
    )


def _create_outbox_event(
    *,
    asset: Asset,
    event_type: str,
    maintenance_date,
    payload: dict,
) -> bool:

    try:
        OutboxEvent.objects.create(
            event_type=event_type,
            aggregate_type=AGGREGATE_TYPE,
            aggregate_id=asset.id,
            tenant_id=asset.tenant_id,
            payload=payload,
            event_version=1,
            source_service=SOURCE_SERVICE,
            idempotency_key=_build_idempotency_key(
                event_type=event_type,
                asset_id=asset.id,
                maintenance_date=maintenance_date,
            ),
        )

        logger.info(
            (
                "Maintenance outbox event created "
                "event_type=%s asset_id=%s"
            ),
            event_type,
            asset.id,
        )

        return True

    except IntegrityError:
        logger.debug(
            (
                "Maintenance notification already exists "
                "event_type=%s asset_id=%s"
            ),
            event_type,
            asset.id,
        )

        return False


def _publish_upcoming_notification(
    *,
    asset: Asset,
    maintenance_date,
    days_left: int,
) -> bool:

    return _create_outbox_event(
        asset=asset,
        event_type=EVENT_UPCOMING,
        maintenance_date=maintenance_date,
        payload={
            "asset_id": str(asset.id),
            "asset_name": asset.name,
            "next_maintenance_date": (
                maintenance_date.isoformat()
            ),
            "days_left": days_left,
        },
    )


def _publish_overdue_notification(
    *,
    asset: Asset,
    maintenance_date,
    days_overdue: int,
) -> bool:

    return _create_outbox_event(
        asset=asset,
        event_type=EVENT_OVERDUE,
        maintenance_date=maintenance_date,
        payload={
            "asset_id": str(asset.id),
            "asset_name": asset.name,
            "next_maintenance_date": (
                maintenance_date.isoformat()
            ),
            "days_overdue": days_overdue,
        },
    )


def check_maintenance_dates():

    today = timezone.now().date()

    warning_cutoff = (
        today + timedelta(days=MAINTENANCE_WARNING_DAYS)
    )

    assets = (
        Asset.objects.not_deleted()
        .filter(
            last_maintenance_date__isnull=False,
            next_maintenance_date__isnull=False,
            next_maintenance_date__lte=warning_cutoff,
        )
        .only(
            "id",
            "tenant_id",
            "name",
            "next_maintenance_date",
        )
    )

    upcoming_count = 0
    overdue_count = 0
    skipped_count = 0

    for asset in assets.iterator(chunk_size=1000):

        maintenance_date = asset.next_maintenance_date

        try:

            if maintenance_date < today:

                days_overdue = (
                    today - maintenance_date
                ).days

                created = _publish_overdue_notification(
                    asset=asset,
                    maintenance_date=maintenance_date,
                    days_overdue=days_overdue,
                )

                if created:
                    overdue_count += 1
                else:
                    skipped_count += 1

            else:

                days_left = (
                    maintenance_date - today
                ).days

                created = _publish_upcoming_notification(
                    asset=asset,
                    maintenance_date=maintenance_date,
                    days_left=days_left,
                )

                if created:
                    upcoming_count += 1
                else:
                    skipped_count += 1

        except Exception:
            logger.exception(
                (
                    "Failed to process maintenance "
                    "notification asset_id=%s"
                ),
                asset.id,
            )

    logger.info(
        (
            "Maintenance check complete "
            "upcoming=%d overdue=%d skipped=%d"
        ),
        upcoming_count,
        overdue_count,
        skipped_count,
    )

    return (
        upcoming_count,
        overdue_count,
        skipped_count,
    )


class Command(BaseCommand):

    help = (
        "Checks assets with upcoming or overdue "
        "maintenance dates and publishes "
        "transactional outbox events."
    )

    def handle(self, *args, **kwargs):

        self.stdout.write(
            "Starting maintenance notification check..."
        )

        upcoming, overdue, skipped = (
            check_maintenance_dates()
        )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Maintenance check complete "
                    f"upcoming={upcoming} "
                    f"overdue={overdue} "
                    f"skipped={skipped}"
                )
            )
        )