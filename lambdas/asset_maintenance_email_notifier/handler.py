import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_sqs_client = None
_ses_client = None
_dynamodb_client = None


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def _get_ses_client():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses")
    return _ses_client


def _get_dynamodb_client():
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def _mark_processed(idempotency_key: str) -> bool:
    """Atomically claims the key. Returns True if first time, False if duplicate."""
    ttl = int(time.time()) + 30 * 24 * 60 * 60  # 30 days
    try:
        _get_dynamodb_client().put_item(
            TableName=os.environ["IDEMPOTENCY_TABLE_NAME"],
            Item={
                "idempotency_key": {"S": idempotency_key},
                "expires_at": {"N": str(ttl)},
            },
            ConditionExpression="attribute_not_exists(idempotency_key)",
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _send_result(event_id: str, *, status: str, error: str = None):
    queue_url = os.environ["SQS_RESULTS_URL"]
    message = {"event_id": event_id, "status": status}
    if error:
        message["error"] = error
    _get_sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),
    )


def _build_email_body(data: dict, action: str) -> str:
    asset_type = (data.get("asset_type") or {}).get("name", "—")
    supervisor = data.get("supervisor") or {}
    last_maintenance = data.get("last_maintenance_date") or "—"
    description = data.get("description") or "—"
    serial_number = data.get("serial_number") or "—"

    return (
        f"Hello {supervisor.get('name', '')},\n\n"
        f'The asset "{data.get("name")}" maintenance date is approaching.\n\n'
        f"{'─' * 40}\n"
        f"EVENT\n"
        f"{'─' * 40}\n"
        f"  Action : {action}\n\n"
        f"{'─' * 40}\n"
        f"ASSET DETAILS\n"
        f"{'─' * 40}\n"
        f"  ID              : {data.get('id')}\n"
        f"  Name            : {data.get('name')}\n"
        f"  Serial number   : {serial_number}\n"
        f"  Type            : {asset_type}\n"
        f"  Status          : {data.get('status')}\n"
        f"  Location        : {data.get('location')}\n"
        f"  Description     : {description}\n\n"
        f"{'─' * 40}\n"
        f"MAINTENANCE\n"
        f"{'─' * 40}\n"
        f"  Installation date     : {data.get('installation_date')}\n"
        f"  Last maintenance      : {last_maintenance}\n"
        f"  Maintenance interval  : {data.get('recommended_maintenance_interval_days')} days\n\n"
        f"{'─' * 40}\n"
        f"TIMESTAMPS\n"
        f"{'─' * 40}\n"
        f"  Created   : {data.get('created_at')}\n"
        f"  Updated   : {data.get('updated_at')}\n\n"
        f"Please log in to the platform to review the details.\n"
    )


def _send_email(*, to: str, data: dict, event_type: str):
    from_email = os.environ["SES_FROM_EMAIL"]
    action = event_type.split(".")[-1].replace("_", " ").capitalize()

    _get_ses_client().send_email(
        Source=from_email,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {
                "Data": f"Asset maintenance: {data.get('name')} — {action}",
            },
            "Body": {
                "Text": {
                    "Data": _build_email_body(data, action),
                },
            },
        },
    )


def handle(event, context):
    for record in event["Records"]:
        event_id = None
        try:
            body = json.loads(record["body"])
            message = body.get("Message")
            if message:
                body = json.loads(message)

            event_id = body.get("id")
            idempotency_key = body.get("idempotency_key") or event_id
            event_type = body.get("event_type", "")
            data = body.get("payload", {}).get("data", {})

            logger.info(
                "Processing event id=%s type=%s tenant=%s asset_id=%s",
                event_id,
                event_type,
                body.get("tenant_id"),
                data.get("id"),
            )

            if not _mark_processed(idempotency_key):
                logger.info(
                    "Duplicate event skipped idempotency_key=%s event_id=%s",
                    idempotency_key,
                    event_id,
                )
                if event_id:
                    _send_result(event_id, status="processed")
                continue

            supervisor_email = (data.get("supervisor") or {}).get("email")

            if not supervisor_email:
                logger.warning(
                    "No supervisor email in event_id=%s, skipping email.",
                    event_id,
                )
            else:
                _send_email(to=supervisor_email, data=data, event_type=event_type)
                logger.info(
                    "Email sent to=%s event_id=%s", supervisor_email, event_id
                )

            if event_id:
                _send_result(event_id, status="processed")
                logger.info("Result sent: event_id=%s status=processed", event_id)

        except Exception as exc:
            logger.error(
                "Failed to process record event_id=%s: %s",
                event_id,
                exc,
                exc_info=True,
            )
            if event_id:
                _send_result(event_id, status="failed", error=str(exc))
                logger.info("Result sent: event_id=%s status=failed", event_id)
