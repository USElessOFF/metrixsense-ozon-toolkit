"""Схемы запросов и ответов аутентификации"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    """Запрос на регистрацию"""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=4, max_length=128, description="Password")


class UserLogin(BaseModel):
    """Запрос на вход"""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Ответ с JWT-токеном"""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class UserResponse(BaseModel):
    """Ответ с данными пользователя (без пароля)"""

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    is_active: bool = Field(..., description="Is account active")
    created_at: datetime = Field(..., description="Account creation date")
