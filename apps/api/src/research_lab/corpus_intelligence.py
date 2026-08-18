from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from research_lab.models import (
    CitationSnapshot,
    DailyDiscoveryEvent,
    FullTextQueueItem,
    IngestionRun,
    Paper,
    PaperChunk,
    PaperContentProfile,
    PaperLocalization,
    PaperTopic,
    ResearchOpportunity,
    Topic,
    Venue,
)
from research_lab.schemas import (
    CorpusCoverageResponse,
    FullTextQueuePaper,
    FullTextQueueResponse,
    ResearchOpportunitiesResponse,
    ResearchOpportunityResponse,
    WhatsNewItem,
    WhatsNewResponse,
)


def get_corpus_coverage(session: Session) -> CorpusCoverageResponse:
    total = session.scalar(select(func.count()).select_from(Paper)) or 0
    abstract_ready = session.scalar(
        select(func.count()).select_from(Paper).where(
            Paper.abstract.is_not(None),
            func.length(func.trim(Paper.abstract)) > 0,
        )
    ) or 0
    full_text_ready = session.scalar(select(func.count(func.distinct(PaperChunk.paper_id)))) or 0
    full_text_queued = session.scalar(
        select(func.count()).select_from(FullTextQueueItem).where(
            FullTextQueueItem.status.in_(["pending", "processing"])
        )
    ) or 0
    full_text_restricted = session.scalar(
        select(func.count()).select_from(PaperContentProfile).where(
            PaperContentProfile.full_text_status == "restricted"
        )
    ) or 0
    translated_ko = session.scalar(
        select(func.count()).select_from(PaperLocalization).where(
            PaperLocalization.locale == "ko",
            PaperLocalization.status == "completed",
        )
    ) or 0
    expansion_totals = session.execute(
        select(
            func.coalesce(func.sum(IngestionRun.fetched_count), 0),
            func.coalesce(func.sum(IngestionRun.accepted_count), 0),
            func.coalesce(func.sum(IngestionRun.inserted_count), 0),
            func.coalesce(func.sum(IngestionRun.updated_count), 0),
        ).where(IngestionRun.source == "openalex_expansion")
    ).one()
    expansion_target_total = 100_000
    return CorpusCoverageResponse(
        total_records=total,
        metadata_only=max(total - abstract_ready, 0),
        abstract_ready=abstract_ready,
        full_text_ready=full_text_ready,
        full_text_queued=full_text_queued,
        full_text_restricted=full_text_restricted,
        translated_ko=translated_ko,
        expansion_target_total=expansion_target_total,
        expansion_progress_pct=round(min(total / expansion_target_total, 1.0) * 100, 3),
        expansion_fetched_total=int(expansion_totals[0] or 0),
        expansion_accepted_total=int(expansion_totals[1] or 0),
        expansion_inserted_total=int(expansion_totals[2] or 0),
        expansion_updated_total=int(expansion_totals[3] or 0),
    )


def get_full_text_queue(session: Session, *, limit: int = 20) -> FullTextQueueResponse:
    count_rows = session.execute(
        select(FullTextQueueItem.status, func.count(FullTextQueueItem.id)).group_by(
            FullTextQueueItem.status
        )
    ).all()
    counts: dict[str, int] = {status: int(count) for status, count in count_rows}
    rows = session.execute(
        select(FullTextQueueItem, Paper.title)
        .join(Paper, Paper.id == FullTextQueueItem.paper_id)
        .where(FullTextQueueItem.status.in_(["pending", "processing"]))
        .order_by(desc(FullTextQueueItem.priority), FullTextQueueItem.created_at)
        .limit(limit)
    ).all()
    return FullTextQueueResponse(
        pending=int(counts.get("pending", 0)),
        processing=int(counts.get("processing", 0)),
        completed=int(counts.get("completed", 0)),
        restricted=int(counts.get("restricted", 0)),
        failed=int(counts.get("failed", 0)),
        items=[
            FullTextQueuePaper(
                paper_id=item.paper_id,
                title=title,
                priority=item.priority,
                status=item.status,
                rights_status=item.rights_status,
                reason_factors=item.reason_factors,
            )
            for item, title in rows
        ],
    )


