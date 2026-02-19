"""Gmail OAuth2 authentication routes."""
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.services import gmail
from app.schemas.user import UserOut

router = APIRouter()


def _get_current_user_id(request: Request) -> str | None:
    return request.session.get("user_id")


def require_user(request: Request) -> str:
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/google")
async def google_login(request: Request):
    """Redirect the user to Google's OAuth2 consent screen."""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    url = gmail.build_oauth_url(state)
    return RedirectResponse(url)


@router.get("/callback")
async def google_callback(request: Request, code: str, state: str):
    """Handle the OAuth2 callback, exchange code for tokens, upsert user."""
    if state != request.session.get("oauth_state"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    tokens = await gmail.exchange_code_for_tokens(code)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    email = await gmail.get_user_email(access_token)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(email=email)
            db.add(user)

        user.google_access_token = access_token
        if refresh_token:
            user.google_refresh_token = refresh_token
        user.token_expires_at = expires_at

        await db.commit()
        await db.refresh(user)
        user_id = str(user.id)

    request.session["user_id"] = user_id
    from app.config import settings
    return RedirectResponse(f"{settings.frontend_url}/dashboard")


@router.post("/logout")
async def logout(request: Request):
    """Revoke Google tokens and clear the session."""
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.google_access_token:
            await gmail.revoke_token(user.google_access_token)
            user.google_access_token = None
            user.google_refresh_token = None
            await db.commit()

    request.session.clear()
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
async def get_me(request: Request):
    """Return the current authenticated user's profile."""
    user_id = require_user(request)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserOut.model_validate(user)
