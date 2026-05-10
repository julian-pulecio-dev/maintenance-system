from notifier_base import EmailNotifierHandler  # noqa: E402 (bundled at deploy time)


def _fmt(value) -> str:
    return str(value) if value is not None else "—"


class AssetSensorAlertNotifier(EmailNotifierHandler):

    def get_recipient_email(self, data: dict) -> str | None:
        return (data.get("supervisor") or {}).get("email")

    def build_subject(self, data: dict, action: str) -> str:
        alert = data.get("alert") or {}
        severity = (alert.get("severity") or "warning").upper()
        return f"[{severity}] Alert: something is wrong with {data.get('name')}"

    def build_body(self, data: dict, action: str) -> str:
        supervisor = data.get("supervisor") or {}
        asset_type = (data.get("asset_type") or {}).get("name", "—")
        alert = data.get("alert") or {}
        message = alert.get("message") or "No additional details provided."
        severity = (alert.get("severity") or "warning").capitalize()

        return (
            f"Hello {supervisor.get('name', '')},\n\n"
            f'An alert has been raised for asset "{data.get("name")}".\n\n'
            f"{'─' * 40}\n"
            f"ALERT\n"
            f"{'─' * 40}\n"
            f"  Severity : {severity}\n"
            f"  Message  : {message}\n\n"
            f"{'─' * 40}\n"
            f"ASSET\n"
            f"{'─' * 40}\n"
            f"  ID            : {_fmt(data.get('id'))}\n"
            f"  Name          : {_fmt(data.get('name'))}\n"
            f"  Serial number : {_fmt(data.get('serial_number'))}\n"
            f"  Type          : {asset_type}\n"
            f"  Status        : {_fmt(data.get('status'))}\n"
            f"  Location      : {_fmt(data.get('location'))}\n\n"
            f"{'─' * 40}\n"
            f"SUPERVISOR\n"
            f"{'─' * 40}\n"
            f"  Name  : {supervisor.get('name', '—')}\n"
            f"  Email : {supervisor.get('email', '—')}\n\n"
            f"Please log in to the platform to review the details.\n"
        )


_notifier = AssetSensorAlertNotifier()


def handle(event, context):
    return _notifier.handle(event, context)
