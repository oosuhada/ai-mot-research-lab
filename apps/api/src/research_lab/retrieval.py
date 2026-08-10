from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from research_lab.embeddings import EmbeddingProvider, LocalHashEmbeddingProvider

SearchMode = Literal["lexical", "vector", "hybrid"]


@dataclass(frozen=True, slots=True)
class SearchFilters:
    year_from: int | None = None
    year_to: int | None = None
    axis: str | None = None
    work_type: str | None = None
    venue: str | None = None
    author: str | None = None
    methodology: str | None = None
    is_oa: bool | None = None


@dataclass(frozen=True, slots=True)
class RankedPaper:
    id: uuid.UUID
    doi: str | None
    openalex_id: str | None
    title: str
    abstract: str | None
    publication_date: date | None
    publication_year: int | None
    work_type: str | None
    oa_status: str | None
    is_oa: bool
    primary_url: str | None
    pdf_url: str | None
    license: str | None
    lexical_rank: int | None
    semantic_rank: int | None
    fused_score: float


class HybridRetrievalService:
    def __init__(
        self,
        session: Session,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.session = session
        self.embedding_provider = embedding_provider or LocalHashEmbeddingProvider()

    def search(
        self,
        query: str,
        *,
        mode: SearchMode = "hybrid",
        limit: int = 20,
        filters: SearchFilters | None = None,
    ) -> list[RankedPaper]:
        filters = filters or SearchFilters()
        candidate_limit = max(limit * 4, 50)

        lexical = (
            self._lexical_search(query, candidate_limit, filters)
            if mode in {"lexical", "hybrid"}
            else []
        )
        vector = (
            self._vector_search(query, candidate_limit, filters)
            if mode in {"vector", "hybrid"}
            else []
        )

        return reciprocal_rank_fusion(lexical, vector, limit=limit)

    def _filter_sql(self, filters: SearchFilters) -> tuple[str, dict[str, object]]:
        clauses: list[str] = []
        params: dict[str, object] = {}

        if filters.year_from is not None:
            clauses.append("p.publication_year >= :year_from")
            params["year_from"] = filters.year_from
        if filters.year_to is not None:
            clauses.append("p.publication_year <= :year_to")
            params["year_to"] = filters.year_to
        if filters.work_type:
            clauses.append("p.work_type = :work_type")
            params["work_type"] = filters.work_type
        if filters.is_oa is not None:
            clauses.append("p.is_oa = :is_oa")
            params["is_oa"] = filters.is_oa
        if filters.venue:
            clauses.append(
                "EXISTS (SELECT 1 FROM venues v WHERE v.id = p.venue_id AND v.name ILIKE :venue)"
            )
            params["venue"] = f"%{filters.venue}%"
        if filters.author:
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM paper_authors pa JOIN authors a ON a.id = pa.author_id "
                "WHERE pa.paper_id = p.id AND a.display_name ILIKE :author"
                ")"
            )
            params["author"] = f"%{filters.author}%"
        if filters.axis:
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM paper_topics pt JOIN topics t ON t.id = pt.topic_id "
                "WHERE pt.paper_id = p.id AND t.kind = 'research_axis' AND t.slug = :axis"
                ")"
            )
            params["axis"] = filters.axis
        if filters.methodology:
            methodology_slug = filters.methodology
            if not methodology_slug.startswith("methodology-"):
                methodology_slug = f"methodology-{methodology_slug}"
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM paper_topics pt JOIN topics t ON t.id = pt.topic_id "
                "WHERE pt.paper_id = p.id AND t.kind = 'methodology' AND t.slug = :methodology"
                ")"
            )
            params["methodology"] = methodology_slug

        return (" AND ".join(clauses) if clauses else "TRUE"), params

    def _lexical_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
    ) -> list[dict[str, object]]:
        filter_sql, params = self._filter_sql(filters)
        params.update({"query": _broad_websearch_query(query), "limit": limit})
        statement = text(
            f"""
            WITH q AS (
                SELECT websearch_to_tsquery('simple', :query) AS tsq
            )
            SELECT
                p.id,
                p.doi,
                p.openalex_id,
                p.title,
                p.abstract,
                p.publication_date,
                p.publication_year,
                p.work_type,
                p.oa_status,
                p.is_oa,
                p.primary_url,
                p.pdf_url,
                p.license,
                ts_rank_cd(p.search_vector, q.tsq) AS lexical_score
            FROM papers p
            CROSS JOIN q
            WHERE p.search_vector @@ q.tsq
              AND {filter_sql}
            ORDER BY lexical_score DESC, p.publication_year DESC NULLS LAST, p.id
            LIMIT :limit
            """
        )
        rows = self.session.execute(statement, params).mappings().all()
        return [dict(row) for row in rows]

    def _vector_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
    ) -> list[dict[str, object]]:
        filter_sql, params = self._filter_sql(filters)
        vector = self.embedding_provider.embed(query)
        params.update({"embedding": str(vector), "limit": limit})
        statement = text(
            f"""
            SELECT
                p.id,
                p.doi,
                p.openalex_id,
                p.title,
                p.abstract,
                p.publication_date,
                p.publication_year,
                p.work_type,
                p.oa_status,
                p.is_oa,
                p.primary_url,
                p.pdf_url,
                p.license,
                (pe.embedding <=> CAST(:embedding AS vector)) AS vector_distance
            FROM papers p
            JOIN paper_embeddings pe ON pe.paper_id = p.id
            WHERE pe.provider = :provider
              AND pe.model = :model
              AND {filter_sql}
            ORDER BY pe.embedding <=> CAST(:embedding AS vector), p.id
            LIMIT :limit
            """
        )
        params["provider"] = self.embedding_provider.name
        params["model"] = self.embedding_provider.model
        rows = self.session.execute(statement, params).mappings().all()
        return [dict(row) for row in rows]


