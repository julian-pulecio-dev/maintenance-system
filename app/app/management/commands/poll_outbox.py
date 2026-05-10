import json
import logging
import os
from datetime import timedelta
from threading import Event, Thread

import boto3
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from outbox.models import OutboxEvent

logger = logging.getLogger(__name__)

BATCH_SIZE = 100

POLL_INTERVAL_SECONDS = 60
RESULTS_INTERVAL_SECONDS = 10

RESULTS_BATCH_SIZE = 10

STUCK_THRESHOLD_MINUTES = 10

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


def _recover_stuck_processing_events():

    stuck_cutoff = (
        timezone.now()
        - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
    )

    recovered = (
        OutboxEvent.objects.processing()
        .filter(last_attempted_at__lt=stuck_cutoff)
        .update(
            status=OutboxEvent.Status.PENDING,
            last_attempted_at=timezone.now(),
            error_message=(
                "Recovered stuck PROCESSING event"
            ),
        )
    )

    if recovered:
        logger.warning(
            (
                "Recovered %d stuck PROCESSING "
                "events"
            ),
            recovered,
        )


def _claim_pending_events():

    with transaction.atomic():

        events = list(
            OutboxEvent.objects.pending()
            .select_for_update(skip_locked=True)
            .order_by("created_at")[:BATCH_SIZE]
        )

        if not events:
            return []

        event_ids = [event.id for event in events]

        OutboxEvent.objects.filter(
            id__in=event_ids
        ).update(
            status=OutboxEvent.Status.PROCESSING,
            last_attempted_at=timezone.now(),
        )

    logger.info(
        "Claimed %d outbox event(s)",
        len(events),
    )

    return events


def _publish(event: OutboxEvent):

    topic_arn = os.environ["SNS_TOPIC_ARN"]

    body = json.dumps(
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": str(event.aggregate_id),
            "tenant_id": str(event.tenant_id),
            "payload": event.payload,
            "event_version": event.event_version,
            "source_service": event.source_service,
            "idempotency_key": (
                event.idempotency_key
            ),
            "created_at": (
                event.created_at.isoformat()
            ),
        }
    )

    _get_sns_client().publish(
        TopicArn=topic_arn,
        Message=body,
        MessageAttributes={
            "event_type": {
                "DataType": "String",
                "StringValue": (
                    event.event_type
                ),
            },
            "tenant_id": {
                "DataType": "String",
                "StringValue": str(
                    event.tenant_id
                ),
            },
        },
    )

    logger.info(
        (
            "Outbox event dispatched "
            "id=%s type=%s"
        ),
        event.id,
        event.event_type,
    )


def _dispatch_pending_events():

    events = _claim_pending_events()

    if not events:
        return

    dispatched = 0
    failed = 0

    for event in events:

        try:

            _publish(event)

            dispatched += 1

        except Exception as exc:

            failed += 1

            event.mark_failed(str(exc))

            logger.exception(
                (
                    "Failed to dispatch "
                    "event_id=%s"
                ),
                event.id,
            )

    logger.info(
        (
            "Dispatch cycle complete "
            "dispatched=%d failed=%d"
        ),
        dispatched,
        failed,
    )


def _process_results():

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

    processed = 0
    failed = 0

    for message in messages:

        try:

            body = json.loads(message["Body"])

            event_id = body["event_id"]

            status = body["status"]

            error = body.get("error")

            try:

                event = (
                    OutboxEvent.objects
                    .select_for_update()
                    .get(id=event_id)
                )

            except OutboxEvent.DoesNotExist:

                logger.error(
                    (
                        "Received result for "
                        "unknown event_id=%s"
                    ),
                    event_id,
                )

                continue

            if (
                event.status
                != OutboxEvent.Status.PROCESSING
            ):

                logger.warning(
                    (
                        "Ignoring invalid "
                        "result transition "
                        "event_id=%s status=%s"
                    ),
                    event.id,
                    event.status,
                )

                continue

            if status == "processed":

                event.mark_sent()

                processed += 1

            else:

                event.mark_failed(
                    error
                    or (
                        "Unknown downstream "
                        "processing error"
                    )
                )

                failed += 1

            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message[
                    "ReceiptHandle"
                ],
            )

            logger.info(
                (
                    "Processed result "
                    "event_id=%s status=%s"
                ),
                event.id,
                status,
            )

        except Exception:

            logger.exception(
                (
                    "Failed to process "
                    "results message_id=%s"
                ),
                message.get("MessageId"),
            )

    logger.info(
        (
            "Results cycle complete "
            "processed=%d failed=%d"
        ),
        processed,
        failed,
    )


class Command(BaseCommand):

    help = (
        "Dispatches outbox events to SNS and "
        "marks them SENT only after "
        "successful downstream processing."
    )

    def handle(self, *args, **kwargs):

        self.stdout.write(
            "Starting outbox dispatcher..."
        )

        stop_event = Event()

        dispatcher_thread = Thread(
            target=self._run_dispatcher,
            args=(stop_event,),
            daemon=True,
        )

        results_thread = Thread(
            target=self._run_results_processor,
            args=(stop_event,),
            daemon=True,
        )

        dispatcher_thread.start()

        results_thread.start()

        try:

            stop_event.wait()

        except KeyboardInterrupt:

            self.stdout.write(
                "Shutting down..."
            )

            stop_event.set()

    def _run_dispatcher(
        self,
        stop_event: Event,
    ):

        while not stop_event.is_set():

            try:

                _recover_stuck_processing_events()

                _dispatch_pending_events()

            except Exception:

                logger.exception(
                    "Unhandled dispatcher error"
                )

            stop_event.wait(
                timeout=POLL_INTERVAL_SECONDS
            )

    def _run_results_processor(
        self,
        stop_event: Event,
    ):

        while not stop_event.is_set():

            try:

                _process_results()

            except Exception:

                logger.exception(
                    "Unhandled results error"
                )

            stop_event.wait(
                timeout=RESULTS_INTERVAL_SECONDS
            )