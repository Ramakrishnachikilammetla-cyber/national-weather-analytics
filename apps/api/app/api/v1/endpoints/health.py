from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Liveness check. Does not query a database."""
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )
