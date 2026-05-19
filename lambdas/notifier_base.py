import abc
import json
import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class EmailNotifierHandler(abc.ABC):

    _sqs_client = None
    _ses_client = None
    _dynamodb_client = None

    @classmethod
    def _get_sqs_client(cls):
        if cls._sqs_client is None:
            cls._sqs_client = boto3.client("sqs")
        return cls._sqs_client

    @classmethod
    def _get_ses_client(cls):
        if cls._ses_client is None:
            cls._ses_client = boto3.client("ses")
        return cls._ses_client

    @classmethod
    def _get_dynamodb_client(cls):
        if cls._dynamodb_client is None:
            cls._dynamodb_client = boto3.client("dynamodb")
        return cls._dynamodb_client

    def _mark_processed(self, idempotency_key: str) -> bool:

        ttl = int(time.time()) + 30 * 24 * 60 * 60

        try:

            self._get_dynamodb_client().put_item(
                TableName=os.environ["IDEMPOTENCY_TABLE_NAME"],
                Item={
                    "idempotency_key": {"S": idempotency_key},
                    "expires_at": {"N": str(ttl)},
                },
                ConditionExpression=(
                    "attribute_not_exists(idempotency_key)"
                ),
            )

            return True

        except ClientError as exc:

            if (
                exc.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                return False

            raise

    def _delete_idempotency_key(
        self,
        idempotency_key: str,
    ):

        try:

            self._get_dynamodb_client().delete_item(
                TableName=os.environ["IDEMPOTENCY_TABLE_NAME"],
                Key={
                    "idempotency_key": {
                        "S": idempotency_key
                    }
                },
            )

            logger.warning(
                "Released idempotency key=%s",
                idempotency_key,
            )

        except Exception:

            logger.exception(
                "Failed deleting idempotency key=%s",
                idempotency_key,
            )

    def _send_result(
        self,
        event_id: str,
        *,
        status: str,
        error: str = None,
    ):

        queue_url = os.environ["SQS_RESULTS_URL"]

        message = {
            "event_id": event_id,
            "status": status,
        }

        if error:
            message["error"] = error

        self._get_sqs_client().send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
        )

    def _send_email(
        self,
        *,
        to: str,
        data: dict,
        event_type: str,
    ):

        action = (
            event_type
            .split(".")[-1]
            .replace("_", " ")
            .capitalize()
        )

        self._get_ses_client().send_email(
            Source=os.environ["SES_FROM_EMAIL"],
            Destination={
                "ToAddresses": [to]
            },
            Message={
                "Subject": {
                    "Data": self.build_subject(
                        data,
                        action,
                    )
                },
                "Body": {
                    "Text": {
                        "Data": self.build_body(
                            data,
                            action,
                        )
                    }
                },
            },
        )

    @abc.abstractmethod
    def get_recipient_email(
        self,
        data: dict,
    ) -> str | None:
        pass

    @abc.abstractmethod
    def build_subject(
        self,
        data: dict,
        action: str,
    ) -> str:
        pass

    @abc.abstractmethod
    def build_body(
        self,
        data: dict,
        action: str,
    ) -> str:
        pass

    def handle(self, event, context):

        for record in event["Records"]:

            event_id = None
            idempotency_key = None

            try:

                body = json.loads(record["body"])

                message = body.get("Message")

                if message:
                    body = json.loads(message)

                event_id = body.get("id")

                idempotency_key = (
                    body.get("idempotency_key")
                    or event_id
                )

                event_type = body.get(
                    "event_type",
                    "",
                )

                data = (
                    body.get("payload", {})
                    .get("data", {})
                )

                logger.info(
                    (
                        "Processing event "
                        "id=%s type=%s "
                        "tenant=%s record_id=%s"
                    ),
                    event_id,
                    event_type,
                    body.get("tenant_id"),
                    data.get("id"),
                )

                #
                # CLAIM IDEMPOTENCY FIRST
                #

                if not self._mark_processed(
                    idempotency_key
                ):

                    logger.info(
                        (
                            "Duplicate event skipped "
                            "idempotency_key=%s "
                            "event_id=%s"
                        ),
                        idempotency_key,
                        event_id,
                    )

                    continue

                recipient = self.get_recipient_email(
                    data
                )

                if not recipient:

                    logger.warning(
                        (
                            "No recipient email "
                            "in event_id=%s"
                        ),
                        event_id,
                    )

                else:

                    self._send_email(
                        to=recipient,
                        data=data,
                        event_type=event_type,
                    )

                    logger.info(
                        (
                            "Email sent to=%s "
                            "event_id=%s"
                        ),
                        recipient,
                        event_id,
                    )

                if event_id:

                    self._send_result(
                        event_id,
                        status="processed",
                    )

                    logger.info(
                        (
                            "Result sent: "
                            "event_id=%s "
                            "status=processed"
                        ),
                        event_id,
                    )

            except Exception as exc:

                logger.error(
                    (
                        "Failed to process "
                        "record event_id=%s: %s"
                    ),
                    event_id,
                    exc,
                    exc_info=True,
                )

                #
                # IMPORTANT:
                # release idempotency lock
                # so retries can happen
                #

                if idempotency_key:

                    self._delete_idempotency_key(
                        idempotency_key
                    )

                if event_id:

                    self._send_result(
                        event_id,
                        status="failed",
                        error=str(exc),
                    )

                    logger.info(
                        (
                            "Result sent: "
                            "event_id=%s "
                            "status=failed"
                        ),
                        event_id,
                    )