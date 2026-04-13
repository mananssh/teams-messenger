from __future__ import annotations

from loguru import logger

from app.auth.graph_auth import get_access_token, get_or_create_1on1_chat, send_chat_message
from app.config import Settings
from app.dispatcher.markdown_utils import markdown_to_html
from app.models import AttendanceRecord, ParticipantNotification


def send_teams_notification(
    notification: ParticipantNotification,
    *,
    participant: AttendanceRecord | None,
    settings: Settings,
) -> bool:
    """Send a participant's personalized notification as a 1:1 Teams chat message."""
    email = participant.emailAddress if participant else None
    name = participant.identity.displayName if participant else notification.id

    if not email:
        logger.warning("[Teams] No email for {} — cannot deliver notification", name)
        return False

    try:
        token = get_access_token(settings)
        chat_id = get_or_create_1on1_chat(token, email)
        html_body = markdown_to_html(notification.teams_notification_markdown)
        send_chat_message(token, chat_id, html_body, content_type="html")
        logger.success("[Teams] Notification sent to {} ({})", name, email)
        return True
    except Exception as exc:
        logger.error("[Teams] Failed to notify {} ({}): {}", name, email, exc)
        return False
