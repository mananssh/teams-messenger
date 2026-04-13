from __future__ import annotations

from pathlib import Path

import whisper
from loguru import logger

_model_cache: dict[str, whisper.Whisper] = {}


def _get_model(name: str) -> whisper.Whisper:
    if name not in _model_cache:
        logger.info("Loading Whisper model '{}'…", name)
        _model_cache[name] = whisper.load_model(name)
    return _model_cache[name]


def transcribe_audio(
    file_path: str | Path,
    *,
    model_name: str = "base",
) -> str | None:
    """Transcribe an audio file using OpenAI Whisper and return the raw text."""
    try:
        model = _get_model(model_name)
        logger.info("Transcribing '{}'…", Path(file_path).name)
        result = model.transcribe(str(file_path))
        return result["text"]
    except Exception:
        logger.exception("Transcription failed")
        return None
