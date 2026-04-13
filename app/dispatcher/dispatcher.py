from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from app.config import Settings
from app.models import (
    ACTION_LABELS,
    AttendanceRecord,
    MeetingAnalysis,
    ExtractedAction,
    lookup_participant,
)
from app.dispatcher.teams_service import send_teams_notification
from app.dispatcher.email_service import send_email, send_notification_email
from app.dispatcher.jira_service import create_jira_ticket
from app.dispatcher.github_service import create_github_issue

EventCallback = Callable[[str, dict[str, Any]], None] | None


def _emit(on_event: EventCallback, event_type: str, data: dict[str, Any]) -> None:
    if on_event is not None:
        on_event(event_type, data)


def _action_title(action: ExtractedAction) -> str:
    return (
        action.payload.issue_summary
        or action.payload.issue_title
        or action.payload.subject
        or action.payload.message_content
        or action.payload.task_summary
    )


def dispatch(
    analysis: MeetingAnalysis,
    *,
    participants: list[AttendanceRecord],
    settings: Settings,
    on_event: EventCallback = None,
) -> None:
    """Route extracted actions to integrations and send participant notifications."""
    if analysis.extracted_actions:
        for action in analysis.extracted_actions:
            participant = lookup_participant(action.assignee_id, participants)
            ok = _route_action(action, participant=participant, settings=settings)
            label = ACTION_LABELS.get(action.action_type, action.action_type)
            name = participant.identity.displayName if participant else action.assignee_id
            _emit(on_event, "dispatch", {
                "action_id": action.action_id,
                "type": action.action_type,
                "label": label,
                "title": _action_title(action),
                "assignee": name,
                "status": "success" if ok else ("skipped" if ok is None else "error"),
            })
    else:
        logger.info("No extracted actions to dispatch")

    if analysis.participant_notifications:
        meeting_title = analysis.meeting_metadata.title
        for notification in analysis.participant_notifications:
            participant = lookup_participant(notification.id, participants)
            name = participant.identity.displayName if participant else notification.id

            if settings.enable_teams:
                tok = send_teams_notification(notification, participant=participant, settings=settings)
                _emit(on_event, "dispatch", {
                    "action_id": f"teams-{notification.id}",
                    "type": "notification_teams",
                    "label": "Teams",
                    "title": f"Notification to {name}",
                    "assignee": name,
                    "status": "success" if tok else "error",
                })

            if settings.enable_email:
                eok = send_notification_email(
                    notification,
                    meeting_title=meeting_title,
                    participant=participant,
                    settings=settings,
                )
                _emit(on_event, "dispatch", {
                    "action_id": f"email-{notification.id}",
                    "type": "notification_email",
                    "label": "Email",
                    "title": f"Summary to {name}",
                    "assignee": name,
                    "status": "success" if eok else "error",
                })


def _route_action(
    action: ExtractedAction,
    *,
    participant: AttendanceRecord | None,
    settings: Settings,
) -> bool | None:
    """Route a single action. Returns True=success, False=error, None=skipped."""
    name = participant.identity.displayName if participant else action.assignee_id
    logger.info("Action {} → {} (assignee: {})", action.action_id, action.action_type, name)

    match action.action_type:
        case "create_jira_ticket":
            if settings.enable_jira:
                return create_jira_ticket(action, participant=participant, settings=settings)
            logger.debug("Jira disabled — skipping {}", action.action_id)
            return None

        case "create_github_issue":
            if settings.enable_github:
                return create_github_issue(action, settings=settings)
            logger.debug("GitHub disabled — skipping {}", action.action_id)
            return None

        case "draft_email":
            if settings.enable_email:
                return send_email(action, participant=participant, settings=settings)
            logger.debug("Email disabled — skipping {}", action.action_id)
            return None

        case "ms_teams_ping":
            logger.info(
                "[Draft] Teams ping for {} → included in their notification",
                name,
            )
            return True

        case "manual_review":
            logger.warning(
                "Manual review required for {}: {}",
                action.action_id,
                action.payload.missing_context or action.payload.task_summary,
            )
            return True
