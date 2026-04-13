"""teams-messenger  —  Meeting audio / Teams transcript → structured actions pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.config import Settings, ROOT_DIR
from app.models import ACTION_LABELS, AttendanceRecord


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format="<level>{level:<8}</level> | <cyan>{name}</cyan> | {message}",
    )


def _generate_meeting_id() -> str:
    return "mtg-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _load_participants(path: str) -> list[AttendanceRecord]:
    p = Path(path)
    if not p.exists():
        logger.error("Participants file not found: {}", p)
        raise SystemExit(1)
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [AttendanceRecord.model_validate(r) for r in raw]


def _print_results(analysis) -> None:
    meta = analysis.meeting_metadata
    print("\n" + "=" * 60)
    print(f"  {meta.title}")
    print("=" * 60)
    print(f"\n{meta.summary}\n")

    if analysis.extracted_actions:
        print("  Extracted actions:")
        for action in analysis.extracted_actions:
            label = ACTION_LABELS.get(action.action_type, action.action_type)
            title = (
                action.payload.issue_summary
                or action.payload.issue_title
                or action.payload.subject
                or action.payload.message_content
                or action.payload.task_summary
            )
            print(f"    [{label}] {title} → {action.assignee_id}")
        print()

    if analysis.participant_notifications:
        print("  Participant notifications:")
        for pn in analysis.participant_notifications:
            print(f"\n    [{pn.id}]")
            for line in pn.teams_notification_markdown.strip().splitlines():
                print(f"    {line}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyse meeting audio or Teams transcripts and dispatch actions.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override LOG_LEVEL from .env",
    )
    parser.add_argument(
        "--meeting-id",
        default=None,
        help="Meeting ID (auto-generated if omitted)",
    )

    sub = parser.add_subparsers(dest="mode", required=True)

    # ── audio subcommand ────────────────────────────────────────
    audio_p = sub.add_parser("audio", help="Transcribe audio with Whisper")
    audio_p.add_argument("file", help="Path to the audio file")
    audio_p.add_argument(
        "--participants",
        required=True,
        help="Path to participants JSON (Graph attendanceRecords format)",
    )

    # ── transcript subcommand ───────────────────────────────────
    transcript_p = sub.add_parser("transcript", help="Parse an MS Teams VTT transcript")
    transcript_p.add_argument("file", help="Path to the .vtt transcript file")
    transcript_p.add_argument(
        "--participants",
        default=None,
        help="Path to participants JSON (Graph attendanceRecords format). "
             "Provides emails/IDs for dispatching. If omitted, speakers are "
             "extracted from VTT tags (display names only, no email).",
    )

    args = parser.parse_args(argv)

    settings = Settings()
    _configure_logging(args.log_level or settings.log_level)
    meeting_id = args.meeting_id or _generate_meeting_id()

    logger.info("teams-messenger pipeline starting (mode: {})", args.mode)
    logger.info(
        "Feature flags — Teams: {} | Email: {} | Jira: {} | GitHub: {}",
        settings.enable_teams,
        settings.enable_email,
        settings.enable_jira,
        settings.enable_github,
    )

    # ── Resolve transcript + participants based on mode ──────────
    if args.mode == "audio":
        from app.transcription.whisper_service import transcribe_audio

        audio_path = Path(args.file)
        if not audio_path.exists():
            logger.error("Audio file not found: {}", audio_path)
            return 1

        logger.info("Transcribing: {}", audio_path.name)
        transcript = transcribe_audio(audio_path, model_name=settings.whisper_model)
        if not transcript:
            logger.error("Transcription produced no output")
            return 1
        logger.success("Transcription complete ({} chars)", len(transcript))

        participants = _load_participants(args.participants)

    elif args.mode == "transcript":
        from app.transcription.vtt_parser import parse_vtt

        vtt_path = Path(args.file)
        result = parse_vtt(vtt_path)
        if result is None:
            logger.error("Failed to parse VTT file")
            return 1

        transcript = result.text

        if args.participants:
            participants = _load_participants(args.participants)
            logger.info("Using participants from JSON ({} records)", len(participants))
        else:
            participants = result.participants
            logger.warning(
                "No --participants file provided — using VTT speaker tags "
                "(display names only, no email/ID for dispatching)",
            )

        logger.success(
            "VTT parsed ({} chars, {} speakers)",
            len(transcript),
            len(result.participants),
        )

    # ── Run the pipeline ─────────────────────────────────────────
    from app.pipeline import run

    analysis = run(
        transcript,
        participants=participants,
        meeting_id=meeting_id,
        settings=settings,
    )
    if analysis is None:
        logger.error("Pipeline failed — see errors above")
        return 1

    _print_results(analysis)
    logger.info("Pipeline completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
