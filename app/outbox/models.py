import uuid
from django.db import models
from django.db import models
from django.utils import timezone


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    event_type = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Semantic event name, e.g. work_order.created"
    )

    aggregate_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Domain entity type, e.g. work_order"
    )

    aggregate_id = models.UUIDField(
        db_index=True,
        help_text="ID of the related aggregate/entity"
    )

    payload = models.JSONField(
        help_text="Self-contained event payload"
    )

    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    retry_count = models.PositiveIntegerField(
        default=0
    )

    event_version = models.PositiveIntegerField(
        default=1
    )

    error_message = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )

    processed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        db_table = "outbox_events"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="idx_outbox_status_created"
            ),
            models.Index(
                fields=["aggregate_type", "aggregate_id"],
                name="idx_outbox_aggregate"
            ),
        ]

    def mark_processing(self):
        self.status = self.Status.PROCESSING
        self.save(update_fields=["status"])

    def mark_sent(self):
        self.status = self.Status.SENT
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at"])

    def mark_failed(self, error_message: str):
        self.status = self.Status.FAILED
        self.retry_count += 1
        self.error_message = error_message

        self.save(
            update_fields=[
                "status",
                "retry_count",
                "error_message",
            ]
        )

    def __str__(self):
        return f"{self.event_type} ({self.status})"