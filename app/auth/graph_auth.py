"""Microsoft Graph API authentication via MSAL Device Code Flow.

First run prompts the user to open a browser and enter a code.
Subsequent runs reuse the locally cached token (silent refresh).

Azure App Registration prerequisites:
  1. Register an app at https://portal.azure.com -> Azure AD -> App registrations
  2. Set Redirect URI to https://login.microsoftonline.com/common/oauth2/nativeclient
  3. Add Delegated permissions: Chat.ReadWrite, Chat.Create, User.Read, User.ReadBasic.All
  4. Grant admin consent if required by your org
"""

from __future__ import annotations

from pathlib import Path

import httpx
import msal
from loguru import logger

from app.config import Settings

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = [
    "https://graph.microsoft.com/Chat.ReadWrite",
    "https://graph.microsoft.com/Chat.Create",
    "https://graph.microsoft.com/User.Read",
    "https://graph.microsoft.com/User.ReadBasic.All",
]

_app_cache: dict[str, tuple[msal.PublicClientApplication, msal.SerializableTokenCache]] = {}


def _build_msal_app(settings: Settings) -> tuple[msal.PublicClientApplication, msal.SerializableTokenCache]:
    """Build (or return cached) MSAL app with a persistent token cache."""
    cache_key = f"{settings.ms_client_id}:{settings.ms_tenant_id}"
    if cache_key in _app_cache:
        return _app_cache[cache_key]

    cache = msal.SerializableTokenCache()
    cache_path = Path(settings.ms_token_cache_path)
    if cache_path.exists():
        cache.deserialize(cache_path.read_text(encoding="utf-8"))

    app = msal.PublicClientApplication(
        settings.ms_client_id,
        authority=f"https://login.microsoftonline.com/{settings.ms_tenant_id}",
        token_cache=cache,
    )
    _app_cache[cache_key] = (app, cache)
    return app, cache


def _save_cache(cache: msal.SerializableTokenCache, settings: Settings) -> None:
    if cache.has_state_changed:
        Path(settings.ms_token_cache_path).write_text(cache.serialize(), encoding="utf-8")


def get_access_token(settings: Settings) -> str:
    """Acquire an access token — silent refresh first, device code fallback."""
    app, cache = _build_msal_app(settings)

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result or "access_token" not in result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to create device flow: {flow}")

        print("\n" + "=" * 60)
        print("  Microsoft login required. Open a browser and go to:")
        print(f"    {flow['verification_uri']}")
        print(f"    Enter code: {flow['user_code']}")
        print("=" * 60 + "\n")

        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache, settings)

    if "access_token" not in result:
        raise RuntimeError(f"Auth failed: {result.get('error_description', result)}")

    logger.debug("Graph token acquired (expires_in={}s)", result.get("expires_in"))
    return result["access_token"]


def graph_get(token: str, path: str) -> dict:
    """GET request to the Graph API."""
    resp = httpx.get(
        f"{GRAPH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


def graph_post(token: str, path: str, body: dict) -> dict:
    """POST request to the Graph API."""
    resp = httpx.post(
        f"{GRAPH_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


_me_cache: dict[str, dict] = {}


def _get_me(token: str) -> dict:
    """Cached /me lookup (avoids repeated calls within a single run)."""
    if token not in _me_cache:
        _me_cache[token] = graph_get(token, "/me")
    return _me_cache[token]


def get_or_create_1on1_chat(token: str, user_email: str) -> str:
    """Get (or create) a 1:1 chat with a user and return the chat ID."""
    user = graph_get(token, f"/users/{user_email}")
    user_id = user["id"]

    me = _get_me(token)
    my_id = me["id"]

    if user_id == my_id:
        return "48:notes"

    chat = graph_post(token, "/chats", {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{my_id}')",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
            },
        ],
    })
    return chat["id"]



def send_chat_message(token: str, chat_id: str, content: str, *, content_type: str = "html") -> dict:
    """Send a message to an existing chat (1:1 or group)."""
    return graph_post(
        token,
        f"/chats/{chat_id}/messages",
        {"body": {"contentType": content_type, "content": content}},
    )
