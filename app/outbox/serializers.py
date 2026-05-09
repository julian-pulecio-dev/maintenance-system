from rest_framework import serializers

from .models import OutboxEvent


class OutboxEventSerializer(serializers.ModelSerializer):

    class Meta:
        model = OutboxEvent
        fields = (
            "id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "payload",
            "status",
            "retry_count",
            "event_version",
            "idempotency_key",
            "source_service",
            "error_message",
            "created_at",
            "processed_at",
            "last_attempted_at",
        )
        read_only_fields = fields
