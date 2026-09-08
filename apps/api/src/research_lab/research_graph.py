from __future__ import annotations

import base64
import json
import math
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import Settings, get_settings
from research_lab.models import CitationSnapshot, Paper
from research_lab.retrieval import HybridRetrievalService, RankedPaper, SearchFilters, SearchMode, SearchScope, SortMode

GraphMode = Literal["off", "auto", "on"]


@dataclass(frozen=True, slots=True)
class GraphHealth:
    enabled: bool
    available: bool
    provider: str
    latency_ms: float | None = None
    detail: str | None = None


@dataclass(slots=True)
class GraphPaperCandidate:
    paper_id: uuid.UUID
    distance: int | None = None
    page_rank: float = 0.0
    citation_paths: int = 0
    shared_topics: int = 0
    shared_authors: int = 0
    shared_institutions: int = 0
    same_community: bool = False
    reasons: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class GraphRetrievalTrace:
    requested_mode: GraphMode
    applied: bool
    provider: str
    seed_count: int
    expansion_count: int
    returned_graph_only_count: int
    latency_ms: float
    fallback_reason: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GraphRetrievalResult:
    rows: list[RankedPaper]
    trace: GraphRetrievalTrace


@dataclass(frozen=True, slots=True)
class GraphExpansionResult:
    candidates: list[GraphPaperCandidate]
    warnings: tuple[str, ...] = ()


class GraphQueryProvider(Protocol):
    name: str

    def run(self, statement: str, parameters: Mapping[str, object] | None = None) -> list[dict[str, object]]: ...


