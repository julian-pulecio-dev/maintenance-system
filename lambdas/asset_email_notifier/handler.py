import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        body = body.get("Message", body)  # Handle SNS-wrapped messages
        body = json.loads(body)
        asset_id = body.get("payload", {}).get("asset_id")
        if not asset_id:
            logger.warning("Received event without asset_id in payload: %s", body)
            continue
        logger.info(
            "Received event for asset_id=%s type=%s tenant=%s",
            asset_id,
            body.get("event_type"),
            body.get("tenant_id"),
        )
        # TODO: integrate email service (e.g. SES, SendGrid)
