import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from asset.models import Asset
from outbox.models import OutboxEvent

logger = logging.getLogger(__name__)

MAINTENANCE_WARNING_DAYS = 7
SOURCE_SERVICE = "asset-service"
AGGREGATE_TYPE = "Asset"


def _create_outbox_event(asset: Asset, event_type: str, payload: dict):
    OutboxEvent.objects.create(
        event_type=event_type,
        aggregate_type=AGGREGATE_TYPE,
        aggregate_id=asset.id,
        tenant_id=asset.tenant_id,
        payload=payload,
        event_version=1,
        source_service=SOURCE_SERVICE,
        idempotency_key=f"{event_type}:{asset.id}:{timezone.now().date()}",
    )
    logger.info(
        "Outbox event created event_type=%s asset_id=%s",
        event_type,
        asset.id,
    )


def _publish_upcoming_notification(asset: Asset, days_left: int):
    _create_outbox_event(
        asset=asset,
        event_type="asset.maintenance.upcoming",
        payload={
            "asset_id": str(asset.id),
            "asset_name": asset.name,
            "next_maintenance_date": asset.next_maintenance_date.isoformat(),
            "days_left": days_left,
            "message": (
                f"El mantenimiento del activo '{asset.name}' está programado "
                f"para el {asset.next_maintenance_date.isoformat()}. "
                f"Faltan {days_left} día(s)."
            ),
        },
    )


def _publish_overdue_notification(asset: Asset, days_overdue: int):
    _create_outbox_event(
        asset=asset,
        event_type="asset.maintenance.overdue",
        payload={
            "asset_id": str(asset.id),
            "asset_name": asset.name,
            "next_maintenance_date": asset.next_maintenance_date.isoformat(),
            "days_overdue": days_overdue,
            "message": (
                f"El mantenimiento del activo '{asset.name}' estaba programado "
                f"para el {asset.next_maintenance_date.isoformat()} "
                f"y se encuentra VENCIDO hace {days_overdue} día(s)."
            ),
        },
    )


def check_maintenance_dates():
    today = timezone.now().date()
    warning_cutoff = today + timedelta(days=MAINTENANCE_WARNING_DAYS)

    assets = Asset.objects.filter(next_maintenance_date__isnull=False)

    upcoming_count = overdue_count = skipped_count = 0

    for asset in assets:
        maintenance_date = asset.next_maintenance_date

        if hasattr(maintenance_date, "date"):
            maintenance_date = maintenance_date.date()

        try:
            with transaction.atomic():
                if maintenance_date < today:
                    days_overdue = (today - maintenance_date).days
                    _publish_overdue_notification(asset, days_overdue)
                    overdue_count += 1

                elif maintenance_date <= warning_cutoff:
                    days_left = (maintenance_date - today).days
                    _publish_upcoming_notification(asset, days_left)
                    upcoming_count += 1

                else:
                    skipped_count += 1

        except Exception as exc:
            logger.error(
                "Failed to create outbox event for asset_id=%s: %s",
                asset.id,
                exc,
            )

    logger.info(
        "Maintenance check complete: upcoming=%d overdue=%d skipped=%d",
        upcoming_count,
        overdue_count,
        skipped_count,
    )

    return upcoming_count, overdue_count, skipped_count


class Command(BaseCommand):
    help = (
        "Revisa los activos con next_maintenance_date próximo o vencido "
        "y publica eventos en la tabla outbox transaccional."
    )

    def handle(self, *args, **_):
        self.stdout.write("Iniciando revisión de fechas de mantenimiento...")

        upcoming, overdue, skipped = check_maintenance_dates()

        self.stdout.write(
            self.style.SUCCESS(
                f"Revisión completa — próximos: {upcoming} "
                f"| vencidos: {overdue} | sin acción: {skipped}"
            )
        )
