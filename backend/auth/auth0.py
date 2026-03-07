"""Auth0 JWT verification middleware for FastAPI."""

import json
import urllib.request
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import settings

security = HTTPBearer(auto_error=False)


@lru_cache()
def get_jwks() -> dict:
    """Fetch the JSON Web Key Set from Auth0 (cached)."""
    jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
    with urllib.request.urlopen(jwks_url) as response:
        return json.loads(response.read())


def _get_signing_key(token: str) -> dict:
    """Extract the matching signing key from the JWKS."""
    jwks = get_jwks()
    unverified_header = jwt.get_unverified_header(token)
    for key in jwks["keys"]:
        if key["kid"] == unverified_header.get("kid"):
            return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find appropriate signing key.",
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """FastAPI dependency — verifies the Bearer JWT and returns the payload.

    If Auth0 is not configured (no domain set), bypass auth and return
    a stub user so development can proceed without credentials.
    """
    # ── Dev bypass when Auth0 is not configured ─────────────
    domain = (settings.AUTH0_DOMAIN or "").strip()
    if not domain or "your-" in domain or "." not in domain:
        return {"sub": "dev|local", "email": "dev@localhost"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header.",
        )

    token = credentials.credentials
    try:
        signing_key = _get_signing_key(token)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=f"https://{settings.AUTH0_DOMAIN}/",
        )
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {exc}",
        )
