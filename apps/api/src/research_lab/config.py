from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

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
    public_api_hosts: str = ""
    database_url: str = "postgresql+psycopg://research:research@localhost:55432/research_lab"
    openalex_api_key: Optional[str] = None
    openalex_content_daily_limit: int = Field(default=40, ge=0)
    unpaywall_email: Optional[str] = None
    core_api_key: Optional[str] = None
    deepl_api_key: Optional[str] = None
    deepl_base_url: Optional[str] = None
    translation_monthly_reserve_characters: int = Field(default=10_000, ge=0)
    crossref_mailto: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    embedding_provider: str = "local_hash"
    fastembed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    fastembed_reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    artifact_root: Path = Path("../../artifacts")
    private_data_root: Path = Path("../../data/private")
    private_data_require_external: bool = False
    private_data_expected_mount: Optional[Path] = None
    private_data_sentinel: Optional[Path] = None
    private_data_min_free_gb: int = Field(default=25, ge=1)
    openalex_base_url: str = "https://api.openalex.org"
    unpaywall_base_url: str = "https://api.unpaywall.org/v2"
    core_base_url: str = "https://api.core.ac.uk/v3"
    biorxiv_api_base_url: str = "https://api.biorxiv.org"
    chemrxiv_api_base_url: str = "https://www.cambridge.org/engage/coe/public-api/v1"
    crossref_base_url: str = "https://api.crossref.org"
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    arxiv_base_url: str = "https://export.arxiv.org/api/query"
    
    # Sci-Hub resolver settings
    sci_hub_base_urls: list[str] = Field(
        default_factory=lambda: [
            "https://sci-hub.kr",
            "https://sci-hub.se",
            "https://sci-hub.st",
            "https://sci-hub.ru",
            "https://sci-hub.shop",
        ]
    )
    sci_hub_request_interval_seconds: float = Field(default=3.0, gt=0)
    
    # LibGen resolver settings
    libgen_api_base_url: str = "http://libgen.rs"
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    scihub_cli_executable: str = "scihub-cli"
    libgen_cli_executable: str = "libgen-cli"


@lru_cache
def get_settings() -> Settings:
    return Settings()
