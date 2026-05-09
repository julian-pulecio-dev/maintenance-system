import json
import logging
import os
import time
from datetime import timedelta
from threading import Thread, Event

import boto3
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from outbox.models import OutboxEvent

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
STUCK_THRESHOLD_MINUTES = 10
POLL_INTERVAL_SECONDS = 60
RESULTS_INTERVAL_SECONDS = 10
RESULTS_BATCH_SIZE = 10

_sns_client = None
_sqs_client = None


def _get_sns_client():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns")
    return _sns_client


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def recover_stuck_records():
    stuck_cutoff = timezone.now() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
    stuck = OutboxEvent.objects.processing().filter(last_attempted_at__lt=stuck_cutoff)
    count = 0
    for event in stuck:
        event.mark_failed(f"Recovered: stuck in PROCESSING for over {STUCK_THRESHOLD_MINUTES} minutes")
        count += 1
    if count:
        logger.warning("Recovered %d stuck PROCESSING events", count)


def _publish(event: OutboxEvent):
    topic_arn = os.environ["SNS_TOPIC_ARN"]

    body = json.dumps({
        "id": str(event.id),
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": str(event.aggregate_id),
        "tenant_id": str(event.tenant_id),
        "payload": event.payload,
        "event_version": event.event_version,
        "source_service": event.source_service,
        "idempotency_key": event.idempotency_key,
        "created_at": event.created_at.isoformat(),
    })

    _get_sns_client().publish(
        TopicArn=topic_arn,
        Message=body,
        MessageAttributes={
            "event_type": {
                "DataType": "String",
                "StringValue": event.event_type,
            },
            "tenant_id": {
                "DataType": "String",
                "StringValue": str(event.tenant_id),
            },
        },
    )

    logger.info(
        "event published id=%s type=%s aggregate=%s/%s tenant=%s",
        event.id,
        event.event_type,
        event.aggregate_type,
        event.aggregate_id,
        event.tenant_id,
    )


def poll_and_publish():
    with transaction.atomic():
        events = list(
            OutboxEvent.objects
            .pending()
            .select_for_update(skip_locked=True)[:BATCH_SIZE]
        )
        for event in events:
            event.mark_processing()

    logger.info("Poll cycle: found %d pending event(s)", len(events))

    published = failed = 0
    for event in events:
        try:
            _publish(event)
            event.mark_sent()
            published += 1
        except Exception as exc:
            event.mark_failed(str(exc))
            failed += 1
            logger.error("Failed to publish event %s: %s", event.id, exc)

    if published or failed:
        logger.info("Poll cycle complete: published=%d failed=%d", published, failed)


def process_results():
    queue_url = os.environ["SQS_RESULTS_URL"]
    sqs = _get_sqs_client()

    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=RESULTS_BATCH_SIZE,
        WaitTimeSeconds=5,
    )

    messages = response.get("Messages", [])
    if not messages:
        return

    for message in messages:
        try:
            body = json.loads(message["Body"])
            event_id = body["event_id"]
            status = body["status"]
            error = body.get("error")

            event = OutboxEvent.objects.get(id=event_id)

            if status == "processed":
                event.mark_sent()
            else:
                event.mark_failed(error or "Unknown error reported by worker")

        except OutboxEvent.DoesNotExist:
            logger.error("Result for unknown event_id=%s", body.get("event_id"))

        except Exception as exc:
            logger.error("Failed to process result for message=%s: %s", message["MessageId"], exc)
            continue

        try:
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )
            logger.info("Result processed event_id=%s status=%s", event_id, status)
        except Exception as exc:
            logger.error("Failed to delete message=%s: %s", message["MessageId"], exc)


class Command(BaseCommand):
    help = "Polls the outbox table, publishes pending events, and processes worker results"

    def handle(self, *args, **_):
        self.stdout.write("Outbox worker started")
        stop_event = Event()

        poller_thread = Thread(target=self._run_poller, args=(stop_event,), daemon=True)
        results_thread = Thread(target=self._run_results_reader, args=(stop_event,), daemon=True)

        poller_thread.start()
        results_thread.start()

        try:
            stop_event.wait()
        except KeyboardInterrupt:
            self.stdout.write("Shutting down...")
            stop_event.set()

    def _run_poller(self, stop_event: Event):
        while not stop_event.is_set():
            try:
                recover_stuck_records()
                poll_and_publish()
            except Exception as exc:
                logger.exception("Unhandled error in poll cycle: %s", exc)
            stop_event.wait(timeout=POLL_INTERVAL_SECONDS)

    def _run_results_reader(self, stop_event: Event):
        while not stop_event.is_set():
            try:
                process_results()
            except Exception as exc:
                logger.exception("Unhandled error in results cycle: %s", exc)
            stop_event.wait(timeout=RESULTS_INTERVAL_SECONDS)