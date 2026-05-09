import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        logger.info(
            "Sending Slack notification for event id=%s type=%s tenant=%s",
            body.get("id"),
            body.get("event_type"),
            body.get("tenant_id"),
        )
        # TODO: integrate Slack Incoming Webhooks or Bolt SDK
