import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction, IntegrityError
from django.db.models import (
    Q,
    F,
    ExpressionWrapper,
    DateField,
    IntegerField,
)
from django.db.models.functions import Cast
from django.utils import timezone

from asset.schemas import validate_asset_metadata
from asset_type.models import AssetType
from tenant.models import Tenant
from user.models import User

class AssetQuerySet(models.QuerySet):

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def not_deleted(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def operational(self):
        return self.not_deleted().filter(
            status=Asset.AssetStatus.ACTIVE,
        )

    def with_next_maintenance_date(self):
        return self.annotate(
            next_maintenance_date=ExpressionWrapper(
                F("last_maintenance_date")
                + (
                    Cast(
                        F("recommended_maintenance_interval_days"),
                        IntegerField(),
                    )
                    * timedelta(days=1)
                ),
                output_field=DateField(),
            )
        )

    def overdue(self):
        today = timezone.now().date()

        return (
            self.not_deleted()
            .with_next_maintenance_date()
            .filter(next_maintenance_date__lt=today)
        )

    def due_before(self, target_date):
        return (
            self.not_deleted()
            .with_next_maintenance_date()
            .filter(next_maintenance_date__lte=target_date)
        )

    def for_supervisor(self, supervisor):
        """Assets assigned to a specific supervisor."""
        return self.filter(supervisor=supervisor)

    def overdue_for_supervisor(self, supervisor):
        """Assets with overdue maintenance under a given supervisor."""
        return self.for_supervisor(supervisor).overdue()


class Asset(models.Model):

    class AssetStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        MAINTENANCE = "maintenance", "Maintenance"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="assets",
        db_index=True,
    )

    supervisor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="supervised_assets",
        db_index=True,
        help_text="User responsible for supervising this asset",
    )

    serial_number = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Manufacturer serial number (unique per tenant)",
    )

    name = models.CharField(max_length=255, db_index=True)

    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="assets",
        db_index=True,
    )

    location = models.CharField(max_length=255, db_index=True)

    installation_date = models.DateField()

    status = models.CharField(
        max_length=50,
        choices=AssetStatus.choices,
        default=AssetStatus.ACTIVE,
        db_index=True,
    )

    description = models.TextField(null=True, blank=True)

    last_maintenance_date = models.DateField(null=True, blank=True)

    recommended_maintenance_interval_days = models.PositiveIntegerField()

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = AssetQuerySet.as_manager()

    class Meta:
        db_table = "assets"

        indexes = [
            models.Index(
                fields=["tenant", "deleted_at"],
                name="idx_asset_tenant_deleted",
            ),
            models.Index(
                fields=["tenant", "status"], name="idx_asset_tenant_status"
            ),
            models.Index(
                fields=["tenant", "asset_type"], name="idx_asset_tenant_type"
            ),
            models.Index(
                fields=["tenant", "last_maintenance_date"],
                name="idx_asset_tenant_maintenance",
            ),
            # Supervisor indexes
            models.Index(
                fields=["tenant", "supervisor"],
                name="idx_asset_tenant_supervisor",
            ),
            models.Index(
                fields=["supervisor", "status"],
                name="idx_asset_supervisor_status",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=Q(recommended_maintenance_interval_days__gt=0),
                name="chk_recommended_interval_positive",
            ),
            models.CheckConstraint(
                check=(
                    Q(last_maintenance_date__isnull=True)
                    | Q(last_maintenance_date__gte=F("installation_date"))
                ),
                name="chk_last_maintenance_after_installation",
            ),
            models.UniqueConstraint(
                fields=["tenant", "serial_number"],
                condition=Q(
                    deleted_at__isnull=True,
                    serial_number__isnull=False,
                ),
                name="uq_tenant_active_serial_number",
            ),
        ]

    def clean(self):
        super().clean()
        self._validate_dates()
        self._validate_metadata()
        self._validate_supervisor()

    def _validate_dates(self):
        today = timezone.now().date()
        errors = {}

        if self.installation_date and self.installation_date > today:
            errors["installation_date"] = (
                "Installation date cannot be in the future."
            )

        if self.last_maintenance_date and self.last_maintenance_date > today:
            errors["last_maintenance_date"] = (
                "Last maintenance date cannot be in the future."
            )

        if (
            self.installation_date
            and self.last_maintenance_date
            and self.last_maintenance_date < self.installation_date
        ):
            errors["last_maintenance_date"] = (
                "Last maintenance date cannot be before installation date."
            )

        if errors:
            raise ValidationError(errors)

    def _validate_metadata(self):
        try:
            validate_asset_metadata(self)
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)

    def _validate_supervisor(self):
        if hasattr(self.supervisor, "tenant"):
            if self.supervisor.tenant_id != self.tenant_id:
                raise ValidationError(
                    {"supervisor": "The supervisor must belong to the same tenant."}
                )

    def mark_as_active(self):
        self.status = self.AssetStatus.ACTIVE

    def mark_as_inactive(self):
        self.status = self.AssetStatus.INACTIVE

    def mark_as_in_maintenance(self):
        self.status = self.AssetStatus.MAINTENANCE

    def mark_as_failed(self):
        self.status = self.AssetStatus.FAILED

    def save(self, *args, **kwargs):
        """
        Validation is intentionally NOT enforced here.

        Responsibility moved to:
        - serializers
        - forms
        - service layer
        - application commands
        """
        super().save(*args, **kwargs)

    def calculate_next_maintenance_date(self):
        if (
            self.last_maintenance_date is None
            or self.recommended_maintenance_interval_days is None
        ):
            return None

        return self.last_maintenance_date + timedelta(
            days=self.recommended_maintenance_interval_days
        )

    def assign_supervisor(self, supervisor):
        """Assigns a supervisor and persists the change."""
        self.supervisor = supervisor
        self.save(update_fields=["supervisor", "updated_at"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def is_operational(self):
        return not self.is_deleted and self.status == self.AssetStatus.ACTIVE

    @property
    def next_maintenance_date(self):
        return self.calculate_next_maintenance_date()

    @property
    def is_maintenance_overdue(self):
        next_date = self.next_maintenance_date

        if next_date is None:
            return False

        return timezone.now().date() > next_date

    @property
    def has_supervisor(self) -> bool:
        return True

    @property
    def supervisor_name(self) -> str:
        return str(self.supervisor)

    def get_metadata_value(self, path: str, default=None):
        current = self.metadata

        for key in path.split("."):
            if not isinstance(current, dict):
                return default
            if key not in current:
                return default
            current = current[key]

        return current

    def soft_delete(self):
        if self.is_deleted:
            return

        self.deleted_at = timezone.now()

        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self):
        if not self.is_deleted:
            return

        self.deleted_at = None

        try:
            with transaction.atomic():
                self.save(update_fields=["deleted_at", "updated_at"])
        except IntegrityError:
            raise ValidationError(
                {
                    "serial_number": (
                        "Cannot restore asset because another "
                        "active asset already uses this serial number."
                    )
                }
            )

    def __str__(self):
        identifier = self.serial_number or str(self.id)
        return f"{self.name} - {identifier}"