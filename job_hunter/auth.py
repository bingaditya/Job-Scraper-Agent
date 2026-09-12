from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class AuthUser:
    id: str
    email: str | None = None


@lru_cache(maxsize=8)
def _jwks_client_for(supabase_url: str) -> PyJWKClient:
    """One cached PyJWKClient per project URL; it caches keys internally too."""
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthUser:
    """FastAPI dependency: verifies a Supabase Auth JWT via the project's JWKS endpoint.

    Supabase projects on the newer "JWT Signing Keys" system use asymmetric keys
    (e.g. ECC P-256 / ES256) discoverable at {SUPABASE_URL}/auth/v1/.well-known/jwks.json
    rather than a shared HS256 secret, so verification fetches (and caches) the
    public signing key by the token's `kid` rather than using a static secret.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    storage = request.app.state.config.storage
    if not storage.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server is not configured with SUPABASE_URL.",
        )

    try:
        jwks_client = _jwks_client_for(storage.supabase_url)
        signing_key = jwks_client.get_signing_key_from_jwt(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
    except jwt.PyJWKClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not resolve signing key: {exc}",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing a subject claim.",
        )
    return AuthUser(id=str(user_id), email=payload.get("email"))
