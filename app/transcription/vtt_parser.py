"""Parse Microsoft Teams VTT (WebVTT) transcript files.

Teams exports transcripts as .vtt with speaker voice tags:

    WEBVTT

    617c22e3-ccc5-445a-b806-be21f6abb3be/0
    00:00:00.000 --> 00:00:05.840
    <v Graham Hosking>We need to discuss the Q4 roadmap.</v>

This module extracts speaker-labelled text and auto-builds
AttendanceRecord objects (Graph-API-compatible) from unique speakers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from app.models import AttendanceRecord, ParticipantIdentity

_VOICE_TAG = re.compile(r"<v\s+([^>]+)>(.*?)</v>", re.DOTALL)
_TIMESTAMP = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}")


@dataclass
class TranscriptResult:
    """Cleaned transcript text + auto-extracted participants."""
    text: str
    participants: list[AttendanceRecord] = field(default_factory=list)


def parse_vtt(file_path: str | Path) -> TranscriptResult | None:
    """Parse a Teams VTT file into clean speaker-labelled text.

    Returns a TranscriptResult with:
      - text: "Ram: Good morning everyone.\\nMeera: I have updates."
      - participants: list of AttendanceRecord (email/id empty — VTT has names only)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error("VTT file not found: {}", file_path)
        return None

    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to read VTT file")
        return None

    seen_speakers: dict[str, int] = {}
    segments: list[tuple[str, str]] = []

    for line in raw.splitlines():
        line = line.strip()

        if not line or line == "WEBVTT" or _TIMESTAMP.match(line):
            continue

        if re.match(r"^[a-f0-9\-]+(/\d+)?$", line) or re.match(r"^\d+$", line):
            continue

        if line.startswith("NOTE"):
            continue

        match = _VOICE_TAG.search(line)
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()

            if speaker not in seen_speakers:
                seen_speakers[speaker] = len(seen_speakers)

            if text:
                segments.append((speaker, text))
        elif segments:
            prev_speaker, prev_text = segments[-1]
            segments[-1] = (prev_speaker, f"{prev_text} {line}")

    if not segments:
        logger.error("No speaker segments found in VTT file")
        return None

    merged: list[tuple[str, str]] = []
    for speaker, text in segments:
        if merged and merged[-1][0] == speaker:
            merged[-1] = (speaker, f"{merged[-1][1]} {text}")
        else:
            merged.append((speaker, text))

    transcript_lines = [f"{speaker}: {text}" for speaker, text in merged]

    participants = [
        AttendanceRecord(
            identity=ParticipantIdentity(displayName=name),
            role="Attendee",
        )
        for name in seen_speakers
    ]

    logger.info(
        "Parsed VTT: {} segments, {} unique speakers",
        len(merged),
        len(participants),
    )

    return TranscriptResult(
        text="\n".join(transcript_lines),
        participants=participants,
    )