def list_whats_new(session: Session, *, days: int = 7, limit: int = 30) -> WhatsNewResponse:
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    publication_cutoff = cutoff.date()
    publication_through = now.date()
    raw_event_rows = session.execute(
        select(DailyDiscoveryEvent, Paper, Venue.name)
        .join(Paper, Paper.id == DailyDiscoveryEvent.paper_id)
        .outerjoin(Venue, Venue.id == Paper.venue_id)
        .where(
            DailyDiscoveryEvent.created_at >= cutoff,
            Paper.publication_date >= publication_cutoff,
            Paper.publication_date <= publication_through,
        )
        .order_by(
            desc(Paper.publication_date),
            desc(DailyDiscoveryEvent.relevance_score + DailyDiscoveryEvent.novelty_score),
            desc(DailyDiscoveryEvent.created_at),
        )
        .limit(limit)
    ).all()
    event_rows: list[tuple[DailyDiscoveryEvent, Paper, str | None]] = [
        (event, paper, venue_name) for event, paper, venue_name in raw_event_rows
    ]

    if not event_rows:
        paper_rows = session.execute(
            select(Paper, Venue.name)
            .outerjoin(Venue, Venue.id == Paper.venue_id)
            .where(
                Paper.publication_date >= publication_cutoff,
                Paper.publication_date <= publication_through,
            )
            .order_by(desc(Paper.publication_date), desc(Paper.retrieved_at), Paper.id)
            .limit(limit)
        ).all()
        event_rows = [
            (
                DailyDiscoveryEvent(
                    paper_id=paper.id,
                    event_kind="newly_discovered",
                    event_date=paper.retrieved_at.date(),
                    relevance_score=0.6,
                    novelty_score=0.5,
                    created_at=paper.retrieved_at,
                    updated_at=paper.retrieved_at,
                ),
                paper,
                venue_name,
            )
            for paper, venue_name in paper_rows
        ]

    paper_ids = [paper.id for _, paper, _ in event_rows]
    topic_map: dict[uuid.UUID, list[str]] = {paper_id: [] for paper_id in paper_ids}
    if paper_ids:
        for paper_id, display_name in session.execute(
            select(PaperTopic.paper_id, Topic.display_name)
            .join(Topic, Topic.id == PaperTopic.topic_id)
            .where(
                PaperTopic.paper_id.in_(paper_ids),
                Topic.kind.in_(["research_axis", "research_subaxis"]),
            )
            .order_by(Topic.kind, Topic.display_name)
        ):
            topic_map[paper_id].append(display_name)
    full_text_ids = set(
        session.scalars(select(PaperChunk.paper_id).where(PaperChunk.paper_id.in_(paper_ids)).distinct())
    )

    items = []
    for event, paper, venue_name in event_rows:
        depth = cast(
            Literal["metadata", "abstract", "full_text"],
            "full_text" if paper.id in full_text_ids else "abstract" if paper.abstract else "metadata",
        )
        topics = topic_map.get(paper.id, [])[:4]
        why = event.summary or _why_it_matters(paper, topics, depth)
        items.append(
            WhatsNewItem(
                paper_id=paper.id,
                title=paper.title,
                abstract=paper.abstract,
                publication_date=paper.publication_date,
                publication_year=paper.publication_year,
                venue_name=venue_name,
                event_kind=event.event_kind,
                detected_at=event.created_at,
                relevance_score=event.relevance_score,
                novelty_score=event.novelty_score,
                evidence_depth=depth,
                is_oa=paper.is_oa,
                topics=topics,
                why_it_matters=why,
            )
        )
    return WhatsNewResponse(window_days=days, generated_at=now, items=items)


