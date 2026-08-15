from __future__ import annotations

import importlib.util
import math
import time
from dataclasses import dataclass
from statistics import median

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embedding_selection import choose_search_embedding_provider
from research_lab.embeddings import build_embedding_provider
from research_lab.models import PaperEmbedding
from research_lab.retrieval import HybridRetrievalService
from research_lab.schemas import RetrievalHealthResponse, RetrievalProviderHealth

BENCHMARK_QUERIES: tuple[str, ...] = (
    "AI capability firm performance",
    "AI adoption organizational change",
    "responsible AI governance human oversight",
    "industrial AI smart manufacturing",
    "agentic systems enterprise workflows",
)


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkResult:
    provider: str
    model: str
    query_count: int
    sample_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float


def get_retrieval_health(session: Session, settings: Settings) -> RetrievalHealthResponse:
    embedding_rows = session.execute(
        select(PaperEmbedding.provider, PaperEmbedding.model, func.count(PaperEmbedding.id))
        .group_by(PaperEmbedding.provider, PaperEmbedding.model)
        .order_by(PaperEmbedding.provider, PaperEmbedding.model)
    ).all()
    database_default_iterative_scan = str(
        session.execute(text("SHOW hnsw.iterative_scan")).scalar_one()
    )
    fastembed_installed = importlib.util.find_spec("fastembed") is not None
    auto_selection = choose_search_embedding_provider(session, settings, "auto")
    return RetrievalHealthResponse(
        configured_provider=settings.embedding_provider,
        auto_selected_provider=auto_selection.provider.name,
        auto_selection_reason=auto_selection.reason,
        fastembed_dependency_installed=fastembed_installed,
        database_default_hnsw_iterative_scan=database_default_iterative_scan,
        vector_query_hnsw_policy="strict_order_per_vector_query",
        providers=[
            RetrievalProviderHealth(provider=provider, model=model, embedding_count=int(count))
            for provider, model, count in embedding_rows
        ],
        notes=[
            "Provider availability reports stored embedding rows; it does not imply benchmark quality.",
            "FastEmbed models remain lazy and process-cached; this endpoint does not load model weights.",
            "The database default can remain off because vector-search transactions set strict_order locally.",
        ],
    )


def benchmark_retrieval(
    session: Session,
    settings: Settings,
    *,
    provider_name: str,
    repeats: int = 3,
) -> RetrievalBenchmarkResult:
    provider = build_embedding_provider(settings, provider_name)
    service = HybridRetrievalService(session, provider)

    # One warm-up also ensures an optional local model is initialized before timed samples.
    service.search(BENCHMARK_QUERIES[0], mode="hybrid", limit=10)
    samples: list[float] = []
    for _ in range(repeats):
        for query in BENCHMARK_QUERIES:
            started = time.perf_counter()
            service.search(query, mode="hybrid", limit=10)
            samples.append((time.perf_counter() - started) * 1000.0)

    ordered = sorted(samples)
    p95_index = _percentile_index(ordered, 0.95)
    p99_index = _percentile_index(ordered, 0.99)
    return RetrievalBenchmarkResult(
        provider=provider.name,
        model=provider.model,
        query_count=len(BENCHMARK_QUERIES),
        sample_count=len(samples),
        p50_ms=median(samples),
        p95_ms=ordered[p95_index],
        p99_ms=ordered[p99_index],
        min_ms=ordered[0],
        max_ms=ordered[-1],
    )


def _percentile_index(ordered: list[float], quantile: float) -> int:
    return max(math.ceil(len(ordered) * quantile) - 1, 0)


def postgres_search_statement_stats(session: Session, *, limit: int = 20) -> list[dict[str, object]]:
    """Return real PostgreSQL timing statistics for search-related statements.

    pg_stat_statements reports aggregate mean/min/max timing rather than request-level
    percentiles. P50/P95/P99 come from benchmark_retrieval; this report identifies the
    database statements that deserve EXPLAIN ANALYZE follow-up.
    """

    available = bool(
        session.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements')")
        ).scalar_one()
    )
    if not available:
        return []
    rows = session.execute(
        text(
            """
            SELECT queryid, calls,
                   round(total_exec_time::numeric, 3) AS total_exec_ms,
                   round(mean_exec_time::numeric, 3) AS mean_exec_ms,
                   round(min_exec_time::numeric, 3) AS min_exec_ms,
                   round(max_exec_time::numeric, 3) AS max_exec_ms,
                   rows,
                   left(regexp_replace(query, '\\s+', ' ', 'g'), 600) AS query
            FROM pg_stat_statements
            WHERE (lower(ltrim(query)) LIKE 'select%' OR lower(ltrim(query)) LIKE 'with%')
              AND query ILIKE ANY (ARRAY[
                '%websearch_to_tsquery%', '%paper_embeddings%', '%paper_chunks%',
                '%authors%ILIKE%', '%venues%ILIKE%', '%tags%ILIKE%'
            ])
            ORDER BY total_exec_time DESC
            LIMIT :limit
            """
        ),
        {"limit": max(1, limit)},
    ).mappings()
    return [dict(row) for row in rows]
