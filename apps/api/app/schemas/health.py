from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness payload for GET /api/v1/health (docs/API_DESIGN.md)."""

    status: str = Field(description="Process liveness; 'ok' when the API is running.")
    service: str
    environment: str
