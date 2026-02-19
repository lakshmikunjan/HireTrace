"""Gmail API wrapper: OAuth token management and email reading."""
import base64
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Gmail search query to find job application confirmation emails
APPLICATION_QUERY = (
    '"Thank you for applying" OR "Application received" OR "Your application to" OR '
    '"We received your application" OR "application has been submitted"'
)


def build_oauth_url(state: str) -> str:
    """Generate the Google OAuth2 authorization URL."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    """Exchange an authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def get_user_email(access_token: str) -> str:
    """Get the authenticated user's email address from Google."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()["email"]


async def revoke_token(token: str) -> None:
    """Revoke a Google OAuth token."""
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": token},
        )


def _build_credentials(user) -> Credentials:
    """Build a Google Credentials object from a User model instance."""
    creds = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    if user.token_expires_at:
        creds.expiry = user.token_expires_at.replace(tzinfo=timezone.utc)
    return creds


def list_new_messages(user, max_results: int = 100) -> list[dict]:
    """
    List Gmail messages matching the application keyword filter.
    Refreshes the access token if expired.
    Returns a list of minimal message objects with 'id' and 'threadId'.
    """
    creds = _build_credentials(user)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    result = (
        service.users()
        .messages()
        .list(userId="me", q=APPLICATION_QUERY, maxResults=max_results)
        .execute()
    )
    return result.get("messages", [])


def get_message_detail(user, message_id: str) -> dict:
    """
    Fetch full message detail (headers + body) for a given Gmail message ID.
    Returns a dict with: sender, subject, body, date.
    """
    creds = _build_credentials(user)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    body = _extract_body(msg["payload"])
    date_str = headers.get("date", "")

    return {
        "id": message_id,
        "sender": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "body": body,
        "date": _parse_date(date_str),
        "snippet": msg.get("snippet", ""),
    }


def _extract_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    if "parts" in payload:
        for part in payload["parts"]:
            text = _extract_body(part)
            if text:
                return text
    return ""


def _parse_date(date_str: str) -> datetime | None:
    """Parse an RFC 2822 email date string to a timezone-aware datetime."""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None
