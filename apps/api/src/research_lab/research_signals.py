from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import and_, case, desc, func, not_, or_, select, text
from sqlalchemy.orm import Session

from research_lab.models import (
    Author,
    EvidenceClaim,
    Paper,
    PaperAuthor,
    PaperContentProfile,
    PaperResearchCard,
    PaperTopic,
    Topic,
)
from research_lab.schemas import ResearchCardEvidenceSignal, ResearchSignalItem, ResearchSignalLiftResponse

_LIMITATION_TOPIC_PATTERNS: tuple[tuple[str, tuple[str, ...], str, str], ...] = (
    (
        "Causality and longitudinal evidence",
        ("causal", "causality", "longitudinal", "panel", "experiment"),
        "Repeated concern that observed AI-performance links may need stronger causal or longitudinal designs.",
        "AI causality longitudinal endogeneity performance",
    ),
    (
        "Generalizability and external validity",
        ("implementation", "scaling", "sector", "industrial", "context"),
        "Signals that findings may not transfer cleanly across sectors, countries, firms, or deployment contexts.",
        "AI generalizability external validity single country context",
    ),
    (
        "Measurement ambiguity",
        ("measurement", "evaluation", "metric", "performance", "productivity", "value", "roi"),
        "Signals that AI capability, adoption, trust, value, or performance constructs are measured inconsistently.",
        "AI capability measurement construct operationalization proxy",
    ),
    (
        "Self-report and survey dependence",
        ("survey", "questionnaire", "trust", "readiness"),
        (
            "Signals where evidence may depend heavily on respondent reports rather than "
            "observed behavioral or operational data."
        ),
        "AI self reported survey common method bias questionnaire",
    ),
    (
        "Trust, explainability, and accountability",
        ("trust", "explainability", "explainable", "accountability", "transparency"),
        "Signals around whether AI-supported decisions can be understood, governed, and responsibly delegated.",
        "AI trust explainability accountability transparency",
    ),
    (
        "Bias, fairness, and privacy risk",
        ("bias", "fairness", "privacy", "discrimination", "ethical", "ethics", "rights"),
        "Signals that adoption and governance claims need explicit checks for fairness, privacy, and social impact.",
        "AI bias fairness privacy discrimination ethics",
    ),
)

_METHOD_DATA_KEYWORDS = (
    "method",
    "experiment",
    "simulation",
    "survey",
    "case",
    "panel",
    "longitudinal",
    "data",
    "dataset",
    "benchmark",
    "evaluation",
    "metric",
    "performance",
    "digital twin",
    "sensor",
    "trace",
)


