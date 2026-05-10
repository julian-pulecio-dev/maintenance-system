import copy
from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from outbox.models import OutboxEvent
from .models import Asset


class AssetAlreadyDeletedException(Exception):
    pass


class AssetNotDeletedException(Exception):
    pass


def _serialize_supervisor(asset: Asset) -> Dict[str, Any]:
    supervisor = asset.supervisor
    return {
        "id": str(supervisor.id),
        "email": supervisor.email,
        "name": supervisor.name,
        "is_active": supervisor.is_active,
    }


def _serialize_asset_type(asset: Asset) -> Dict[str, Any]:
    asset_type = asset.asset_type
    return {
        "id": str(asset_type.id),
        "name": asset_type.name,
        "description": asset_type.description,
    }


def _build_payload(asset: Asset) -> Dict[str, Any]:
    return {
        "version": 1,
        "data": {
            "id": str(asset.id),
            "tenant_id": str(asset.tenant_id),
            "supervisor": _serialize_supervisor(asset),
            "serial_number": asset.serial_number,
            "name": asset.name,
            "asset_type": _serialize_asset_type(asset),
            "location": asset.location,
            "installation_date": (
                asset.installation_date.isoformat()
                if asset.installation_date
                else None
            ),
            "status": asset.status,
            "description": asset.description,
            "last_maintenance_date": (
                asset.last_maintenance_date.isoformat()
                if asset.last_maintenance_date
                else None
            ),
            "recommended_maintenance_interval_days": (
                asset.recommended_maintenance_interval_days
            ),
            "metadata": copy.deepcopy(asset.metadata),
            "created_at": asset.created_at.isoformat(),
            "updated_at": asset.updated_at.isoformat(),
            "deleted_at": (
                asset.deleted_at.isoformat() if asset.deleted_at else None
            ),
        },
    }


def _publish_event(
    *,
    asset: Asset,
    event_type: str,
    changed_fields: Optional[List[str]] = None,
) -> OutboxEvent:
    payload = _build_payload(asset)

    if changed_fields:
        payload["changed_fields"] = changed_fields

    return OutboxEvent.objects.create(
        tenant=asset.tenant,
        event_type=event_type,
        aggregate_type="asset",
        aggregate_id=asset.id,
        payload=payload,
        source_service="asset",
    )


class AssetService:

    @staticmethod
    @transaction.atomic
    def create_asset(
        *,
        tenant,
        validated_data: Dict[str, Any],
    ) -> Asset:
        try:
            asset = Asset.objects.create(tenant=tenant, **validated_data)
        except IntegrityError:
            raise DjangoValidationError(
                {
                    "serial_number": (
                        "An active asset with this serial number already exists."
                    )
                }
            )

        _publish_event(
            asset=asset,
            event_type="asset.created",
        )

        return asset

    @staticmethod
    @transaction.atomic
    def update_asset(
        *,
        asset: Asset,
        validated_data: Dict[str, Any],
    ) -> Asset:
        # select_for_update() ensures no other worker can modify
        # this asset until the transaction completes.
        asset = Asset.objects.select_for_update().get(pk=asset.pk)

        changed_fields: List[str] = []

        for field, value in validated_data.items():
            if getattr(asset, field) != value:
                setattr(asset, field, value)
                changed_fields.append(field)

        if not changed_fields:
            return asset

        # Explicitly set updated_at so Django respects it even when
        # using update_fields (auto_now is not reliable in that case).
        asset.updated_at = timezone.now()
        changed_fields.append("updated_at")

        try:
            asset.save(update_fields=changed_fields)
        except IntegrityError:
            raise DjangoValidationError(
                {
                    "serial_number": (
                        "An active asset with this serial number already exists."
                    )
                }
            )

        _publish_event(
            asset=asset,
            event_type="asset.updated",
            changed_fields=changed_fields,
        )

        return asset

    @staticmethod
    @transaction.atomic
    def delete_asset(*, asset: Asset) -> Asset:
        # select_for_update() prevents race conditions between workers
        # attempting to delete the same asset concurrently.
        asset = Asset.objects.select_for_update().get(pk=asset.pk)

        if asset.deleted_at is not None:
            raise AssetAlreadyDeletedException(
                f"Asset {asset.id} already deleted at {asset.deleted_at}."
            )

        asset.soft_delete()

        _publish_event(
            asset=asset,
            event_type="asset.deleted",
        )

        return asset

    @staticmethod
    @transaction.atomic
    def assign_supervisor(*, asset: Asset, supervisor) -> Asset:
        asset = Asset.objects.select_for_update().get(pk=asset.pk)
        asset.assign_supervisor(supervisor)
        _publish_event(
            asset=asset,
            event_type="asset.supervisor_assigned",
            changed_fields=["supervisor"],
        )
        return asset

    @staticmethod
    def report_sensor_alert(
        *, asset: Asset, alert_data: Dict[str, Any]
    ) -> OutboxEvent:
        payload = _build_payload(asset)
        payload["data"]["alert"] = alert_data
        return OutboxEvent.objects.create(
            tenant=asset.tenant,
            event_type="asset.sensor_alert",
            aggregate_type="asset",
            aggregate_id=asset.id,
            payload=payload,
            source_service="asset",
        )

    @staticmethod
    @transaction.atomic
    def restore_asset(*, asset: Asset) -> Asset:
        # select_for_update() prevents race conditions between workers
        # attempting to restore the same asset concurrently.
        asset = Asset.objects.select_for_update().get(pk=asset.pk)

        if asset.deleted_at is None:
            raise AssetNotDeletedException(
                f"Asset {asset.id} is not deleted and cannot be restored."
            )

        asset.restore()

        _publish_event(
            asset=asset,
            event_type="asset.restored",
        )

        return asset
