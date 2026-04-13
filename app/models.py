from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ── Graph-API-compatible participant models ──────────────────

class ParticipantIdentity(BaseModel):
    """Mirrors microsoft.graph.identity."""
    id: str = ""
    displayName: str = ""


class AttendanceRecord(BaseModel):
    """Mirrors microsoft.graph.attendanceRecord (subset).

    Compatible with the JSON returned by:
      GET /users/{userId}/onlineMeetings/{meetingId}/attendanceReports/{reportId}/attendanceRecords
    """
    emailAddress: str = ""
    identity: ParticipantIdentity
    role: str = "Attendee"
    totalAttendanceInSeconds: int = 0


def build_registry(participants: list[AttendanceRecord]) -> dict[str, str]:
    """Convert a list of AttendanceRecords into a {pid: displayName} registry for the LLM."""
    return {f"p{i + 1}": p.identity.displayName for i, p in enumerate(participants)}


def lookup_participant(
    assignee_id: str,
    participants: list[AttendanceRecord],
) -> AttendanceRecord | None:
    """Resolve an LLM-assigned ID (e.g. 'p1') back to the full AttendanceRecord."""
    idx_str = assignee_id.removeprefix("p")
    try:
        idx = int(idx_str) - 1
        if 0 <= idx < len(participants):
            return participants[idx]
    except ValueError:
        pass
    return None


# ── Action type definitions ──────────────────────────────────

ACTION_TYPES = Literal[
    "create_jira_ticket",
    "create_github_issue",
    "draft_email",
    "ms_teams_ping",
    "manual_review",
]

ACTION_LABELS: dict[str, str] = {
    "create_jira_ticket": "Jira",
    "create_github_issue": "GitHub",
    "draft_email": "Email",
    "ms_teams_ping": "Teams",
    "manual_review": "Review",
}


# ── LLM output schema (Gemini structured output) ────────────

class MeetingMetadata(BaseModel):
    meeting_id: str
    title: str
    summary: str


class ActionPayload(BaseModel):
    """Union of all possible payload fields across action types.

    Each action_type uses a subset — only the keys defined in the
    Action Routing Matrix for that type will be populated:
      create_jira_ticket  -> issue_summary, issue_description, suggested_priority
      create_github_issue -> issue_title, issue_body
      draft_email         -> subject, intended_recipient, draft_body
      ms_teams_ping       -> intended_recipient, message_content
      manual_review       -> task_summary, missing_context
    """
    issue_summary: str = ""
    issue_description: str = ""
    suggested_priority: str = ""
    issue_title: str = ""
    issue_body: str = ""
    subject: str = ""
    intended_recipient: str = ""
    draft_body: str = ""
    message_content: str = ""
    task_summary: str = ""
    missing_context: str = ""


class ExtractedAction(BaseModel):
    action_id: str
    assignee_id: str
    action_type: ACTION_TYPES
    payload: ActionPayload


class ParticipantNotification(BaseModel):
    id: str
    teams_notification_markdown: str


class MeetingAnalysis(BaseModel):
    meeting_metadata: MeetingMetadata
    extracted_actions: list[ExtractedAction] = []
    participant_notifications: list[ParticipantNotification] = []
