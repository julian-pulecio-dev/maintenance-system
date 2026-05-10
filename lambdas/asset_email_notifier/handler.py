from notifier_base import EmailNotifierHandler


class AssetEmailNotifier(EmailNotifierHandler):

    def get_recipient_email(self, data: dict) -> str | None:
        return (data.get("supervisor") or {}).get("email")

    def build_subject(self, data: dict, action: str) -> str:
        return f"Asset update: {data.get('name')} — {action}"

    def build_body(self, data: dict, action: str) -> str:
        asset_type = (data.get("asset_type") or {}).get("name", "—")
        supervisor = data.get("supervisor") or {}
        last_maintenance = data.get("last_maintenance_date") or "—"
        description = data.get("description") or "—"
        serial_number = data.get("serial_number") or "—"

        return (
            f"Hello {supervisor.get('name', '')},\n\n"
            f'The asset "{data.get("name")}" under your supervision has been updated.\n\n'
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


_notifier = AssetEmailNotifier()


def handle(event, context):
    return _notifier.handle(event, context)
