from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI × MOT Research Lab"
    app_environment: str = "development"
    read_only_mode: bool = False
    public_api_hosts: str = "aimot.oosu.dev"
    database_url: str = "postgresql+psycopg://research:research@localhost:55432/research_lab"
    openalex_api_key: str | None = None
    crossref_mailto: str | None = None
    semantic_scholar_api_key: str | None = None
    openai_api_key: str | None = None
    embedding_provider: str = "local_hash"
    fastembed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    fastembed_reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    artifact_root: Path = Path("../../artifacts")
    private_data_root: Path = Path("../../data/private")
    openalex_base_url: str = "https://api.openalex.org"
    crossref_base_url: str = "https://api.crossref.org"
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    arxiv_base_url: str = "https://export.arxiv.org/api/query"
    request_timeout_seconds: float = Field(default=30.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