class Neo4jHttpGraphProvider:
    name = "neo4j_http"

    def __init__(
        self,
        uri: str,
        *,
        username: str,
        password: str,
        timeout_seconds: float,
    ) -> None:
        self.uri = uri.rstrip("/")
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds

    def run(self, statement: str, parameters: Mapping[str, object] | None = None) -> list[dict[str, object]]:
        payload = json.dumps(
            {"statements": [{"statement": statement, "parameters": dict(parameters or {})}]}
        ).encode("utf-8")
        credentials = base64.b64encode(f"{self.username}:{self.password}".encode()).decode("ascii")
        request = urllib.request.Request(
            f"{self.uri}/db/neo4j/tx/commit",
            data=payload,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.load(response)
        except (TimeoutError, OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise RuntimeError(f"Neo4j graph provider unavailable: {type(exc).__name__}") from exc

        errors = body.get("errors") or []
        if errors:
            code = errors[0].get("code", "Neo4jError") if isinstance(errors[0], dict) else "Neo4jError"
            raise RuntimeError(f"Neo4j graph query failed: {code}")
        results = body.get("results") or []
        if not results:
            return []
        first = results[0]
        columns = first.get("columns") or []
        rows: list[dict[str, object]] = []
        for item in first.get("data") or []:
            values = item.get("row") or []
            rows.append(dict(zip(columns, values, strict=False)))
        return rows


class ResearchGraphService:
    """Read-only graph intelligence over a rebuildable Neo4j projection.

    Canonical paper metadata and evidence always remain in PostgreSQL. Methods
    return canonical paper UUIDs and graph-derived ranking signals only.
    """

    def __init__(self, provider: GraphQueryProvider, *, result_cap: int = 80) -> None:
        self.provider = provider
        self.result_cap = result_cap

    def health(self) -> GraphHealth:
        started = time.perf_counter()
        try:
            rows = self.provider.run("RETURN 1 AS ok")
            available = bool(rows and rows[0].get("ok") == 1)
            return GraphHealth(
                enabled=True,
                available=available,
                provider=self.provider.name,
                latency_ms=(time.perf_counter() - started) * 1000,
                detail=None if available else "Graph provider did not return an expected health response.",
            )
        except RuntimeError as exc:
            return GraphHealth(
                enabled=True,
                available=False,
                provider=self.provider.name,
                latency_ms=(time.perf_counter() - started) * 1000,
                detail=str(exc),
            )

    def expand_paper_seeds(
        self,
        seed_ids: Iterable[uuid.UUID],
        *,
        hops: int = 2,
        limit: int | None = None,
    ) -> list[GraphPaperCandidate]:
        return self.expand_paper_seeds_with_trace(seed_ids, hops=hops, limit=limit).candidates

    def expand_paper_seeds_with_trace(
        self,
        seed_ids: Iterable[uuid.UUID],
        *,
        hops: int = 2,
        limit: int | None = None,
    ) -> GraphExpansionResult:
        ids = _uuid_strings(seed_ids)
        if not ids:
            return GraphExpansionResult([])
        seed_id_set = {uuid.UUID(value) for value in ids}
        hops = max(1, min(hops, 2))
        cap = min(limit or self.result_cap, self.result_cap)
        merged: dict[uuid.UUID, GraphPaperCandidate] = {}
        tasks: tuple[tuple[str, Callable[[], list[dict[str, object]]]], ...] = (
            ("citation", lambda: self.citation_neighborhood(ids, hops=hops, limit=cap)),
            ("topic", lambda: self.related_papers(ids, relation="topic", limit=cap)),
            ("author", lambda: self.related_papers(ids, relation="author", limit=cap)),
            ("institution", lambda: self.related_papers(ids, relation="institution", limit=max(10, cap // 2))),
            ("community", lambda: self.related_papers(ids, relation="community", limit=max(10, cap // 2))),
        )
        completed: list[tuple[str, list[dict[str, object]]]] = []
        warnings: list[str] = []
        succeeded = 0
        with ThreadPoolExecutor(max_workers=len(tasks), thread_name_prefix="research-graph") as executor:
            future_to_reason = {executor.submit(task): reason for reason, task in tasks}
            for future in as_completed(future_to_reason):
                reason = future_to_reason[future]
                try:
                    rows = future.result()
                    succeeded += 1
                except RuntimeError as exc:
                    warnings.append(f"{reason}:{exc}")
                    continue
                completed.append((reason, rows))
        if succeeded == 0 and warnings:
            raise RuntimeError("All graph expansion queries failed: " + "; ".join(warnings))

        for reason, rows in completed:
            for row in rows:
                candidate = _candidate_from_row(row)
                if candidate.paper_id in seed_id_set:
                    continue
                current = merged.get(candidate.paper_id)
                if current is None:
                    current = candidate
                    merged[candidate.paper_id] = current
                else:
                    _merge_candidate(current, candidate)
                current.reasons.add(reason)
        ordered = sorted(
            merged.values(),
            key=lambda row: (
                -(graph_signal_score(row)),
                row.distance if row.distance is not None else 99,
                -row.page_rank,
                str(row.paper_id),
            ),
        )
        return GraphExpansionResult(ordered[:cap], tuple(sorted(warnings)))

    def citation_neighborhood(
        self,
        seed_ids: Iterable[str | uuid.UUID],
        *,
        hops: int = 2,
        limit: int = 80,
    ) -> list[dict[str, object]]:
        ids = _uuid_strings(seed_ids)
        hops = max(1, min(hops, 2))
        statement = f"""
        UNWIND $seed_ids AS seed_id
        MATCH (seed:Paper {{paper_id: seed_id}})
        MATCH path=(seed)-[:CITES*1..{hops}]-(candidate:Paper)
        WHERE NOT candidate.paper_id IN $seed_ids
        WITH candidate, min(length(path)) AS distance, count(*) AS citation_paths
        RETURN candidate.paper_id AS paper_id,
               distance,
               citation_paths,
               coalesce(candidate.citationPageRank, 0.0) AS page_rank,
               candidate.citationCommunity AS community
        ORDER BY distance ASC, page_rank DESC, citation_paths DESC
        LIMIT $limit
        """
        return self.provider.run(statement, {"seed_ids": ids, "limit": min(limit, self.result_cap)})

    def related_papers(
        self,
        seed_ids: Iterable[str | uuid.UUID],
        *,
        relation: Literal["topic", "author", "institution", "community"],
        limit: int = 80,
    ) -> list[dict[str, object]]:
        ids = _uuid_strings(seed_ids)
        cap = min(limit, self.result_cap)
        if relation == "topic":
            statement = """
            UNWIND $seed_ids AS seed_id
            MATCH (seed:Paper {paper_id: seed_id})-[:HAS_TOPIC]->(topic:Topic)<-[:HAS_TOPIC]-(candidate:Paper)
            WHERE NOT candidate.paper_id IN $seed_ids
            WITH candidate, count(DISTINCT topic) AS shared_topics
            RETURN candidate.paper_id AS paper_id, shared_topics,
                   coalesce(candidate.citationPageRank, 0.0) AS page_rank,
                   candidate.citationCommunity AS community
            ORDER BY shared_topics DESC, page_rank DESC
            LIMIT $limit
            """
        elif relation == "author":
            statement = """
            UNWIND $seed_ids AS seed_id
            MATCH (author:Author)-[:AUTHORED]->(seed:Paper {paper_id: seed_id})
            MATCH (author)-[:AUTHORED]->(candidate:Paper)
            WHERE NOT candidate.paper_id IN $seed_ids
            WITH candidate, count(DISTINCT author) AS shared_authors
            RETURN candidate.paper_id AS paper_id, shared_authors,
                   coalesce(candidate.citationPageRank, 0.0) AS page_rank,
                   candidate.citationCommunity AS community
            ORDER BY shared_authors DESC, page_rank DESC
            LIMIT $limit
            """
        elif relation == "institution":
            statement = """
            UNWIND $seed_ids AS seed_id
            MATCH (seed_author:Author)-[:AUTHORED]->(seed:Paper {paper_id: seed_id})
            MATCH (seed_author)-[:AFFILIATED_WITH]->(institution:Institution)<-[:AFFILIATED_WITH]-(author:Author)
            MATCH (author)-[:AUTHORED]->(candidate:Paper)
            WHERE NOT candidate.paper_id IN $seed_ids
            WITH candidate, count(DISTINCT institution) AS shared_institutions
            RETURN candidate.paper_id AS paper_id, shared_institutions,
                   coalesce(candidate.citationPageRank, 0.0) AS page_rank,
                   candidate.citationCommunity AS community
            ORDER BY shared_institutions DESC, page_rank DESC
            LIMIT $limit
            """
        else:
            statement = """
            UNWIND $seed_ids AS seed_id
            MATCH (seed:Paper {paper_id: seed_id})
            WHERE seed.citationCommunity IS NOT NULL
            WITH collect(DISTINCT seed.citationCommunity) AS communities
            MATCH (candidate:Paper)
            WHERE candidate.citationCommunity IN communities
              AND NOT candidate.paper_id IN $seed_ids
            RETURN candidate.paper_id AS paper_id, true AS same_community,
                   coalesce(candidate.citationPageRank, 0.0) AS page_rank,
                   candidate.citationCommunity AS community
            ORDER BY page_rank DESC
            LIMIT $limit
            """
        return self.provider.run(statement, {"seed_ids": ids, "limit": cap})

    def topic_bridges(
        self,
        left_seed_ids: Iterable[uuid.UUID],
        right_seed_ids: Iterable[uuid.UUID],
        *,
        limit: int = 40,
    ) -> list[dict[str, object]]:
        statement = """
        UNWIND $left_ids AS left_id
        MATCH (:Paper {paper_id: left_id})-[:HAS_TOPIC]->(left_topic:Topic)
        WITH collect(DISTINCT left_topic.topic_id) AS left_topics
        UNWIND $right_ids AS right_id
        MATCH (:Paper {paper_id: right_id})-[:HAS_TOPIC]->(right_topic:Topic)
        WITH left_topics, collect(DISTINCT right_topic.topic_id) AS right_topics
        MATCH (candidate:Paper)-[:HAS_TOPIC]->(lt:Topic)
        WHERE lt.topic_id IN left_topics
        WITH right_topics, candidate, count(DISTINCT lt) AS left_shared
        MATCH (candidate)-[:HAS_TOPIC]->(rt:Topic)
        WHERE rt.topic_id IN right_topics
        RETURN candidate.paper_id AS paper_id, left_shared,
               count(DISTINCT rt) AS right_shared,
               coalesce(candidate.citationPageRank, 0.0) AS page_rank
        ORDER BY (left_shared + right_shared) DESC, page_rank DESC
        LIMIT $limit
        """
        return self.provider.run(
            statement,
            {
                "left_ids": _uuid_strings(left_seed_ids),
                "right_ids": _uuid_strings(right_seed_ids),
                "limit": min(limit, self.result_cap),
            },
        )

    def community_lookup(self, paper_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
        rows = self.provider.run(
            """
            UNWIND $paper_ids AS paper_id
            MATCH (paper:Paper {paper_id: paper_id})
            RETURN paper.paper_id AS paper_id, paper.citationCommunity AS community
            """,
            {"paper_ids": _uuid_strings(paper_ids)},
        )
        communities: dict[uuid.UUID, int] = {}
        for row in rows:
            paper_id = row.get("paper_id")
            community = _int_or_none(row.get("community"))
            if paper_id and community is not None:
                communities[uuid.UUID(str(paper_id))] = community
        return communities

    def pagerank_lookup(self, paper_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, float]:
        rows = self.provider.run(
            """
            UNWIND $paper_ids AS paper_id
            MATCH (paper:Paper {paper_id: paper_id})
            RETURN paper.paper_id AS paper_id, coalesce(paper.citationPageRank, 0.0) AS page_rank
            """,
            {"paper_ids": _uuid_strings(paper_ids)},
        )
        return {
            uuid.UUID(str(row["paper_id"])): _float_or_zero(row.get("page_rank"))
            for row in rows
            if row.get("paper_id")
        }


class GraphAugmentedRetrievalService:
    def __init__(
        self,
        session: Session,
        baseline: HybridRetrievalService,
        graph: ResearchGraphService | None,
    ) -> None:
        self.session = session
        self.baseline = baseline
        self.graph = graph

    def search(
        self,
        query: str,
        *,
        graph_mode: GraphMode,
        mode: SearchMode = "hybrid",
        scope: SearchScope = "all",
        sort: SortMode = "relevance",
        limit: int = 20,
        filters: SearchFilters | None = None,
        seed_limit: int = 12,
        hops: int = 2,
    ) -> GraphRetrievalResult:
        started = time.perf_counter()
        baseline_rows = self.baseline.search(
            query,
            mode=mode,
            scope=scope,
            sort=sort,
            limit=max(limit, seed_limit),
            filters=filters,
        )
        if graph_mode == "off" or self.graph is None:
            reason = None if graph_mode == "off" else "graph_not_configured"
            return GraphRetrievalResult(
                rows=baseline_rows[:limit],
                trace=GraphRetrievalTrace(
                    requested_mode=graph_mode,
                    applied=False,
                    provider=self.graph.provider.name if self.graph is not None else "none",
                    seed_count=min(len(baseline_rows), seed_limit),
                    expansion_count=0,
                    returned_graph_only_count=0,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    fallback_reason=reason,
                ),
            )

        health = self.graph.health()
        if not health.available:
            return GraphRetrievalResult(
                rows=baseline_rows[:limit],
                trace=GraphRetrievalTrace(
                    requested_mode=graph_mode,
                    applied=False,
                    provider=health.provider,
                    seed_count=min(len(baseline_rows), seed_limit),
                    expansion_count=0,
                    returned_graph_only_count=0,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    fallback_reason=health.detail or "graph_unavailable",
                ),
            )

        seed_rows = baseline_rows[:seed_limit]
        try:
            expansion = self.graph.expand_paper_seeds_with_trace([row.id for row in seed_rows], hops=hops)
            expanded = expansion.candidates
        except RuntimeError as exc:
            return GraphRetrievalResult(
                rows=baseline_rows[:limit],
                trace=GraphRetrievalTrace(
                    requested_mode=graph_mode,
                    applied=False,
                    provider=self.graph.provider.name,
                    seed_count=len(seed_rows),
                    expansion_count=0,
                    returned_graph_only_count=0,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    fallback_reason=str(exc),
                ),
            )

        ranked = self._merge_canonical(baseline_rows, expanded, limit=limit)
        baseline_ids = {row.id for row in baseline_rows}
        graph_only = sum(1 for row in ranked if row.id not in baseline_ids)
        return GraphRetrievalResult(
            rows=ranked,
            trace=GraphRetrievalTrace(
                requested_mode=graph_mode,
                applied=True,
                provider=self.graph.provider.name,
                seed_count=len(seed_rows),
                expansion_count=len(expanded),
                returned_graph_only_count=graph_only,
                latency_ms=(time.perf_counter() - started) * 1000,
                warnings=expansion.warnings,
            ),
        )

    def _merge_canonical(
        self,
        baseline_rows: list[RankedPaper],
        expanded: list[GraphPaperCandidate],
        *,
        limit: int,
    ) -> list[RankedPaper]:
        baseline_by_id = {row.id: row for row in baseline_rows}
        expanded_ids = [candidate.paper_id for candidate in expanded if candidate.paper_id not in baseline_by_id]
        papers = self.session.scalars(select(Paper).where(Paper.id.in_(expanded_ids))).all() if expanded_ids else []
        canonical = {paper.id: paper for paper in papers}
        citation_counts = _latest_citation_counts(self.session, expanded_ids)
        max_graph_signal = max((graph_signal_score(candidate) for candidate in expanded), default=1.0) or 1.0

        scored: list[tuple[float, RankedPaper]] = []
        for row in baseline_rows:
            candidate = next((item for item in expanded if item.paper_id == row.id), None)
            bonus = 0.0
            if candidate is not None:
                bonus = 0.0035 * (graph_signal_score(candidate) / max_graph_signal)
            scored.append((row.fused_score + bonus, replace(row, fused_score=row.fused_score + bonus)))

        for candidate in expanded:
            if candidate.paper_id in baseline_by_id:
                continue
            paper = canonical.get(candidate.paper_id)
            if paper is None:
                continue
            normalized = graph_signal_score(candidate) / max_graph_signal
            graph_fused_score = 0.0055 + (0.008 * normalized)
            reason = ",".join(sorted(candidate.reasons)) or "graph"
            scored.append(
                (
                    graph_fused_score,
                    RankedPaper(
                        id=paper.id,
                        doi=paper.doi,
                        openalex_id=paper.openalex_id,
                        title=paper.title,
                        abstract=paper.abstract,
                        publication_date=paper.publication_date,
                        publication_year=paper.publication_year,
                        work_type=paper.work_type,
                        venue_name=paper.venue.name if paper.venue is not None else None,
                        oa_status=paper.oa_status,
                        is_oa=paper.is_oa,
                        primary_url=paper.primary_url,
                        pdf_url=paper.pdf_url,
                        license=paper.license,
                        lexical_rank=None,
                        semantic_rank=None,
                        fused_score=graph_fused_score,
                        rerank_score=None,
                        matched_source="graph_expansion",
                        matched_locator=(
                            f"graph:{reason};distance={candidate.distance if candidate.distance is not None else 'n/a'}"
                        ),
                        matched_excerpt=(paper.abstract or paper.title)[:600],
                        citation_count=citation_counts.get(paper.id, 0),
                        reading_priority=0,
                    ),
                )
            )
        scored.sort(key=lambda item: (-item[0], str(item[1].id)))
        return [row for _, row in scored[:limit]]


def build_research_graph_service(settings: Settings | None = None) -> ResearchGraphService | None:
    settings = settings or get_settings()
    if not settings.research_graph_enabled or not settings.research_graph_password:
        return None
    provider = Neo4jHttpGraphProvider(
        settings.research_graph_uri,
        username=settings.research_graph_username,
        password=settings.research_graph_password,
        timeout_seconds=settings.research_graph_timeout_seconds,
    )
    return ResearchGraphService(provider, result_cap=settings.research_graph_result_cap)


def graph_signal_score(candidate: GraphPaperCandidate) -> float:
    distance_weight = 1.0 / max(candidate.distance or 3, 1)
    return (
        0.28 * distance_weight
        + 0.20 * min(math.log1p(candidate.citation_paths), 3.0) / 3.0
        + 0.18 * min(candidate.shared_topics, 4) / 4.0
        + 0.12 * min(candidate.shared_authors, 2) / 2.0
        + 0.05 * min(candidate.shared_institutions, 2) / 2.0
        + 0.12 * float(candidate.same_community)
        + 0.05 * min(math.log1p(max(candidate.page_rank, 0.0)), 4.0) / 4.0
    )


def _candidate_from_row(row: Mapping[str, object]) -> GraphPaperCandidate:
    return GraphPaperCandidate(
        paper_id=uuid.UUID(str(row["paper_id"])),
        distance=_int_or_none(row.get("distance")),
        page_rank=_float_or_zero(row.get("page_rank")),
        citation_paths=_int_or_zero(row.get("citation_paths")),
        shared_topics=_int_or_zero(row.get("shared_topics")),
        shared_authors=_int_or_zero(row.get("shared_authors")),
        shared_institutions=_int_or_zero(row.get("shared_institutions")),
        same_community=bool(row.get("same_community")),
    )


def _merge_candidate(target: GraphPaperCandidate, incoming: GraphPaperCandidate) -> None:
    distances = [value for value in (target.distance, incoming.distance) if value is not None]
    target.distance = min(distances) if distances else None
    target.page_rank = max(target.page_rank, incoming.page_rank)
    target.citation_paths += incoming.citation_paths
    target.shared_topics = max(target.shared_topics, incoming.shared_topics)
    target.shared_authors = max(target.shared_authors, incoming.shared_authors)
    target.shared_institutions = max(target.shared_institutions, incoming.shared_institutions)
    target.same_community = target.same_community or incoming.same_community
    target.reasons.update(incoming.reasons)


def _uuid_strings(values: Iterable[str | uuid.UUID]) -> list[str]:
    return [str(uuid.UUID(str(value))) for value in values]


def _int_or_none(value: object | None) -> int | None:
    return int(str(value)) if value is not None else None


def _int_or_zero(value: object | None) -> int:
    return _int_or_none(value) or 0


def _float_or_zero(value: object | None) -> float:
    return float(str(value)) if value is not None else 0.0


def _latest_citation_counts(session: Session, paper_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not paper_ids:
        return {}
    rows = session.execute(
        select(CitationSnapshot.paper_id, CitationSnapshot.citation_count)
        .where(CitationSnapshot.paper_id.in_(paper_ids))
        .order_by(CitationSnapshot.paper_id, CitationSnapshot.captured_at.desc())
    ).all()
    counts: dict[uuid.UUID, int] = {}
    for paper_id, citation_count in rows:
        counts.setdefault(paper_id, citation_count)
    return counts
