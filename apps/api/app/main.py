from fastapi import FastAPI

from app.api.v1.router import api_v1_router
from app.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "National Weather Big Data Analytics Platform API for India. "
            "Foundation phase: liveness only. Auth, database, ingest, Kafka, "
            "Spark, and ML are not enabled yet."
        ),
    )
    application.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
