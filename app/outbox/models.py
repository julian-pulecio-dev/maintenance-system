# outbox/models.py

import uuid
from venv import logger

from django.db import models
from django.utils import timezone
from tenant.models import Tenant


class OutboxEventQuerySet(models.QuerySet):

    def pending(self):
        return self.filter(status=OutboxEvent.Status.PENDING)

    def dispatchable(self, retry_cutoff=None):
        failed_q = models.Q(
            status=OutboxEvent.Status.FAILED,
            retry_count__lt=OutboxEvent.MAX_RETRIES,
        )
        if retry_cutoff is not None:
            failed_q &= models.Q(last_attempted_at__lt=retry_cutoff)
        return self.filter(
            models.Q(status=OutboxEvent.Status.PENDING) | failed_q
        )

    def processing(self):
        return self.filter(status=OutboxEvent.Status.PROCESSING)

    def failed(self):
        return self.filter(status=OutboxEvent.Status.FAILED)

    def sent(self):
        return self.filter(status=OutboxEvent.Status.SENT)

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)

    def for_aggregate(self, aggregate_type: str, aggregate_id, tenant):
        """
        Filter by aggregate type and ID.
        """
        qs = self.filter(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            tenant=tenant,
        )
        return qs


class OutboxEvent(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    MAX_RETRIES = 3
    MAX_ERROR_MESSAGE_LENGTH = 5000

    objects = OutboxEventQuerySet.as_manager()

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="outbox_events",
        db_index=False,  # covered by composite indexes
        help_text="Tenant owner of this event",
    )

    event_type = models.CharField(
        max_length=255,
        help_text="Semantic event name, e.g. work_order.created",
    )

    aggregate_type = models.CharField(
        max_length=100,
        help_text="Domain entity type, e.g. work_order",
    )

    aggregate_id = models.UUIDField(
        help_text="ID of the related aggregate/entity",
    )

    payload = models.JSONField(
        help_text="Self-contained immutable event payload",
    )

    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
    )

    retry_count = models.PositiveIntegerField(
        default=0,
    )

    event_version = models.PositiveIntegerField(
        default=1,
        help_text="Schema/event contract version",
    )

    idempotency_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=(
            "Optional deduplication key for consumers. "
            "Unique per tenant when provided."
        ),
    )

    source_service = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Origin service or bounded context",
    )

    error_message = models.TextField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_attempted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "outbox_events"

        # FIFO: worker always picks the oldest pending events first
        ordering = ["created_at"]

        indexes = [
            # Main worker polling index
            models.Index(
                fields=["tenant_id", "status", "created_at"],
                name="idx_outbox_status_created",
            ),
            # Aggregate traceability
            models.Index(
                fields=["tenant_id", "aggregate_type", "aggregate_id"],
                name="idx_outbox_tenant_aggregate",
            ),
            # Event type filtering / replay / analytics
            models.Index(
                fields=["tenant_id", "event_type"],
                name="idx_outbox_tenant_event_type",
            ),
            # Idempotency key lookup
            models.Index(
                fields=["tenant_id", "idempotency_key"],
                name="idx_outbox_idempotency_key",
            ),
        ]

        constraints = [
            # Enforce uniqueness of idempotency_key per tenant when provided
            models.UniqueConstraint(
                fields=["tenant_id", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="uq_outbox_tenant_idempotency_key",
            ),
        ]

    def mark_processing(self):
        self.status = self.Status.PROCESSING
        self.last_attempted_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "last_attempted_at",
            ]
        )

    def mark_sent(self):
        logger.error(
            "MARK_SENT CALLED event_id=%s retry_count=%s current_status=%s",
            self.id,
            self.retry_count,
            self.status,
        )

        now = timezone.now()

        self.status = self.Status.SENT
        self.processed_at = now
        self.last_attempted_at = now

        self.save(
            update_fields=[
                "status",
                "processed_at",
                "last_attempted_at",
            ]
        )

    def mark_failed(self, error_message: str):
        self.retry_count += 1

        self.error_message = (
            error_message[: self.MAX_ERROR_MESSAGE_LENGTH]
            if error_message
            else None
        )

        self.last_attempted_at = timezone.now()

        self.status = self.Status.FAILED

        self.save(
            update_fields=[
                "status",
                "retry_count",
                "error_message",
                "last_attempted_at",
            ]
        )

    @property
    def is_retryable(self) -> bool:
        """
        True only for events that are eligible to be requeued.
        PROCESSING is excluded — the worker must release it first.
        """
        return (
            self.status in (self.Status.PENDING, self.Status.FAILED)
            and self.retry_count < self.MAX_RETRIES
        )

    def __str__(self):
        return f"[{self.tenant_id}] " f"{self.event_type} " f"({self.status})"
