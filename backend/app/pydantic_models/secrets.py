"""Схемы запросов и ответов секретов"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SecretsResponse(BaseModel):
    seller_client_id: str | None = Field(default=None, description="Ozon Seller API Client ID")
    seller_api_key: str | None = Field(default=None, description="Ozon Seller API Key")
    performance_client_id: str | None = Field(default=None, description="Ozon Performance API Client ID")
    performance_secret: str | None = Field(default=None, description="Ozon Performance API Secret")
    seller_valid: bool = Field(default=False, description="Валидность Seller API ключей")
    performance_valid: bool = Field(default=False, description="Валидность Performance API ключей")


class SecretsUpdate(BaseModel):
    seller_client_id: str | None = Field(default=None)
    seller_api_key: str | None = Field(default=None)
    performance_client_id: str | None = Field(default=None)
    performance_secret: str | None = Field(default=None)