def reciprocal_rank_fusion(
    lexical: list[dict[str, object]],
    vector: list[dict[str, object]],
    *,
    limit: int,
    rrf_k: int = 60,
) -> list[RankedPaper]:
    records: dict[uuid.UUID, dict[str, object]] = {}
    scores: dict[uuid.UUID, float] = {}
    lexical_ranks: dict[uuid.UUID, int] = {}
    semantic_ranks: dict[uuid.UUID, int] = {}

    for rank, row in enumerate(lexical, start=1):
        paper_id = row["id"]
        if not isinstance(paper_id, uuid.UUID):
            paper_id = uuid.UUID(str(paper_id))
        records[paper_id] = row
        lexical_ranks[paper_id] = rank
        scores[paper_id] = scores.get(paper_id, 0.0) + (1.0 / (rrf_k + rank))

    for rank, row in enumerate(vector, start=1):
        paper_id = row["id"]
        if not isinstance(paper_id, uuid.UUID):
            paper_id = uuid.UUID(str(paper_id))
        records.setdefault(paper_id, row)
        semantic_ranks[paper_id] = rank
        scores[paper_id] = scores.get(paper_id, 0.0) + (1.0 / (rrf_k + rank))

    ordered_ids = sorted(
        scores,
        key=lambda paper_id: (
            -scores[paper_id],
            lexical_ranks.get(paper_id, 10**9),
            semantic_ranks.get(paper_id, 10**9),
            str(paper_id),
        ),
    )[:limit]

    return [
        RankedPaper(
            id=paper_id,
            doi=_optional_str(records[paper_id].get("doi")),
            openalex_id=_optional_str(records[paper_id].get("openalex_id")),
            title=str(records[paper_id]["title"]),
            abstract=_optional_str(records[paper_id].get("abstract")),
            publication_date=_optional_date(records[paper_id].get("publication_date")),
            publication_year=_optional_int(records[paper_id].get("publication_year")),
            work_type=_optional_str(records[paper_id].get("work_type")),
            oa_status=_optional_str(records[paper_id].get("oa_status")),
            is_oa=bool(records[paper_id].get("is_oa")),
            primary_url=_optional_str(records[paper_id].get("primary_url")),
            pdf_url=_optional_str(records[paper_id].get("pdf_url")),
            license=_optional_str(records[paper_id].get("license")),
            lexical_rank=lexical_ranks.get(paper_id),
            semantic_rank=semantic_ranks.get(paper_id),
            fused_score=scores[paper_id],
        )
        for paper_id in ordered_ids
    ]


def _optional_str(value: object | None) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: object | None) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return None


def _optional_date(value: object | None) -> date | None:
    return value if isinstance(value, date) else None


def _broad_websearch_query(query: str) -> str:
    """Favor recall for the lexical leg before RRF fusion.

    PostgreSQL websearch syntax joins bare terms with AND. For literature
    discovery that was too restrictive (for example, `AI adoption firm
    performance` required every token to occur in the same record). The
    semantic leg already supplies precision, so lexical retrieval uses an OR
    pool and lets ts_rank_cd plus RRF determine ordering.
    """
    tokens = [token for token in query.split() if token.strip()]
    return " OR ".join(tokens) if tokens else query

