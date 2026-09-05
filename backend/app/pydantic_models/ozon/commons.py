"""Общие базовые модели Ozon API, используемые в Seller и Performance API"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OzonBaseModel(BaseModel):
    """Базовая модель для всех схем Ozon API (с алиасами, заполнение по имени)"""

    model_config = ConfigDict(populate_by_name=True)


class BearerTokenResponse(OzonBaseModel):
    """POST /api/client/token — ответ с bearer-токеном Performance API"""

    access_token: str = Field(..., description="Access token")
    expires_in: int = Field(default=1800, description="Token expiration time in seconds")
    token_type: str = Field(default="Bearer", description="Token type, usually 'Bearer'")
