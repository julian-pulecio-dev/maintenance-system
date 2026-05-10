import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction, IntegrityError
from django.db.models import Q, F
from django.utils import timezone

from asset.models import Asset
from tenant.models import Tenant
from user.models import User
from work_order_type.models import WorkOrderType


class WorkOrderQuerySet(models.QuerySet):

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def not_deleted(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def for_asset(self, asset):
        return self.filter(asset=asset)

    def for_assigned_to(self, user):
        return self.filter(assigned_to=user)

    def open(self):
        return self.not_deleted().filter(
            status=WorkOrder.WorkOrderStatus.OPEN,
        )

    def in_progress(self):
        return self.not_deleted().filter(
            status=WorkOrder.WorkOrderStatus.IN_PROGRESS,
        )

    def completed(self):
        return self.not_deleted().filter(
            status=WorkOrder.WorkOrderStatus.COMPLETED,
        )

    def active(self):
        return self.not_deleted().filter(
            status__in=[
                WorkOrder.WorkOrderStatus.OPEN,
                WorkOrder.WorkOrderStatus.IN_PROGRESS,
                WorkOrder.WorkOrderStatus.ON_HOLD,
            ]
        )

    def overdue(self):
        today = timezone.now().date()

        return self.active().filter(
            due_date__lt=today,
        )


class WorkOrder(models.Model):

    class WorkOrderStatus(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        ON_HOLD = "on_hold", "On Hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class WorkOrderPriority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    VALID_STATUS_TRANSITIONS = {
        WorkOrderStatus.OPEN: {
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.ON_HOLD,
            WorkOrderStatus.CANCELLED,
        },
        WorkOrderStatus.IN_PROGRESS: {
            WorkOrderStatus.ON_HOLD,
            WorkOrderStatus.COMPLETED,
            WorkOrderStatus.CANCELLED,
        },
        WorkOrderStatus.ON_HOLD: {
            WorkOrderStatus.IN_PROGRESS,
            WorkOrderStatus.CANCELLED,
        },
        WorkOrderStatus.COMPLETED: set(),
        WorkOrderStatus.CANCELLED: set(),
    }

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="work_orders",
        db_index=True,
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="work_orders",
        db_index=True,
    )

    work_order_type = models.ForeignKey(
        WorkOrderType,
        on_delete=models.PROTECT,
        related_name="work_orders",
        db_index=True,
    )

    assigned_to = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="assigned_work_orders",
        db_index=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_work_orders",
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
        db_index=True,
    )

    description = models.TextField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=50,
        choices=WorkOrderStatus.choices,
        default=WorkOrderStatus.OPEN,
        db_index=True,
    )

    priority = models.CharField(
        max_length=50,
        choices=WorkOrderPriority.choices,
        default=WorkOrderPriority.MEDIUM,
        db_index=True,
    )

    scheduled_date = models.DateField(
        null=True,
        blank=True,
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
    )

    completed_date = models.DateField(
        null=True,
        blank=True,
    )

    notes = models.TextField(
        null=True,
        blank=True,
    )

    estimated_hours = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    objects = WorkOrderQuerySet.as_manager()

    class Meta:
        db_table = "work_orders"

        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["tenant", "deleted_at"],
                name="idx_work_order_tenant_deleted",
            ),
            models.Index(
                fields=["tenant", "status"],
                name="idx_work_order_tenant_status",
            ),
            models.Index(
                fields=["tenant", "asset"],
                name="idx_work_order_tenant_asset",
            ),
            models.Index(
                fields=["tenant", "assigned_to"],
                name="idx_work_order_tenant_assigned",
            ),
            models.Index(
                fields=["tenant", "due_date"],
                name="idx_work_order_tenant_due_date",
            ),
            models.Index(
                fields=["tenant", "priority"],
                name="idx_work_order_tenant_priority",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                check=(Q(completed_date__isnull=True) | Q(status="completed")),
                name=(
                    "chk_work_order_completed_date_requires_completed_status"
                ),
            ),
            models.CheckConstraint(
                check=(
                    Q(due_date__isnull=True)
                    | Q(scheduled_date__isnull=True)
                    | Q(due_date__gte=F("scheduled_date"))
                ),
                name="chk_work_order_due_date_after_scheduled",
            ),
        ]

    def clean(self):
        super().clean()

        self._validate_dates()
        self._validate_tenant_consistency()

    def _validate_dates(self):
        errors = {}

        if (
            self.scheduled_date
            and self.due_date
            and self.due_date < self.scheduled_date
        ):
            errors["due_date"] = "Due date cannot be before scheduled date."

        if (
            self.completed_date
            and self.status != self.WorkOrderStatus.COMPLETED
        ):
            errors["completed_date"] = (
                "Completed date can only be set " "when status is completed."
            )

        if errors:
            raise ValidationError(errors)

    def _validate_tenant_consistency(self):
        errors = {}

        if self.asset_id and self.asset.tenant_id != self.tenant_id:
            errors["asset"] = "Asset must belong to the same tenant."

        if (
            self.work_order_type_id
            and self.work_order_type.tenant_id != self.tenant_id
        ):
            errors["work_order_type"] = (
                "Work order type must belong " "to the same tenant."
            )

        if (
            self.assigned_to_id
            and self.assigned_to.tenant_id != self.tenant_id
        ):
            errors["assigned_to"] = (
                "Assigned user must belong " "to the same tenant."
            )

        if self.created_by_id and self.created_by.tenant_id != self.tenant_id:
            errors["created_by"] = (
                "Created by user must belong " "to the same tenant."
            )

        if errors:
            raise ValidationError(errors)

    def _validate_not_deleted(self):
        if self.is_deleted:
            raise ValidationError(
                {"non_field_errors": ("Cannot modify a deleted work order.")}
            )

    def _validate_transition(self, target_status):
        allowed = self.VALID_STATUS_TRANSITIONS[self.status]

        if target_status not in allowed:
            raise ValidationError(
                {
                    "status": (
                        f"Cannot transition from "
                        f"{self.status} to {target_status}."
                    )
                }
            )

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

    def _append_note(self, notes: str):
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
        new_entry = f"[{timestamp}] {notes}"
        self.notes = (
            f"{new_entry}\n---\n{self.notes}" if self.notes else new_entry
        )

    def start(self, notes: str):
        self._validate_not_deleted()
        self._validate_transition(self.WorkOrderStatus.IN_PROGRESS)
        self.status = self.WorkOrderStatus.IN_PROGRESS
        self.completed_date = None
        self._append_note(notes)
        self.save(
            update_fields=["status", "completed_date", "notes", "updated_at"]
        )

    def put_on_hold(self, notes: str):
        self._validate_not_deleted()
        self._validate_transition(self.WorkOrderStatus.ON_HOLD)
        self.status = self.WorkOrderStatus.ON_HOLD
        self.completed_date = None
        self._append_note(notes)
        self.save(
            update_fields=["status", "completed_date", "notes", "updated_at"]
        )

    def complete(self, notes: str, estimated_hours):
        self._validate_not_deleted()
        self._validate_transition(self.WorkOrderStatus.COMPLETED)
        self.status = self.WorkOrderStatus.COMPLETED
        if self.completed_date is None:
            self.completed_date = timezone.now().date()
        self.estimated_hours = estimated_hours
        self._append_note(notes)
        self.save(
            update_fields=[
                "status",
                "completed_date",
                "estimated_hours",
                "notes",
                "updated_at",
            ]
        )

    def cancel(self, notes: str):
        self._validate_not_deleted()
        self._validate_transition(self.WorkOrderStatus.CANCELLED)
        self.status = self.WorkOrderStatus.CANCELLED
        self.completed_date = None
        self._append_note(notes)
        self.save(
            update_fields=["status", "completed_date", "notes", "updated_at"]
        )

    def assign_to(self, user, notes: str):
        self._validate_not_deleted()

        if self.status in (
            self.WorkOrderStatus.COMPLETED,
            self.WorkOrderStatus.CANCELLED,
        ):
            raise ValidationError(
                {
                    "assigned_to": (
                        "Cannot assign users to a "
                        "completed or cancelled work order."
                    )
                }
            )

        if user.tenant_id != self.tenant_id:
            raise ValidationError(
                {
                    "assigned_to": (
                        "Assigned user must belong " "to the same tenant."
                    )
                }
            )

        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M UTC")
        new_entry = f"[{timestamp}] {notes}"
        self.notes = (
            f"{new_entry}\n---\n{self.notes}" if self.notes else new_entry
        )
        self.assigned_to = user
        self.save(update_fields=["assigned_to", "notes", "updated_at"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def is_active(self):
        return not self.is_deleted and self.status in (
            self.WorkOrderStatus.OPEN,
            self.WorkOrderStatus.IN_PROGRESS,
            self.WorkOrderStatus.ON_HOLD,
        )

    @property
    def is_overdue(self):
        if self.due_date is None:
            return False

        if self.status in (
            self.WorkOrderStatus.COMPLETED,
            self.WorkOrderStatus.CANCELLED,
        ):
            return False

        return timezone.now().date() > self.due_date

    def soft_delete(self):
        if self.is_deleted:
            return

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self, notes: str):
        if not self.is_deleted:
            return

        if hasattr(self.asset, "is_deleted") and self.asset.is_deleted:
            raise ValidationError(
                {
                    "asset": (
                        "Cannot restore work order because "
                        "the related asset is deleted."
                    )
                }
            )

        self.deleted_at = None
        self._append_note(notes)

        try:
            with transaction.atomic():
                self.save(update_fields=["deleted_at", "notes", "updated_at"])
        except IntegrityError:
            raise ValidationError(
                {"non_field_errors": ("Cannot restore work order.")}
            )

    def __str__(self):
        return f"{self.title} " f"[{self.get_status_display()}]"
