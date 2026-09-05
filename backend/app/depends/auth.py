from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.user_adapter import UserAdapter
from backend.app.config import settings
from backend.app.database import get_db_session
from backend.app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

COOKIE_NAME = "metrixsense_token"

logger = structlog.get_logger(__name__)

def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.JWT_EXPIRATION_HOURS * 3600,
        expires=settings.JWT_EXPIRATION_HOURS * 3600,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )


async def get_token_from_request(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
) -> str:
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token
    if token:
        return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


async def get_current_user(
    db: AsyncSession = Depends(get_db_session),  # noqa: B008
    token: str = Depends(get_token_from_request),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    adapter = UserAdapter(db)
    user = await adapter.get_by_id(int(user_id), load_secrets=True)
    if user is None:
        raise credentials_exception
    return user
