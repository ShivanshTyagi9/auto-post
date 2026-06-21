"""
Thin wrapper around Supabase Auth (GoTrue) REST API.

Signup uses the Admin API (service_role key) so accounts are created already
email-confirmed: this app gates signup behind an activation code, so Supabase's
own email-confirmation step would be redundant — and silently break the
"sign up -> immediately logged in" flow unless the project's dashboard
"Confirm email" toggle happened to be off. We confirm explicitly instead of
depending on that toggle.

Customer/Admin profile data (name, IG credentials, role, etc.) lives in our own
``admins``/``customers`` tables, keyed by the Supabase Auth user id. Supabase
itself only ever sees email + password.

All calls are async (httpx.AsyncClient) so they don't block the event loop —
matches the convention already used for Graph API calls in client.py.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


class SupabaseAuthError(Exception):
    """Raised when Supabase Auth rejects a request (bad credentials, duplicate email, etc.)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    return url


def _anon_key() -> str:
    key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY is not set")
    return key


def _service_role_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set")
    return key


def _error_message(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        return data.get("msg") or data.get("message") or data.get("error_description") or resp.text
    except ValueError:
        return resp.text


async def create_confirmed_user(email: str, password: str) -> dict[str, Any]:
    """Create a Supabase Auth user that's already email-confirmed (admin API)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_base_url()}/auth/v1/admin/users",
            headers={
                "apikey": _service_role_key(),
                "Authorization": f"Bearer {_service_role_key()}",
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password, "email_confirm": True},
        )
    if resp.status_code >= 400:
        raise SupabaseAuthError(_error_message(resp), resp.status_code)
    return resp.json()


async def login(email: str, password: str) -> dict[str, Any]:
    """Exchange email+password for a Supabase session (access_token, refresh_token, user)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{_base_url()}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": _anon_key(), "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
    if resp.status_code >= 400:
        raise SupabaseAuthError(_error_message(resp), 401)
    return resp.json()


async def get_user(access_token: str) -> Optional[dict[str, Any]]:
    """Validate an access token and return the Supabase user it belongs to, or None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_base_url()}/auth/v1/user",
                headers={"apikey": _anon_key(), "Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()


async def delete_user(user_id: str) -> None:
    """Best-effort delete of a Supabase Auth user — used to roll back a signup if our
    own DB write fails after the Supabase user was already created, so the two stores
    don't drift out of sync."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.delete(
                f"{_base_url()}/auth/v1/admin/users/{user_id}",
                headers={"apikey": _service_role_key(), "Authorization": f"Bearer {_service_role_key()}"},
            )
    except httpx.HTTPError:
        pass