def list_research_opportunities(session: Session, *, limit: int = 12) -> ResearchOpportunitiesResponse:
    now = datetime.now(UTC)
    stored = list(
        session.scalars(
            select(ResearchOpportunity)
            .order_by(ResearchOpportunity.coverage_count, desc(ResearchOpportunity.adjacent_count))
            .limit(limit)
        )
    )
    if not stored:
        stored = _compute_opportunities(session, now)
    coverage = get_corpus_coverage(session)
    limitations = [
        "These are corpus-coverage signals, not confirmed gaps in the scholarly field.",
        f"Only {coverage.full_text_ready} of {coverage.total_records} records currently have full-text evidence.",
        "Keyword-derived sub-areas and methodology labels are system inference.",
    ]
    return ResearchOpportunitiesResponse(
        generated_at=now,
        corpus_limitations=limitations,
        items=[_opportunity_response(item) for item in stored[:limit]],
    )


def refresh_corpus_intelligence(
    session: Session,
    *,
    discovery_days: int = 2,
    create_discovery_events: bool = True,
) -> dict[str, int]:
    now = datetime.now(UTC)
    papers = list(session.scalars(select(Paper)))
    profiles_upserted = 0
    queue_upserted = 0
    events_upserted = 0

    citation_counts = {
        paper_id: count
        for paper_id, count in session.execute(
            select(CitationSnapshot.paper_id, func.max(CitationSnapshot.citation_count)).group_by(
                CitationSnapshot.paper_id
            )
        )
    }
    full_text_ids = set(session.scalars(select(PaperChunk.paper_id).distinct()))
    for paper in papers:
        abstract_ready = bool(paper.abstract and paper.abstract.strip())
        full_text_ready = paper.id in full_text_ids
        profile = session.get(PaperContentProfile, paper.id)
        if profile is None:
            profile = PaperContentProfile(paper_id=paper.id)
            session.add(profile)
            profiles_upserted += 1
        profile.abstract_status = "available" if abstract_ready else "missing"
        profile.abstract_updated_at = paper.updated_at if abstract_ready else None
        if full_text_ready:
            profile.full_text_status = "available"
            profile.full_text_updated_at = paper.updated_at
        elif paper.is_oa and paper.pdf_url:
            profile.full_text_status = "queued"
            profile.full_text_access = "open_access"
            profile.rights_status = "open_access"
            priority = min(100, 50 + min(citation_counts.get(paper.id, 0), 25) + (10 if abstract_ready else 0))
            profile.full_text_priority = priority
            queue = session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == paper.id))
            if queue is None:
                queue = FullTextQueueItem(paper_id=paper.id)
                session.add(queue)
                queue_upserted += 1
            queue.priority = priority
            queue.rights_status = "open_access"
            queue.reason_factors = {
                "open_access": True,
                "pdf_available": True,
                "abstract_ready": abstract_ready,
                "citation_count": citation_counts.get(paper.id, 0),
            }
        elif paper.doi or paper.arxiv_id or paper.openalex_id:
            profile.full_text_status = "queued"
            profile.full_text_access = "open_access" if paper.is_oa else "unknown"
            profile.rights_status = "open_access" if paper.is_oa else "unknown"
            priority = min(79, 20 + min(citation_counts.get(paper.id, 0), 25) + (10 if abstract_ready else 0))
            queue = session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == paper.id))
            if queue is None:
                queue = FullTextQueueItem(paper_id=paper.id)
                session.add(queue)
                queue_upserted += 1
            queue.priority = priority
            queue.rights_status = "open_access" if paper.is_oa else "unknown"
            queue.reason_factors = {
                "open_access": paper.is_oa,
                "pdf_available": False,
                "resolver_discovery": True,
                "abstract_ready": abstract_ready,
                "citation_count": citation_counts.get(paper.id, 0),
            }
        else:
            profile.full_text_status = "restricted"
            profile.full_text_access = "paywalled"

        if create_discovery_events and paper.retrieved_at >= now - timedelta(days=discovery_days):
            event = session.scalar(
                select(DailyDiscoveryEvent).where(
                    DailyDiscoveryEvent.paper_id == paper.id,
                    DailyDiscoveryEvent.event_kind == "newly_discovered",
                    DailyDiscoveryEvent.event_date == paper.retrieved_at.date(),
                )
            )
            if event is None:
                session.add(
                    DailyDiscoveryEvent(
                        paper_id=paper.id,
                        event_kind="newly_discovered",
                        event_date=paper.retrieved_at.date(),
                        relevance_score=0.6,
                        novelty_score=0.5,
                        summary=_why_it_matters(
                            paper,
                            [],
                            "full_text" if full_text_ready else "abstract" if abstract_ready else "metadata",
                        ),
                        signals={"source": paper.primary_source, "is_oa": paper.is_oa},
                    )
                )
                events_upserted += 1

    for candidate in _compute_opportunities(session, now):
        stored = session.scalar(select(ResearchOpportunity).where(ResearchOpportunity.slug == candidate.slug))
        if stored is None:
            session.add(candidate)
        else:
            stored.title = candidate.title
            stored.hypothesis = candidate.hypothesis
            stored.rationale = candidate.rationale
            stored.coverage_count = candidate.coverage_count
            stored.adjacent_count = candidate.adjacent_count
            stored.signals = candidate.signals
            stored.recommended_method = candidate.recommended_method
            stored.generated_at = now
    session.commit()
    return {
        "papers_scanned": len(papers),
        "profiles_created": profiles_upserted,
        "queue_items_created": queue_upserted,
        "discovery_events_created": events_upserted,
    }


