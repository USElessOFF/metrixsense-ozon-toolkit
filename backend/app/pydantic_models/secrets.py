"""Схемы запросов и ответов секретов"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


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

    @field_validator("seller_client_id")
    @classmethod
    def client_id_is_positive_int(cls, v: str | None) -> str | None:
        """Ozon требует Client-Id как положительное целое — валидируем до внешнего запроса"""
        if v is None or not v.strip():
            return v
        if not v.strip().isdigit():
            raise ValueError("Client-Id должен быть положительным целым числом (из кабинета Ozon)")
        return v.strip()
