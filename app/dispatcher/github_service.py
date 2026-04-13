from __future__ import annotations

import httpx
from loguru import logger

from app.config import Settings
from app.models import ExtractedAction

GITHUB_API = "https://api.github.com"


def create_github_issue(action: ExtractedAction, *, settings: Settings) -> bool:
    """Create a GitHub issue for a create_github_issue action."""
    if not settings.github_token or not settings.github_repo:
        logger.warning("GitHub not configured — skipping {}", action.action_id)
        return False

    owner_repo = settings.github_repo  # expected format: "owner/repo"
    url = f"{GITHUB_API}/repos/{owner_repo}/issues"

    try:
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "title": action.payload.issue_title,
                "body": action.payload.issue_body,
            },
        )
        resp.raise_for_status()
        issue = resp.json()
        logger.success(
            "[GitHub] Created {} — '{}'",
            issue["html_url"],
            action.payload.issue_title,
        )
        return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "[GitHub] {} {} — {}",
            exc.response.status_code,
            url,
            exc.response.text[:200],
        )
        return False
    except Exception as exc:
        logger.error("[GitHub] Failed to create issue for {}: {}", action.action_id, exc)
        return False
