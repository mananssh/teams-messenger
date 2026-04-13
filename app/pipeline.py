from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from app.config import Settings
from app.models import AttendanceRecord, MeetingAnalysis, build_registry
from app.llm.gemini_service import generate_summary
from app.dispatcher.dispatcher import dispatch

EventCallback = Callable[[str, dict[str, Any]], None] | None


def _emit(on_event: EventCallback, event_type: str, data: dict[str, Any]) -> None:
    if on_event is not None:
        on_event(event_type, data)


def run(
    transcript: str,
    *,
    participants: list[AttendanceRecord],
    meeting_id: str,
    settings: Settings,
    on_event: EventCallback = None,
) -> MeetingAnalysis | None:
    """Execute the meeting-analysis pipeline (mode-agnostic).

    Args:
        on_event: Optional callback ``(event_type, data_dict) -> None``
                  used by the web server to stream real-time progress.
                  CLI callers leave this as None.
    """
    registry = build_registry(participants)

    _emit(on_event, "step", {"id": "analyze", "status": "running",
                             "detail": f"Analyzing {len(transcript)} chars with {settings.gemini_model}…"})

    logger.info(
        "Analysing transcript ({} chars, {} participants) via {}",
        len(transcript),
        len(participants),
        settings.gemini_model,
    )
    analysis = generate_summary(
        transcript,
        participant_registry=registry,
        meeting_id=meeting_id,
        settings=settings,
    )
    if analysis is None:
        logger.error("LLM analysis failed")
        _emit(on_event, "step", {"id": "analyze", "status": "error", "detail": "LLM analysis failed"})
        return None

    logger.success(
        "Parsed: {} — '{}' ({} actions)",
        analysis.meeting_metadata.meeting_id,
        analysis.meeting_metadata.title,
        len(analysis.extracted_actions),
    )
    _emit(on_event, "step", {"id": "analyze", "status": "done",
                             "detail": f"{len(analysis.extracted_actions)} actions extracted"})

    _emit(on_event, "step", {"id": "dispatch", "status": "running", "detail": "Dispatching actions…"})
    logger.info("Dispatching actions")
    dispatch(analysis, participants=participants, settings=settings, on_event=on_event)
    _emit(on_event, "step", {"id": "dispatch", "status": "done", "detail": "All dispatches complete"})

    return analysis
