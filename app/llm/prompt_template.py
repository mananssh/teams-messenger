from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.config import ROOT_DIR


def load_system_prompt(prompt_path: str) -> str:
    """Load the system prompt from an external text file.

    Args:
        prompt_path: Path relative to the project root (e.g. "prompts/system.txt").
    """
    full_path = ROOT_DIR / prompt_path

    if not full_path.exists():
        raise FileNotFoundError(
            f"System prompt not found at {full_path}. "
            f"Create the file or set PROMPT_PATH in .env."
        )

    logger.debug("Loaded system prompt from {}", full_path)
    return full_path.read_text(encoding="utf-8").strip()
