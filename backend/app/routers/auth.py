"""Регистрация, вход, текущий пользователь"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend.app.adapters.user_adapter import UserAdapter
from backend.app.depends.auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    set_auth_cookie,
)
from backend.app.depends.db import get_user_adapter
from backend.app.models.user import User
from backend.app.pydantic_models.auth import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)


def get_auth_router() -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])


    @router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
    async def register(
        data: UserRegister,
        response: Response,
        db: UserAdapter = Depends(get_user_adapter),  # noqa: B008
    ):
        if await db.user_exists(data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        user = await db.create_user(data.username, data.password)

        token = create_access_token(user.id, user.username)
        set_auth_cookie(response, token)

        return UserResponse(
            id=user.id,
            username=user.username,
            is_active=user.is_active,
            created_at=user.created_at,
        )


    @router.post("/login", response_model=TokenResponse)
    async def login(
        data: UserLogin,
        response: Response,
        db: UserAdapter = Depends(get_user_adapter),  # noqa: B008
    ):
        user = await db.authenticate(data.username, data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        token = create_access_token(user.id, user.username)
        set_auth_cookie(response, token)
        expires_in = 24 * 3600

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
        )


    @router.post("/logout")
    async def logout(response: Response):
        clear_auth_cookie(response)
        return {"message": "Logged out successfully"}


    @router.get("/me", response_model=UserResponse)
    async def get_me(current_user: User = Depends(get_current_user)):  # noqa: B008
        return UserResponse(
            id=current_user.id,
            username=current_user.username,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
        )
    
    return router