def get_research_signal_lift(session: Session, *, limit: int = 8) -> ResearchSignalLiftResponse:
    """Summarize research-signal candidates from already-materialized corpus metadata.

    This endpoint is deliberately evidence-led and conservative: it uses existing topic,
    year, author, card, and full-text coverage signals, and labels limitation rows as
    text proxies until Research Cards are materialized at scale.
    """

    generated_at = datetime.now(UTC)
    _set_read_timeout(session, milliseconds=8_000)
    current_year = _corpus_current_year(session, generated_at.year)
    recent_start = current_year - 1
    recent_window = f"{recent_start}–{current_year}"
    total_records = session.scalar(select(func.count()).select_from(Paper)) or 0
    full_text_ready = session.scalar(
        select(func.count()).select_from(PaperContentProfile).where(
            PaperContentProfile.full_text_status == "available"
        )
    ) or 0
    research_cards_ready = session.scalar(select(func.count()).select_from(PaperResearchCard)) or 0
    reviewed_research_cards = session.scalar(
        select(func.count()).select_from(PaperResearchCard).where(PaperResearchCard.status == "reviewed")
    ) or 0
    evidence_claims = session.scalar(select(func.count()).select_from(EvidenceClaim)) or 0

    topic_rows = _topic_signal_rows(session, recent_start=recent_start, current_year=current_year)
    emerging_questions = _emerging_question_signals(topic_rows, limit=limit)
    method_data_signals = _method_data_signals(topic_rows, limit=limit)

    return ResearchSignalLiftResponse(
        generated_at=generated_at,
        recent_window=recent_window,
        total_records=int(total_records),
        full_text_ready=int(full_text_ready),
        research_cards_ready=int(research_cards_ready),
        reviewed_research_cards=int(reviewed_research_cards),
        evidence_claims=int(evidence_claims),
        repeated_limitations=_limitation_proxy_signals(topic_rows, limit=limit),
        card_evidence_signals=_card_evidence_signals(session, limit=limit),
        emerging_questions=emerging_questions,
        method_data_signals=method_data_signals,
        frontier_researchers=_frontier_researchers(
            session,
            recent_start=recent_start,
            current_year=current_year,
            limit=limit,
        ),
        next_actions=[
            "Materialize Research Cards for the highest-signal full-text papers before treating any gap as a claim.",
            "Use the limitation proxies to launch falsification searches, not as proof that a literature gap exists.",
            (
                "Deep-search only within a chosen signal or question scope, then inspect "
                "chunk-level evidence before synthesis."
            ),
        ],
        caveats=[
            (
                "Recent growth is based on the local corpus and is affected by collection "
                "strategy, especially 2025–2026 concentration."
            ),
            (
                "Repeated limitations are title/abstract text proxies until Paper Research "
                "Cards are generated and reviewed; card evidence rows are machine-extracted leads."
            ),
            (
                "Researcher counts are frontier candidates, not author impact rankings; "
                "inspect papers before relying on them."
            ),
        ],
    )