def translation_queue(
    session: Session,
    *,
    locale: str = "ko",
    limit: int = 100,
    retrieved_after: datetime | None = None,
) -> list[dict[str, object]]:
    conditions = [Paper.abstract.is_not(None), func.length(func.trim(Paper.abstract)) > 0]
    if retrieved_after is not None:
        conditions.append(Paper.retrieved_at >= retrieved_after)
    papers = list(
        session.scalars(
            select(Paper)
            .where(*conditions)
            .order_by(desc(Paper.retrieved_at))
        )
    )
    queue: list[dict[str, object]] = []
    for paper in papers:
        payload = translation_source_payload(session, paper, locale=locale)
        localization = session.scalar(
            select(PaperLocalization).where(
                PaperLocalization.paper_id == paper.id,
                PaperLocalization.locale == locale,
            )
        )
        if (
            localization is not None
            and localization.status == "completed"
            and localization.source_hash == payload["source_hash"]
        ):
            continue
        queue.append(payload)
        if len(queue) >= max(limit, 1):
            break
    return queue


def translation_source_payload(
    session: Session,
    paper: Paper,
    *,
    locale: str = "ko",
) -> dict[str, object]:
    keywords = list(
        dict.fromkeys(
            session.scalars(
                select(Topic.display_name)
                .join(PaperTopic, PaperTopic.topic_id == Topic.id)
                .where(PaperTopic.paper_id == paper.id)
                .order_by(Topic.kind, Topic.display_name)
                .limit(12)
            )
        )
    )
    source = {
        "title": paper.title,
        "abstract": paper.abstract or "",
        "keywords": keywords,
    }
    source_json = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "paper_id": str(paper.id),
        "locale": locale,
        **source,
        "source_hash": hashlib.sha256(source_json.encode()).hexdigest(),
    }


