from notifier_base import EmailNotifierHandler  # noqa: E402 (bundled at deploy time)


def _fmt(value) -> str:
    return value if value is not None else "—"


class WorkOrderDueEmailNotifier(EmailNotifierHandler):

    def get_recipient_email(self, data: dict) -> str | None:
        return (data.get("assigned_to") or {}).get("email")

    def build_subject(self, data: dict, action: str) -> str:
        return f"Work order: {data.get('title')} — {action}"

    def build_body(self, data: dict, action: str) -> str:
        assigned_to = data.get("assigned_to") or {}
        asset = data.get("asset") or {}
        work_order_type = data.get("work_order_type") or {}
        created_by = data.get("created_by") or {}

        priority = _fmt(data.get("priority")).capitalize()
        estimated_hours = data.get("estimated_hours")
        estimated_hours_str = f"{estimated_hours} h" if estimated_hours else "—"

        return (
            f"Hello {assigned_to.get('name', '')},\n\n"
            f"A work order assigned to you is due soon.\n\n"
            f"{'─' * 40}\n"
            f"EVENT\n"
            f"{'─' * 40}\n"
            f"  Action : {action}\n\n"
            f"{'─' * 40}\n"
            f"WORK ORDER\n"
            f"{'─' * 40}\n"
            f"  ID          : {_fmt(data.get('id'))}\n"
            f"  Title       : {_fmt(data.get('title'))}\n"
            f"  Type        : {_fmt(work_order_type.get('name'))}\n"
            f"  Status      : {_fmt(data.get('status'))}\n"
            f"  Priority    : {priority}\n"
            f"  Description : {_fmt(data.get('description'))}\n"
            f"  Notes       : {_fmt(data.get('notes'))}\n\n"
            f"{'─' * 40}\n"
            f"ASSET\n"
            f"{'─' * 40}\n"
            f"  Name          : {_fmt(asset.get('name'))}\n"
            f"  Serial number : {_fmt(asset.get('serial_number'))}\n"
            f"  Status        : {_fmt(asset.get('status'))}\n\n"
            f"{'─' * 40}\n"
            f"SCHEDULE\n"
            f"{'─' * 40}\n"
            f"  Scheduled date   : {_fmt(data.get('scheduled_date'))}\n"
            f"  Due date         : {_fmt(data.get('due_date'))}\n"
            f"  Estimated hours  : {estimated_hours_str}\n\n"
            f"{'─' * 40}\n"
            f"PEOPLE\n"
            f"{'─' * 40}\n"
            f"  Assigned to : {assigned_to.get('name', '—')} <{assigned_to.get('email', '—')}>\n"
            f"  Created by  : {created_by.get('name', '—')} <{created_by.get('email', '—')}>\n\n"
            f"{'─' * 40}\n"
            f"TIMESTAMPS\n"
            f"{'─' * 40}\n"
            f"  Created   : {_fmt(data.get('created_at'))}\n"
            f"  Updated   : {_fmt(data.get('updated_at'))}\n\n"
            f"Please log in to the platform to review the details.\n"
        )


_notifier = WorkOrderDueEmailNotifier()


def handle(event, context):
    return _notifier.handle(event, context)
