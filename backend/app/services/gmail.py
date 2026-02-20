"""Gmail API wrapper: OAuth token management and email reading."""
import base64
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import settings

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "email",
]

# Gmail search query to find job application confirmation emails (2026 only)
#
# Sender-based terms target the SPECIFIC senders that send application confirmations,
# NOT entire domains — this avoids capturing LinkedIn newsletters/notifications and
# Indeed job alerts which would flood the 2000-result limit and bury real emails.
#
# LinkedIn application confirmations come from:
#   jobs-noreply@linkedin.com  — "Your application to Role at Company"
#   jobs-listings@linkedin.com — "Your application was sent to Company"
#
# Indeed application confirmations come from:
#   indeedapply@indeed.com     — "Application submitted" format
APPLICATION_QUERY = (
    '('
    'from:jobs-noreply@linkedin.com OR '
    'from:jobs-listings@linkedin.com OR '
    'from:indeedapply@indeed.com OR '
    '"Thank you for applying" OR '
    '"Application received" OR '
    '"Your application to" OR '
    '"We received your application" OR '
    '"application has been submitted" OR '
    '"Application submitted" OR '
    '"Thank you for submitting" OR '
    '"submitted your application" OR '
    '"Your application was sent" OR '
    '"application was sent to" OR '
    '"We have received your application" OR '
    '"received your resume"'
    ') -subject:"was viewed by" after:2026/01/01'
)

# Gmail search query to find rejection emails (2026 only)
# Broad enough to catch varied phrasing while avoiding false positives
REJECTION_QUERY = (
    '("move forward with other candidates" OR '
    '"not moving forward with your application" OR '
    '"decided to pursue other" OR '
    '"we regret to inform" OR '
    '"application was not selected" OR '
    '"not selected for" OR '
    '"not be moving forward" OR '
    '"unable to move forward" OR '
    '"not be proceeding" OR '
    '"have filled this position" OR '
    '"decided to go in a different direction" OR '
    '"chosen to move forward with another") after:2026/01/01'
)

# Gmail search query to find assessment/coding challenge emails (2026 only)
ASSESSMENT_QUERY = (
    '("complete your assessment" OR '
    '"coding challenge" OR '
    '"technical assessment" OR '
    '"online assessment" OR '
    '"HackerRank" OR '
    '"Codility" OR '
    '"CodeSignal" OR '
    '"take-home" OR '
    '"invited to complete" OR '
    '"next steps" "assessment") after:2026/01/01'
)

# Gmail search query to find phone screen / recruiter scheduling emails (2026 only)
PHONE_SCREEN_QUERY = (
    '("schedule a call" OR '
    '"phone screen" OR '
    '"phone interview" OR '
    '"recruiter call" OR '
    '"introductory call" OR '
    '"we would like to speak with you" OR '
    '"we would like to chat" OR '
    '"we\'d like to connect" OR '
    '"book a time" OR '
    '"schedule time with") '
    '-("thank you for applying" OR "application received" OR "application submitted") '
    'after:2026/01/01'
)

# Gmail search query to find technical interview invitation emails (2026 only)
TECHNICAL_QUERY = (
    '("technical interview" OR '
    '"virtual onsite" OR '
    '"engineering interview" OR '
    '"we would like to invite you for an interview" OR '
    '"invite you to interview") '
    '-("assessment" OR "coding challenge" OR "HackerRank" OR "Codility" OR "CodeSignal") '
    'after:2026/01/01'
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
        # Google's library compares expiry with a naive UTC datetime,
        # so strip the timezone info (the value is already stored as UTC).
        creds.expiry = user.token_expires_at.replace(tzinfo=None)
    return creds


def _list_all_messages(service, query: str, hard_limit: int = 5000) -> list[dict]:
    """
    Paginate through the Gmail messages list API until all results are returned.
    Gmail returns at most 100 per page; we loop through nextPageToken.
    hard_limit guards against runaway scans on very large inboxes.
    """
    all_messages: list[dict] = []
    page_token: str | None = None

    while len(all_messages) < hard_limit:
        kwargs: dict = {"userId": "me", "q": query, "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
        all_messages.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_messages


def _get_service(user):
    creds = _build_credentials(user)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def list_new_messages(user) -> list[dict]:
    """
    Return ALL Gmail messages matching the application keyword filter (paginated).
    """
    return _list_all_messages(_get_service(user), APPLICATION_QUERY)


def list_rejection_messages(user) -> list[dict]:
    """Return ALL Gmail messages matching the rejection keyword filter (paginated)."""
    return _list_all_messages(_get_service(user), REJECTION_QUERY)


def list_assessment_messages(user) -> list[dict]:
    """Return ALL Gmail messages matching the assessment/coding-challenge filter (paginated)."""
    return _list_all_messages(_get_service(user), ASSESSMENT_QUERY)


def list_phone_screen_messages(user) -> list[dict]:
    """Return Gmail messages that look like phone screen / scheduling invites."""
    return _list_all_messages(_get_service(user), PHONE_SCREEN_QUERY)


def list_technical_messages(user) -> list[dict]:
    """Return Gmail messages that look like technical interview invitations."""
    return _list_all_messages(_get_service(user), TECHNICAL_QUERY)


def send_digest_email(user, html_body: str) -> None:
    """
    Send an HTML email to the user via the Gmail API.
    Requires the gmail.send scope — fails gracefully if the token predates
    that scope (user must re-authenticate once to grant it).
    """
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Weekly HireTrace Digest"
    msg["From"] = f"HireTrace <{user.email}>"
    msg["To"] = user.email
    msg.attach(MIMEText(html_body, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    _get_service(user).users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()


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
    """
    Recursively extract plain-text body from a Gmail message payload.
    Prefers text/plain; falls back to text/html with tags stripped.
    """
    import re as _re

    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    if "parts" in payload:
        html_fallback = ""
        for part in payload["parts"]:
            text = _extract_body(part)
            if text and part.get("mimeType") == "text/plain":
                return text  # plain text wins immediately
            if text and not html_fallback:
                html_fallback = text
        if html_fallback:
            return html_fallback

    # HTML-only email: decode and strip tags
    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            # Convert block-level tags to newlines BEFORE stripping, so the
            # parsers see line-separated text (e.g. "Insomniac Hedge Fund Guy\n- Remote")
            # rather than one long line where the company regex over-captures.
            html = _re.sub(
                r"</?(?:br|p|div|tr|td|th|li|h[1-6])\b[^>]*>",
                "\n", html, flags=_re.IGNORECASE,
            )
            # Strip remaining tags
            text = _re.sub(r"<[^>]+>", " ", html)
            # Decode common HTML entities
            text = (text.replace("&nbsp;", " ").replace("&#39;", "'")
                        .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
            # Clean up each line individually, then drop blank lines
            lines = [_re.sub(r" {2,}", " ", line).strip() for line in text.split("\n")]
            return "\n".join(line for line in lines if line)

    return ""


def _parse_date(date_str: str) -> datetime | None:
    """Parse an RFC 2822 email date string to a timezone-aware datetime."""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None
