from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI & Technology Management Research Lab"
    app_environment: str = "development"
    database_url: str = "postgresql+psycopg://research:research@localhost:55432/research_lab"
    openalex_api_key: str | None = None
    crossref_mailto: str | None = None
    semantic_scholar_api_key: str | None = None
    openai_api_key: str | None = None
    openalex_base_url: str = "https://api.openalex.org"
    crossref_base_url: str = "https://api.crossref.org"
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    arxiv_base_url: str = "https://export.arxiv.org/api/query"
    request_timeout_seconds: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

