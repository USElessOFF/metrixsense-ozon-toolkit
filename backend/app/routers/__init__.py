
from .auth import get_auth_router
from .calculator import get_calculator_router
from .health import get_health_router
from .onboarding import get_onboarding_router
from .reports import get_reports_router
from .secrets import get_secrets_router
from .settings import get_settings_router

__all__ = [
    "get_auth_router",
    "get_calculator_router",
    "get_health_router",
    "get_onboarding_router",
    "get_reports_router",
    "get_secrets_router",
    "get_settings_router",
]
