from __future__ import annotations

from google import genai
from google.genai import types
from loguru import logger

from app.config import Settings
from app.llm.prompt_template import load_system_prompt
from app.models import MeetingAnalysis


def generate_summary(
    transcript: str,
    *,
    participant_registry: dict[str, str],
    meeting_id: str,
    settings: Settings,
) -> MeetingAnalysis | None:
    """Send a transcript to Gemini and return a validated MeetingAnalysis."""
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY is not set — check your .env file")
        return None

    system_prompt = load_system_prompt(settings.prompt_path)
    client = genai.Client(api_key=settings.gemini_api_key)

    user_prompt = (
        f"Meeting ID: {meeting_id}\n\n"
        f"Participant Registry:\n{participant_registry}\n\n"
        f"Transcript:\n{transcript}"
    )

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[system_prompt, user_prompt],
            config=types.GenerateContentConfig(
                temperature=settings.gemini_temperature,
                response_mime_type="application/json",
                response_schema=MeetingAnalysis,
            ),
        )
        logger.debug("Raw LLM output:\n{}", response.text)
        return MeetingAnalysis.model_validate_json(response.text)
    except Exception:
        logger.exception("Gemini API call failed")
        return None
