"""Схема ответа проверки состояния сервиса"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str = "MetrixSense"
    version: str = "1.0.0"