def import_localizations(session: Session, entries: list[dict[str, object]]) -> int:
    imported = 0
    for entry in entries:
        paper_id = uuid.UUID(str(entry["paper_id"]))
        paper = session.get(Paper, paper_id)
        if paper is None:
            continue
        locale = str(entry.get("locale") or "ko")
        source = translation_source_payload(session, paper, locale=locale)
        if str(entry.get("source_hash") or "") != source["source_hash"]:
            raise ValueError(f"Localization source changed for paper {paper_id}")
        translated_abstract = str(entry.get("abstract_translated") or "").strip()
        if paper.abstract and not translated_abstract:
            raise ValueError(f"Localization is missing an abstract for paper {paper_id}")
        if locale == "ko" and translated_abstract and not any("가" <= char <= "힣" for char in translated_abstract):
            raise ValueError(f"Korean localization contains no Hangul for paper {paper_id}")
        localization = session.scalar(
            select(PaperLocalization).where(
                PaperLocalization.paper_id == paper_id,
                PaperLocalization.locale == locale,
            )
        )
        if localization is None:
            localization = PaperLocalization(
                paper_id=paper_id,
                locale=locale,
                source_hash=str(entry["source_hash"]),
            )
            session.add(localization)
        localization.title = str(entry["title_translated"]) if entry.get("title_translated") else None
        localization.abstract = translated_abstract or None
        raw_keywords = entry.get("keywords", [])
        localization.keywords = (
            [str(keyword) for keyword in raw_keywords]
            if isinstance(raw_keywords, list)
            else []
        )
        localization.status = "completed"
        localization.source_hash = str(entry["source_hash"])
        localization.provider = str(entry["provider"]) if entry.get("provider") else "external_batch"
        localization.model = str(entry["model"]) if entry.get("model") else None
        localization.translated_at = datetime.now(UTC)
        imported += 1
    session.commit()
    return imported


def _compute_opportunities(session: Session, generated_at: datetime) -> list[ResearchOpportunity]:
    parent_count = session.scalar(
        select(func.count(func.distinct(PaperTopic.paper_id)))
        .join(Topic, Topic.id == PaperTopic.topic_id)
        .where(Topic.slug == "ai-adoption-business-value")
    ) or 0
    rows = session.execute(
        select(Topic.slug, Topic.display_name, func.count(func.distinct(PaperTopic.paper_id)))
        .outerjoin(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == "research_subaxis")
        .group_by(Topic.slug, Topic.display_name)
    ).all()
    methodology_rows = session.execute(
        select(Topic.display_name, func.count(func.distinct(PaperTopic.paper_id)))
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == "methodology")
        .group_by(Topic.display_name)
        .order_by(func.count(func.distinct(PaperTopic.paper_id)))
    ).all()
    recommended_method = methodology_rows[0][0] if methodology_rows else "Longitudinal or comparative field study"
    opportunities = []
    for slug, display_name, count in sorted(rows, key=lambda row: (int(row[2]), row[1])):
        coverage_count = int(count)
        opportunities.append(
            ResearchOpportunity(
                slug=f"coverage-{slug}",
                title=f"Under-examined connection: {display_name}",
                hypothesis=(
                    f"The current corpus contains relatively little evidence about {display_name.lower()} "
                    "within AI adoption and business value research."
                ),
                rationale=(
                    f"This sub-area has {coverage_count} locally classified records versus "
                    f"{parent_count} records in the parent territory. The difference is a search signal, "
                    "not proof of absence."
                ),
                axis_slug="ai-adoption-business-value",
                evidence_status="insufficient_evidence",
                coverage_count=coverage_count,
                adjacent_count=max(parent_count - coverage_count, 0),
                signals={
                    "classification": "heuristic_subaxis",
                    "parent_coverage": parent_count,
                    "requires_broader_search": True,
                    "candidate_not_conclusion": True,
                },
                recommended_method=recommended_method,
                generated_at=generated_at,
            )
        )
    return opportunities


def _opportunity_response(item: ResearchOpportunity) -> ResearchOpportunityResponse:
    return ResearchOpportunityResponse(
        slug=item.slug,
        title=item.title,
        hypothesis=item.hypothesis,
        rationale=item.rationale,
        axis_slug=item.axis_slug,
        evidence_status="insufficient_evidence",
        coverage_count=item.coverage_count,
        adjacent_count=item.adjacent_count,
        signals=item.signals,
        recommended_method=item.recommended_method,
        generated_at=item.generated_at,
    )


def _why_it_matters(paper: Paper, topics: list[str], depth: str) -> str:
    territory = ", ".join(topics[:2]) if topics else "the scoped AI × MOT corpus"
    return (
        f"New {depth.replace('_', ' ')}-level evidence connected to {territory}. "
        "Relevance is system inference; inspect the paper record before treating it as evidence."
    )
