
from fastapi import APIRouter

from backend.app.pydantic_models import HealthResponse


def get_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health", response_model=HealthResponse)
    async def health_check():
        return HealthResponse(status="ok")

    return router
