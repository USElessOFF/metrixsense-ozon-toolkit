from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from backend.app.config import settings


def _fernet() -> Fernet:
    """Стабильный Fernet-ключ из SECRET_KEY (одинаковый при каждом старте)."""
    raw = settings.SECRET_KEY
    if isinstance(raw, str):
        raw = raw.encode()
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value):
    """Зашифровать строку; None остаётся None."""
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token):
    """Расшифровать; при ошибке — вернуть как есть (совместимость с открытыми данными)."""
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return token


def mask(value):
    """ak_************last4 — полный ключ в UI не отдаём."""
    if not value:
        return value
    if len(value) <= 6:
        return "***"
    return value[:2] + "*" * 8 + value[-4:]


@dataclass
class DecryptedSecrets:
    seller_client_id: str | None
    seller_api_key: str | None
    performance_client_id: str | None
    performance_secret: str | None
