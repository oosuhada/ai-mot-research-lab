from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from research_lab.config import get_settings
from research_lab.embeddings import EmbeddingProvider, build_embedding_provider

SearchMode = Literal["lexical", "vector", "hybrid"]
SearchScope = Literal["metadata", "abstract", "full_text", "all"]
SortMode = Literal["relevance", "newest", "citation_count", "reading_priority"]


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
    reading_status: str | None = None
    tag: str | None = None


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
    venue_name: str | None
    oa_status: str | None
    is_oa: bool
    primary_url: str | None
    pdf_url: str | None
    license: str | None
    lexical_rank: int | None
    semantic_rank: int | None
    fused_score: float
    rerank_score: float | None
    matched_source: str
    matched_locator: str | None
    matched_excerpt: str | None
    citation_count: int
    reading_priority: int


class HybridRetrievalService:
    def __init__(
        self,
        session: Session,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.session = session
        self.embedding_provider = embedding_provider or build_embedding_provider(get_settings())

    def search(
        self,
        query: str,
        *,
        mode: SearchMode = "hybrid",
        scope: SearchScope = "all",
        sort: SortMode = "relevance",
        limit: int = 20,
        filters: SearchFilters | None = None,
    ) -> list[RankedPaper]:
        filters = filters or SearchFilters()
        candidate_limit = 100

        lexical = (
            self._lexical_search(query, candidate_limit, filters, scope)
            if mode in {"lexical", "hybrid"}
            else []
        )
        vector = (
            self._vector_search(query, candidate_limit, filters, scope)
            if mode in {"vector", "hybrid"}
            else []
        )

        fused = reciprocal_rank_fusion(lexical, vector, limit=candidate_limit)
        return _sort_results(fused, sort)[:limit]

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
        if filters.reading_status:
            clauses.append(
                "EXISTS (SELECT 1 FROM reading_queue rq WHERE rq.paper_id = p.id AND rq.status = :reading_status)"
            )
            params["reading_status"] = filters.reading_status
        if filters.tag:
            clauses.append(
                "EXISTS ("
                "SELECT 1 FROM paper_tags ptag JOIN tags tag ON tag.id = ptag.tag_id "
                "WHERE ptag.paper_id = p.id AND tag.name ILIKE :tag"
                ")"
            )
            params["tag"] = f"%{filters.tag}%"

        return (" AND ".join(clauses) if clauses else "TRUE"), params

    def _lexical_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
        scope: SearchScope,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        if scope in {"metadata", "abstract", "all"}:
            rows.extend(self._paper_lexical_search(query, limit, filters, scope))
        if scope in {"full_text", "all"}:
            rows.extend(self._chunk_lexical_search(query, limit, filters))
        return _merge_candidates(rows, "lexical_score", reverse=True, limit=limit)

    def _paper_lexical_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
        scope: SearchScope,
    ) -> list[dict[str, object]]:
        filter_sql, params = self._filter_sql(filters)
        params.update({"query": _broad_websearch_query(query), "limit": limit})
        if scope == "metadata":
            vector_sql = "to_tsvector('simple', coalesce(p.title, ''))"
            matched_source = "metadata"
        elif scope == "abstract":
            vector_sql = "to_tsvector('simple', coalesce(p.abstract, ''))"
            matched_source = "abstract"
        else:
            vector_sql = "p.search_vector"
            matched_source = "abstract"
        params["matched_source"] = matched_source
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
                (SELECT v.name FROM venues v WHERE v.id = p.venue_id LIMIT 1) AS venue_name,
                p.oa_status,
                p.is_oa,
                p.primary_url,
                p.pdf_url,
                p.license,
                ts_rank_cd({vector_sql}, q.tsq) AS lexical_score,
                :matched_source AS matched_source,
                CASE WHEN :matched_source = 'abstract' THEN 'abstract' ELSE 'metadata:title' END AS matched_locator,
                CASE
                    WHEN :matched_source = 'abstract' THEN left(p.abstract, 600)
                    ELSE left(p.title, 600)
                END AS matched_excerpt,
                COALESCE((
                    SELECT cs.citation_count
                    FROM citation_snapshots cs
                    WHERE cs.paper_id = p.id
                    ORDER BY cs.captured_at DESC
                    LIMIT 1
                ), 0) AS citation_count,
                COALESCE((
                    SELECT rq.priority FROM reading_queue rq
                    WHERE rq.paper_id = p.id LIMIT 1
                ), 0) AS reading_priority
            FROM papers p
            CROSS JOIN q
            WHERE {vector_sql} @@ q.tsq
              AND {filter_sql}
            ORDER BY lexical_score DESC, p.publication_year DESC NULLS LAST, p.id
            LIMIT :limit
            """
        )
        rows = self.session.execute(statement, params).mappings().all()
        return [dict(row) for row in rows]

    def _chunk_lexical_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
    ) -> list[dict[str, object]]:
        filter_sql, params = self._filter_sql(filters)
        params.update({"query": _broad_websearch_query(query), "limit": limit})
        statement = text(
            f"""
            WITH q AS (SELECT websearch_to_tsquery('simple', :query) AS tsq),
            ranked AS (
              SELECT p.id, p.doi, p.openalex_id, p.title, p.abstract, p.publication_date,
                     p.publication_year, p.work_type,
                     (SELECT v.name FROM venues v WHERE v.id = p.venue_id LIMIT 1) AS venue_name,
                     p.oa_status, p.is_oa, p.primary_url,
                     p.pdf_url, p.license, pc.source_locator AS matched_locator,
                     left(pc.text, 600) AS matched_excerpt,
                     ts_rank_cd(to_tsvector('simple', pc.text), q.tsq) AS lexical_score,
                     COALESCE((
                       SELECT cs.citation_count FROM citation_snapshots cs
                       WHERE cs.paper_id = p.id ORDER BY cs.captured_at DESC LIMIT 1
                     ), 0) AS citation_count,
                     COALESCE((
                       SELECT rq.priority FROM reading_queue rq
                       WHERE rq.paper_id = p.id LIMIT 1
                     ), 0) AS reading_priority,
                     row_number() OVER (
                       PARTITION BY p.id ORDER BY ts_rank_cd(to_tsvector('simple', pc.text), q.tsq) DESC, pc.id
                     ) AS rn
              FROM paper_chunks pc
              JOIN papers p ON p.id = pc.paper_id
              CROSS JOIN q
              WHERE to_tsvector('simple', pc.text) @@ q.tsq AND {filter_sql}
            )
            SELECT *, 'full_text_chunk' AS matched_source FROM ranked
            WHERE rn = 1
            ORDER BY lexical_score DESC, publication_year DESC NULLS LAST, id
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
        scope: SearchScope,
    ) -> list[dict[str, object]]:
        self._enable_filtered_hnsw_scan()
        rows: list[dict[str, object]] = []
        if scope in {"metadata", "abstract", "all"}:
            rows.extend(self._paper_vector_search(query, limit, filters))
        if scope in {"full_text", "all"}:
            rows.extend(self._chunk_vector_search(query, limit, filters))
        return _merge_candidates(rows, "vector_distance", reverse=False, limit=limit)

    def _paper_vector_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
    ) -> list[dict[str, object]]:
        filter_sql, params = self._filter_sql(filters)
        vector = self.embedding_provider.embed_query(query)
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
                (SELECT v.name FROM venues v WHERE v.id = p.venue_id LIMIT 1) AS venue_name,
                p.oa_status,
                p.is_oa,
                p.primary_url,
                p.pdf_url,
                p.license,
                (pe.embedding <=> CAST(:embedding AS vector)) AS vector_distance,
                'paper_embedding' AS matched_source,
                'title + abstract embedding' AS matched_locator,
                left(COALESCE(p.abstract, p.title), 600) AS matched_excerpt,
                COALESCE((
                    SELECT cs.citation_count FROM citation_snapshots cs
                    WHERE cs.paper_id = p.id ORDER BY cs.captured_at DESC LIMIT 1
                ), 0) AS citation_count,
                COALESCE((
                    SELECT rq.priority FROM reading_queue rq
                    WHERE rq.paper_id = p.id LIMIT 1
                ), 0) AS reading_priority
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

    def _enable_filtered_hnsw_scan(self) -> None:
        """Allow pgvector to scan past filtered-out HNSW candidates in strict distance order."""
        self.session.execute(text("SET LOCAL hnsw.iterative_scan = 'strict_order'"))

    def _chunk_vector_search(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
    ) -> list[dict[str, object]]:
        filter_sql, params = self._filter_sql(filters)
        vector = self.embedding_provider.embed_query(query)
        params.update({"embedding": str(vector), "limit": limit})
        statement = text(
            f"""
            WITH ranked AS (
              SELECT p.id, p.doi, p.openalex_id, p.title, p.abstract, p.publication_date,
                     p.publication_year, p.work_type,
                     (SELECT v.name FROM venues v WHERE v.id = p.venue_id LIMIT 1) AS venue_name,
                     p.oa_status, p.is_oa, p.primary_url,
                     p.pdf_url, p.license, pc.source_locator AS matched_locator,
                     left(pc.text, 600) AS matched_excerpt,
                     (pc.embedding <=> CAST(:embedding AS vector)) AS vector_distance,
                     COALESCE((
                       SELECT cs.citation_count FROM citation_snapshots cs
                       WHERE cs.paper_id = p.id ORDER BY cs.captured_at DESC LIMIT 1
                     ), 0) AS citation_count,
                     COALESCE((
                       SELECT rq.priority FROM reading_queue rq
                       WHERE rq.paper_id = p.id LIMIT 1
                     ), 0) AS reading_priority,
                     row_number() OVER (
                       PARTITION BY p.id ORDER BY pc.embedding <=> CAST(:embedding AS vector), pc.id
                     ) AS rn
              FROM paper_chunks pc
              JOIN papers p ON p.id = pc.paper_id
              WHERE pc.embedding IS NOT NULL AND {filter_sql}
            )
            SELECT *, 'full_text_chunk' AS matched_source FROM ranked
            WHERE rn = 1
            ORDER BY vector_distance, id
            LIMIT :limit
            """
        )
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
            venue_name=_optional_str(records[paper_id].get("venue_name")),
            oa_status=_optional_str(records[paper_id].get("oa_status")),
            is_oa=bool(records[paper_id].get("is_oa")),
            primary_url=_optional_str(records[paper_id].get("primary_url")),
            pdf_url=_optional_str(records[paper_id].get("pdf_url")),
            license=_optional_str(records[paper_id].get("license")),
            lexical_rank=lexical_ranks.get(paper_id),
            semantic_rank=semantic_ranks.get(paper_id),
            fused_score=scores[paper_id],
            rerank_score=None,
            matched_source=_optional_str(records[paper_id].get("matched_source")) or "paper",
            matched_locator=_optional_str(records[paper_id].get("matched_locator")),
            matched_excerpt=_optional_str(records[paper_id].get("matched_excerpt")),
            citation_count=_optional_int(records[paper_id].get("citation_count")) or 0,
            reading_priority=_optional_int(records[paper_id].get("reading_priority")) or 0,
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


def _merge_candidates(
    rows: list[dict[str, object]],
    score_key: str,
    *,
    reverse: bool,
    limit: int,
) -> list[dict[str, object]]:
    def score(row: dict[str, object]) -> float:
        value = row.get(score_key)
        return float(value) if isinstance(value, (int, float)) else (float("-inf") if reverse else float("inf"))

    ordered = sorted(rows, key=score, reverse=reverse)
    seen: set[str] = set()
    merged: list[dict[str, object]] = []
    for row in ordered:
        key = str(row.get("id"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= limit:
            break
    return merged


def _sort_results(rows: list[RankedPaper], sort: SortMode) -> list[RankedPaper]:
    if sort == "newest":
        return sorted(rows, key=lambda row: (row.publication_year or 0, row.fused_score), reverse=True)
    if sort == "citation_count":
        return sorted(rows, key=lambda row: (row.citation_count, row.fused_score), reverse=True)
    if sort == "reading_priority":
        return sorted(rows, key=lambda row: (row.reading_priority, row.fused_score), reverse=True)
    return rows

