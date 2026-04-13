from __future__ import annotations

from jira import JIRA
from loguru import logger

from app.config import Settings
from app.models import AttendanceRecord, ExtractedAction

PRIORITY_MAP: dict[str, str] = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}


def _resolve_assignee(client: JIRA, participant: AttendanceRecord | None) -> str | None:
    """Try to resolve a Jira accountId from the participant's email."""
    if not participant or not participant.emailAddress:
        return None
    try:
        users = client.search_users(query=participant.emailAddress, maxResults=1)
        if users:
            return users[0].accountId
    except Exception as exc:
        logger.debug("Could not resolve Jira user for {}: {}", participant.emailAddress, exc)
    return None


def create_jira_ticket(
    action: ExtractedAction,
    *,
    participant: AttendanceRecord | None,
    settings: Settings,
) -> bool:
    """Create a Jira issue for a create_jira_ticket action."""
    if not settings.jira_server_url or not settings.jira_api_token:
        logger.warning("Jira not configured — skipping {}", action.action_id)
        return False

    try:
        client = JIRA(
            server=settings.jira_server_url,
            basic_auth=(settings.jira_username, settings.jira_api_token),
        )

        priority_raw = (action.payload.suggested_priority or "medium").lower()
        priority_name = PRIORITY_MAP.get(priority_raw, "Medium")

        fields: dict = {
            "project": {"key": settings.jira_project_key},
            "summary": action.payload.issue_summary,
            "description": action.payload.issue_description,
            "issuetype": {"name": "Task"},
            "priority": {"name": priority_name},
        }

        assignee_id = _resolve_assignee(client, participant)
        if assignee_id:
            fields["assignee"] = {"accountId": assignee_id}

        issue = client.create_issue(fields=fields)
        logger.success(
            "[Jira] Created {} — '{}' (priority: {}, assignee: {})",
            issue.key,
            action.payload.issue_summary,
            priority_name,
            participant.emailAddress if participant else "unassigned",
        )
        return True
    except Exception as exc:
        logger.error("[Jira] Failed to create issue for {}: {}", action.action_id, exc)
        return False