def _card_evidence_signals(session: Session, *, limit: int) -> list[ResearchCardEvidenceSignal]:
    rows = session.execute(
        select(PaperResearchCard, Paper)
        .join(Paper, Paper.id == PaperResearchCard.paper_id)
        .where(PaperResearchCard.status.in_(["candidate", "in_review", "reviewed"]))
        .order_by(desc(PaperResearchCard.created_at), desc(Paper.publication_year), Paper.id)
        .limit(max(limit * 8, limit))
    ).all()
    signals: list[ResearchCardEvidenceSignal] = []
    seen: set[tuple[str, str]] = set()
    preferred_fields = (
        ("limitations", "Limitation lead"),
        ("future_research", "Future-research lead"),
        ("dataset_and_sample", "Data lead"),
        ("methodology", "Method lead"),
        ("analysis_technique", "Analysis lead"),
    )
    for card, paper in rows:
        fields = card.fields or {}
        for field_name, label in preferred_fields:
            raw = fields.get(field_name)
            if not isinstance(raw, dict):
                continue
            value_text = _clean_signal_text(raw.get("value_text"))
            if not value_text or raw.get("support_status") != "supported":
                continue
            dedupe_key = (field_name, value_text[:180].lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            signals.append(
                ResearchCardEvidenceSignal(
                    field_name=field_name,
                    label=label,
                    paper_id=paper.id,
                    paper_title=paper.title,
                    publication_year=paper.publication_year,
                    value_text=value_text,
                    source_locator=_clean_signal_text(raw.get("source_locator")),
                    chunk_id=raw.get("chunk_id"),
                    support_status="supported",
                )
            )
            if len(signals) >= limit:
                return signals
    return signals


def _clean_signal_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    if len(cleaned) > 500:
        return cleaned[:497].rstrip() + "..."
    return cleaned


def _set_read_timeout(session: Session, *, milliseconds: int) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        session.execute(text(f"SET LOCAL statement_timeout = {int(milliseconds)}"))


def _corpus_current_year(session: Session, fallback_year: int) -> int:
    max_year = session.scalar(
        select(func.max(Paper.publication_year)).where(Paper.publication_year <= fallback_year)
    )
    return int(max_year or fallback_year)


def _topic_signal_rows(
    session: Session,
    *,
    recent_start: int,
    current_year: int,
) -> list[dict[str, object]]:
    recent_condition = and_(
        Paper.publication_year >= recent_start,
        Paper.publication_year <= current_year,
    )
    baseline_condition = or_(Paper.publication_year < recent_start, Paper.publication_year.is_(None))
    full_text_condition = PaperContentProfile.full_text_status == "available"
    rows = session.execute(
        select(
            Topic.slug,
            Topic.display_name,
            Topic.kind,
            func.count(func.distinct(PaperTopic.paper_id)).label("paper_count"),
            func.count(func.distinct(case((recent_condition, Paper.id)))).label("recent_count"),
            func.count(func.distinct(case((baseline_condition, Paper.id)))).label("baseline_count"),
            func.count(func.distinct(case((full_text_condition, Paper.id)))).label("full_text_count"),
        )
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .join(Paper, Paper.id == PaperTopic.paper_id)
        .outerjoin(PaperContentProfile, PaperContentProfile.paper_id == Paper.id)
        .where(Topic.kind.in_(["research_axis", "research_subaxis", "openalex_topic", "methodology"]))
        .group_by(Topic.id, Topic.slug, Topic.display_name, Topic.kind)
    ).mappings()
    return [dict(row) for row in rows]


def _emerging_question_signals(rows: Iterable[dict[str, object]], *, limit: int) -> list[ResearchSignalItem]:
    candidates: list[ResearchSignalItem] = []
    for row in rows:
        kind = str(row["kind"])
        if kind not in {"research_axis", "research_subaxis"}:
            continue
        paper_count = int(row["paper_count"] or 0)
        recent_count = int(row["recent_count"] or 0)
        baseline_count = int(row["baseline_count"] or 0)
        if paper_count < 10 or recent_count < 3:
            continue
        growth_score = _growth_score(paper_count, recent_count, baseline_count)
        label = str(row["display_name"])
        candidates.append(
            ResearchSignalItem(
                signal_type="emerging_question",
                label=label,
                description=(
                    "A growing local topic cluster. Treat it as a prompt to ask what became "
                    "newly measurable, testable, or governable in this area."
                ),
                paper_count=paper_count,
                recent_count=recent_count,
                full_text_count=int(row["full_text_count"] or 0),
                growth_score=growth_score,
                evidence_depth="derived",
                query_hint=label,
                caveat="Growth is corpus-local; verify with broader search before calling it a field trend.",
            )
        )
    return sorted(candidates, key=lambda item: (item.growth_score, item.recent_count), reverse=True)[:limit]


def _method_data_signals(rows: Iterable[dict[str, object]], *, limit: int) -> list[ResearchSignalItem]:
    candidates: list[ResearchSignalItem] = []
    for row in rows:
        label = str(row["display_name"])
        kind = str(row["kind"])
        paper_count = int(row["paper_count"] or 0)
        recent_count = int(row["recent_count"] or 0)
        baseline_count = int(row["baseline_count"] or 0)
        if paper_count < 10 or recent_count < 3:
            continue
        if kind != "methodology":
            continue
        candidates.append(
            ResearchSignalItem(
                signal_type="method_data",
                label=label,
                description=(
                    "Method, data, or evaluation signal that can change what questions are now feasible "
                    "to test rather than merely discuss."
                ),
                paper_count=paper_count,
                recent_count=recent_count,
                full_text_count=int(row["full_text_count"] or 0),
                growth_score=_growth_score(paper_count, recent_count, baseline_count),
                evidence_depth="derived",
                query_hint=label,
                caveat="Inspect concrete datasets and evaluation metrics in Research Cards before using this signal.",
            )
        )
    return sorted(candidates, key=lambda item: (item.growth_score, item.recent_count), reverse=True)[:limit]


def _limitation_proxy_signals(
    rows: Iterable[dict[str, object]],
    *,
    limit: int,
) -> list[ResearchSignalItem]:
    topic_rows = list(rows)
    signals: list[ResearchSignalItem] = []
    for label, terms, description, query_hint in _LIMITATION_TOPIC_PATTERNS:
        matching_rows = []
        for row in topic_rows:
            if str(row["kind"]) == "research_axis":
                continue
            normalized = str(row["display_name"]).lower()
            if any(term in normalized for term in terms):
                matching_rows.append(row)
        if not matching_rows:
            continue
        best = max(
            matching_rows,
            key=lambda row: (int(row["recent_count"] or 0), int(row["paper_count"] or 0)),
        )
        paper_count = int(best["paper_count"] or 0)
        recent_count = int(best["recent_count"] or 0)
        baseline_count = int(best["baseline_count"] or 0)
        signals.append(
            ResearchSignalItem(
                signal_type="repeated_limitation",
                label=label,
                description=f"{description} Current proxy anchor: {best['display_name']}.",
                paper_count=paper_count,
                recent_count=recent_count,
                full_text_count=int(best["full_text_count"] or 0),
                growth_score=_growth_score(paper_count, recent_count, baseline_count),
                evidence_depth="derived",
                query_hint=query_hint,
                caveat="Fast topic proxy; generate Research Cards before treating it as a confirmed limitation.",
            )
        )
    return sorted(signals, key=lambda item: (item.recent_count, item.paper_count), reverse=True)[:limit]


def _frontier_researchers(
    session: Session,
    *,
    recent_start: int,
    current_year: int,
    limit: int,
) -> list[ResearchSignalItem]:
    recent_condition = and_(
        Paper.publication_year >= recent_start,
        Paper.publication_year <= current_year,
    )
    full_text_condition = PaperContentProfile.full_text_status == "available"
    recent_count_expr = func.count(func.distinct(case((recent_condition, Paper.id))))
    rows = session.execute(
        select(
            Author.display_name,
            func.count(func.distinct(PaperAuthor.paper_id)).label("paper_count"),
            recent_count_expr.label("recent_count"),
            func.count(func.distinct(case((full_text_condition, Paper.id)))).label("full_text_count"),
        )
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .join(Paper, Paper.id == PaperAuthor.paper_id)
        .outerjoin(PaperContentProfile, PaperContentProfile.paper_id == Paper.id)
        .where(
            not_(func.lower(Author.display_name).like("%gemini%")),
            not_(func.lower(Author.display_name).like("%chatterbox%")),
            not_(func.lower(Author.display_name).like("%unknown%")),
        )
        .group_by(Author.id, Author.display_name)
        .having(recent_count_expr >= 3)
        .order_by(desc("recent_count"), desc("paper_count"), Author.display_name)
        .limit(limit)
    ).mappings()
    return [
        ResearchSignalItem(
            signal_type="frontier_researcher",
            label=str(row["display_name"]),
            description=(
                "Recent local-corpus activity candidate. Inspect their paper cluster, methods, and evidence depth "
                "before treating them as a frontier researcher."
            ),
            paper_count=int(row["paper_count"] or 0),
            recent_count=int(row["recent_count"] or 0),
            full_text_count=int(row["full_text_count"] or 0),
            growth_score=round(
                (int(row["recent_count"] or 0) + 1) / math.sqrt(int(row["paper_count"] or 0) + 1),
                3,
            ),
            evidence_depth="derived",
            query_hint=str(row["display_name"]),
            caveat="Author name disambiguation may be imperfect in imported metadata.",
        )
        for row in rows
    ]


def _growth_score(paper_count: int, recent_count: int, baseline_count: int) -> float:
    recent_share = recent_count / max(paper_count, 1)
    baseline_penalty = math.log(baseline_count + 2)
    return round((recent_share * math.log(paper_count + 1)) / max(baseline_penalty, 1.0), 3)
