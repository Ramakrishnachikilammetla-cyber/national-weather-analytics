"""Application settings loaded from environment variables.

Database, Kafka, Spark, and auth settings are reserved for later phases.
This phase does not open a database connection.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "National Weather Analytics API"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"


settings = Settings()
