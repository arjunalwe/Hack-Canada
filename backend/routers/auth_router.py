"""Auth0 router — /api/auth endpoints.

Provides:
  GET  /api/auth/me             – Returns the caller's Auth0 userinfo
  GET  /api/auth/mfa/status     – Whether MFA is enrolled for this user
  POST /api/auth/mfa/enroll     – Initiates MFA enrollment (redirect URL)
  POST /api/auth/passwordless/start – Proxies passwordless magic-link request

All endpoints require a valid Bearer JWT issued by Auth0 and validated
via the existing get_current_user dependency in backend/auth/auth0.py.
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from config import settings
from auth.auth0 import get_current_user

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────

def _management_token() -> str:
    """Obtain a short-lived Management API token via client_credentials.

    Requires AUTH0_CLIENT_SECRET + AUTH0_API_AUDIENCE to be set in .env.
    Falls back to an empty string (which will cause the Management API
    call to fail gracefully) when credentials are missing.
    """
    if not settings.AUTH0_DOMAIN or not settings.AUTH0_CLIENT_SECRET:
        return ""

    url = f"https://{settings.AUTH0_DOMAIN}/oauth/token"
    payload = json.dumps({
        "grant_type":    "client_credentials",
        "client_id":     settings.AUTH0_CLIENT_ID,
        "client_secret": settings.AUTH0_CLIENT_SECRET,
        "audience":      f"https://{settings.AUTH0_DOMAIN}/api/v2/",
    }).encode()

    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            return data.get("access_token", "")
    except Exception:
        return ""


def _management_get(path: str, mgmt_token: str) -> dict:
    url = f"https://{settings.AUTH0_DOMAIN}/api/v2/{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {mgmt_token}"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


# ── Request bodies ──────────────────────────────────────────────────────────

class PasswordlessStartBody(BaseModel):
    email: str
    connection: str = "email"
    send: str = "link"


# ── Routes ──────────────────────────────────────────────────────────────────

@router.get("/me", summary="Return the authenticated user's profile")
async def get_me(user: dict = Depends(get_current_user)):
    """Returns the Auth0 JWT payload for the authenticated caller.

    Useful for the frontend to display basic user info without an extra
    round-trip to the Auth0 /userinfo endpoint.
    """
    return {
        "sub":           user.get("sub"),
        "email":         user.get("email"),
        "name":          user.get("name"),
        "picture":       user.get("picture"),
        "email_verified": user.get("email_verified"),
    }


@router.get("/mfa/status", summary="Check MFA enrollment status for the authenticated user")
async def mfa_status(user: dict = Depends(get_current_user)):
    """Queries the Auth0 Management API to check whether MFA (Guardian)
    is enrolled for this user.

    Returns { enrolled: bool, factors: [...] }.
    """
    sub = user.get("sub", "")
    if not sub or not settings.AUTH0_DOMAIN:
        return {"enrolled": False, "factors": []}

    try:
        mgmt_token = _management_token()
        if not mgmt_token:
            return {"enrolled": False, "factors": [], "note": "Management API not configured"}

        # Encode the user_id for URL safety
        encoded_sub = urllib.parse.quote(sub, safe="")
        factors = _management_get(f"users/{encoded_sub}/authentication-methods", mgmt_token)

        enrolled = isinstance(factors, list) and len(factors) > 0
        return {"enrolled": enrolled, "factors": factors if isinstance(factors, list) else []}

    except urllib.error.HTTPError as e:
        if e.code in (404, 403):
            return {"enrolled": False, "factors": []}
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Management API error: {e.code}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=str(exc))


@router.post("/mfa/enroll", summary="Start MFA enrollment for the authenticated user")
async def mfa_enroll(user: dict = Depends(get_current_user)):
    """Returns an MFA associate URL from Auth0 Guardian.

    The frontend should open this URL (or embed the QR code) to allow
    the user to enroll an authenticator app.

    Requires: AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET,
              AUTH0_API_AUDIENCE (Management API) in .env
    """
    sub = user.get("sub", "")
    if not sub or not settings.AUTH0_DOMAIN:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Auth0 Management API not configured.")
    try:
        mgmt_token = _management_token()
        if not mgmt_token:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Could not obtain Management API token.")

        # Create a ticket for MFA enrollment
        url = f"https://{settings.AUTH0_DOMAIN}/api/v2/guardian/enrollments/ticket"
        payload = json.dumps({"user_id": sub, "send_mail": False}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Authorization": f"Bearer {mgmt_token}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())

        return {
            "message":    "MFA enrollment initiated.",
            "ticket_url": data.get("ticket_url"),
        }
    except HTTPException:
        raise
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Guardian enrollment failed: {e.code}")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=str(exc))


@router.post("/passwordless/start", summary="Send a passwordless magic link or OTP")
async def passwordless_start(body: PasswordlessStartBody):
    """Proxy to Auth0 /passwordless/start.

    Does NOT require authentication (this is the entry point for new users
    or those who forgot their password).  Rate-limiting should be handled
    by Auth0's brute-force protection.
    """
    if not settings.AUTH0_DOMAIN or not settings.AUTH0_CLIENT_ID:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Auth0 not configured.")

    url = f"https://{settings.AUTH0_DOMAIN}/passwordless/start"
    payload = json.dumps({
        "client_id":  settings.AUTH0_CLIENT_ID,
        "connection": body.connection,
        "email":      body.email,
        "send":       body.send,
        "authParams": {
            "scope":        "openid profile email",
            "redirect_uri": f"http://localhost:5500/auth/callback.html",
        },
    }).encode()

    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return JSONResponse(content={"ok": True, "status": resp.status})
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            err = json.loads(body_bytes)
        except Exception:
            err = {"raw": body_bytes.decode(errors="replace")}
        raise HTTPException(status_code=e.code, detail=err)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
