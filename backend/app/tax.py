"""Налоговые системы и их ставки"""

from __future__ import annotations

TAX_SYSTEM_RATES: dict[str, float] = {
    "usn_6": 0.06,   # УСН «Доходы»
    "usn_15": 0.15,  # УСН «Доходы минус расходы»
}

SUPPORTED_TAX_SYSTEMS = frozenset(TAX_SYSTEM_RATES)

INCOME_MINUS_EXPENSE_SYSTEMS = frozenset({"usn_15"})

DEFAULT_TAX_SYSTEM = "usn_6"


def get_tax_rate(tax_system: str | None) -> float:
    """Ставка налога по коду системы; неизвестная система → SettingsError"""
    from backend.app.exceptions import SettingsError

    if not tax_system:
        raise SettingsError(
            "Требуется настройка налоговой системы (tax_system не задан) "
            f"Поддерживаются: {sorted(SUPPORTED_TAX_SYSTEMS)}"
        )
    rate = TAX_SYSTEM_RATES.get(tax_system)
    if rate is None:
        raise SettingsError(
            f"Неизвестная налоговая система: {tax_system!r}"
            f"Поддерживаются: {sorted(SUPPORTED_TAX_SYSTEMS)}"
        )
    return rate
