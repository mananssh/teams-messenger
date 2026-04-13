from __future__ import annotations

import json
import re

from loguru import logger

from app.models import MeetingAnalysis


def parse_llm_output(text: str) -> MeetingAnalysis | None:
    """Parse raw LLM text into a validated MeetingAnalysis.

    With structured output enabled the response should already be clean JSON,
    but we keep lightweight fallbacks for resilience.
    """
    candidates: list[str] = [text]

    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))

    braces = re.search(r"\{.*\}", text, re.DOTALL)
    if braces:
        candidates.append(braces.group(0))

    for candidate in candidates:
        try:
            return MeetingAnalysis.model_validate(json.loads(candidate))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    logger.error("Could not extract valid MeetingAnalysis from LLM output")
    return None
