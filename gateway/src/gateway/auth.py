import hashlib
import logging
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)
from pwdlib import PasswordHash

from gateway.settings import Settings

logger = logging.getLogger(__name__)

_API_TOKEN_PREFIX = "gw"
_DUMMY_API_TOKEN_HASH = "0" * 64
_basic_auth = HTTPBasic(auto_error=False)
_bearer_auth = HTTPBearer(auto_error=False)
_password_hash = PasswordHash.recommended()


def hash_api_token_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def hash_dashboard_password(password: str) -> str:
    return _password_hash.hash(password)


def _settings(request: Request) -> Settings:
    return request.app.state.context.settings


def _unauthorized(challenge: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": challenge},
    )


def _parse_api_token(token: str) -> tuple[str, str] | None:
    prefix, separator, remainder = token.partition("_")
    token_id, secret_separator, secret = remainder.partition("_")
    if (
        prefix != _API_TOKEN_PREFIX
        or not separator
        or not secret_separator
        or not token_id
        or not secret
    ):
        return None
    return token_id, secret


def require_api_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_auth)],
) -> str:
    settings = _settings(request)
    if not settings.api_token_hashes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API token authentication is not configured",
        )

    parsed = _parse_api_token(credentials.credentials) if credentials is not None else None
    token_id, secret = parsed or ("", "")
    expected_hash = settings.api_token_hashes.get(token_id, _DUMMY_API_TOKEN_HASH)
    supplied_hash = hash_api_token_secret(secret)

    if parsed is None or not secrets.compare_digest(supplied_hash, expected_hash):
        raise _unauthorized("Bearer")

    request.state.api_token_id = token_id
    logger.info("API token authenticated", extra={"api_token_id": token_id})
    return token_id


def require_dashboard_basic_auth(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic_auth)],
) -> str:
    settings = _settings(request)
    if not settings.dashboard_password_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard authentication is not configured",
        )

    username = credentials.username if credentials is not None else ""
    password = credentials.password if credentials is not None else ""
    username_valid = secrets.compare_digest(
        username.encode(),
        settings.dashboard_username.encode(),
    )
    try:
        password_valid = _password_hash.verify(password, settings.dashboard_password_hash)
    except Exception as exc:
        logger.error("Dashboard password hash verification failed", exc_info=exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard authentication is not configured",
        ) from exc

    if not username_valid or not password_valid:
        raise _unauthorized('Basic realm="dashboard"')

    return username
