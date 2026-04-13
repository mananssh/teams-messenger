from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Validated application configuration loaded from environment / .env file."""

    # Core
    log_level: str = "INFO"

    # Transcription
    whisper_model: str = "base"

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.2

    # Prompt
    prompt_path: str = "prompts/system.txt"

    # Feature flags
    enable_teams: bool = False
    enable_email: bool = False
    enable_jira: bool = False
    enable_github: bool = False

    # Microsoft Teams / Graph API (MSAL Device Code Flow)
    ms_client_id: str = ""
    ms_tenant_id: str = ""
    ms_token_cache_path: str = ".ms_token_cache.json"

    # Email (SMTP — works with Gmail, Outlook, any SMTP provider)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_default_to: str = ""
    notification_from_email: str = "meetingsummarizer@gds.ey.com"

    # Jira
    jira_server_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    # GitHub
    github_token: str = ""
    github_repo: str = ""

    model_config = {
        "env_file": str(ROOT_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
