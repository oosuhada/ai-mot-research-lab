from __future__ import annotations

import re
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, desc, exists, select
from sqlalchemy.orm import Session

from research_lab.models import Paper, PaperResearchCard, ResearchSignalExtract

SIGNAL_EXTRACT_VERSION = "signal_extract_v1"
SIGNAL_FIELDS = (
    "limitations",
    "future_research",
    "dataset_and_sample",
    "methodology",
    "analysis_technique",
    "variables_or_constructs",
    "findings",
)


@dataclass(frozen=True, slots=True)
class SignalPattern:
    signal_type: str
    label: str
    terms: tuple[str, ...]
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SignalExtractResult:
    selected: int
    cards_processed: int
    extracts_created: int
    cards_without_extracts: int
    skipped_existing: int
    dry_run: bool


_PATTERNS: tuple[SignalPattern, ...] = (
    SignalPattern(
        'limitation',
        'Causality and endogeneity',
        ('causal', 'causality', 'endogeneity'),
        ('limitations', 'future_research'),
    ),
    SignalPattern(
        'limitation',
        'Longitudinal evidence gap',
        ('longitudinal', 'panel', 'over time'),
        ('limitations', 'future_research'),
    ),
    SignalPattern(
        'limitation',
        'Cross-sectional design',
        ('cross-sectional', 'cross sectional', 'single time'),
        ('limitations',),
    ),
    SignalPattern(
        'limitation',
        'Single-country or narrow context',
        ('single-country', 'single country', 'one country', 'context'),
        ('limitations', 'future_research'),
    ),
    SignalPattern(
        'limitation',
        'Generalizability and external validity',
        ('generalizability', 'generalisability', 'external validity'),
        ('limitations', 'future_research'),
    ),
    SignalPattern(
        'limitation',
        'Self-report and common method bias',
        ('self-report', 'self report', 'common method', 'questionnaire'),
        ('limitations',),
    ),
    SignalPattern(
        'limitation',
        'Small or limited sample',
        ('small sample', 'limited sample', 'sample size'),
        ('limitations',),
    ),
    SignalPattern(
        'limitation',
        'Measurement validity',
        ('measurement', 'construct', 'operationalization', 'validity'),
        ('limitations',),
    ),
    SignalPattern(
        'limitation',
        'Bias, fairness, privacy risk',
        ('bias', 'fairness', 'privacy', 'ethical', 'ethics'),
        ('limitations', 'future_research'),
    ),
    SignalPattern(
        'dataset',
        'Survey data',
        ('survey', 'questionnaire', 'respondents'),
        ('dataset_and_sample', 'methodology'),
    ),
    SignalPattern(
        'dataset',
        'Panel or longitudinal data',
        ('panel', 'longitudinal', 'time-series', 'time series'),
        ('dataset_and_sample', 'methodology', 'future_research'),
    ),
    SignalPattern(
        'dataset',
        'Interview data',
        ('interview', 'interviews'),
        ('dataset_and_sample', 'methodology'),
    ),
    SignalPattern(
        'dataset',
        'Case study evidence',
        ('case study', 'case studies'),
        ('dataset_and_sample', 'methodology'),
    ),
    SignalPattern(
        'dataset',
        'Experiment data',
        ('experiment', 'experimental', 'randomized'),
        ('dataset_and_sample', 'methodology'),
    ),
    SignalPattern(
        'dataset',
        'Simulation or synthetic data',
        ('simulation', 'synthetic', 'agent-based'),
        ('dataset_and_sample', 'methodology'),
    ),
    SignalPattern(
        'dataset',
        'Patent or innovation-output data',
        ('patent', 'innovation output'),
        ('dataset_and_sample', 'findings'),
    ),
    SignalPattern(
        'dataset',
        'Financial or firm-performance data',
        ('financial', 'firm performance', 'productivity', 'roi'),
        ('dataset_and_sample', 'findings'),
    ),
    SignalPattern(
        'dataset',
        'Operational trace or sensor data',
        ('sensor', 'trace', 'log data', 'process data', 'operational data'),
        ('dataset_and_sample', 'methodology'),
    ),
    SignalPattern(
        'method',
        'Structural equation modeling',
        ('structural equation', 'sem', 'pls-sem', 'partial least squares'),
        ('methodology', 'analysis_technique'),
    ),
    SignalPattern(
        'method',
        'Regression or econometric model',
        ('regression', 'econometric', 'fixed effects', 'random effects'),
        ('methodology', 'analysis_technique'),
    ),
    SignalPattern(
        'method',
        'Difference-in-differences',
        ('difference-in-differences', 'difference in differences', 'did'),
        ('methodology', 'analysis_technique'),
    ),
    SignalPattern(
        'method',
        'Qualitative coding or thematic analysis',
        ('thematic analysis', 'content analysis', 'grounded theory', 'qualitative'),
        ('methodology', 'analysis_technique'),
    ),
    SignalPattern(
        'method',
        'Systematic review or bibliometric analysis',
        ('systematic review', 'bibliometric', 'meta-analysis', 'literature review'),
        ('methodology', 'analysis_technique'),
    ),
    SignalPattern(
        'method',
        'Machine-learning model evaluation',
        ('machine learning', 'deep learning', 'classification', 'prediction'),
        ('methodology', 'analysis_technique'),
    ),
    SignalPattern(
        'evaluation_metric',
        'Firm performance',
        ('firm performance', 'business performance', 'organizational performance'),
        ('findings', 'variables_or_constructs', 'dataset_and_sample'),
    ),
    SignalPattern(
        'evaluation_metric',
        'Innovation performance',
        ('innovation performance', 'innovation output', 'new product'),
        ('findings', 'variables_or_constructs'),
    ),
    SignalPattern(
        'evaluation_metric',
        'Productivity or efficiency',
        ('productivity', 'efficiency', 'operational performance'),
        ('findings', 'variables_or_constructs'),
    ),
    SignalPattern(
        'evaluation_metric',
        'Trust and adoption intention',
        ('trust', 'adoption intention', 'intention to use', 'acceptance'),
        ('findings', 'variables_or_constructs'),
    ),
    SignalPattern(
        'evaluation_metric',
        'Decision quality',
        ('decision quality', 'decision-making', 'decision making'),
        ('findings', 'variables_or_constructs'),
    ),
    SignalPattern(
        'evaluation_metric',
        'Fairness, privacy, or safety',
        ('fairness', 'privacy', 'safety', 'bias'),
        ('findings', 'variables_or_constructs'),
    ),
    SignalPattern(
        'future_research',
        'Longitudinal validation',
        ('longitudinal', 'over time', 'panel'),
        ('future_research',),
    ),
    SignalPattern(
        'future_research',
        'Causal identification',
        ('causal', 'causality', 'experiment', 'identification'),
        ('future_research',),
    ),
    SignalPattern(
        'future_research',
        'Cross-context replication',
        ('different context', 'other contexts', 'countries', 'industries', 'replicate'),
        ('future_research',),
    ),
    SignalPattern(
        'future_research',
        'Multi-method validation',
        ('mixed method', 'multi-method', 'qualitative', 'quantitative'),
        ('future_research',),
    ),
    SignalPattern(
        'future_research',
        'New data or measurement design',
        ('data', 'dataset', 'measurement', 'metric'),
        ('future_research',),
    ),
)


def backfill_research_signal_extracts(
    session: Session,
    *,
    limit: int = 1_000,
    refresh: bool = False,
    dry_run: bool = False,
) -> SignalExtractResult:
    cards = _select_cards(session, limit=max(limit, 1), refresh=refresh)
    if dry_run:
        return SignalExtractResult(
            selected=len(cards),
            cards_processed=0,
            extracts_created=0,
            cards_without_extracts=0,
            skipped_existing=0,
            dry_run=True,
        )

    extracts_created = 0
    cards_without_extracts = 0
    skipped_existing = 0
    for card, paper in cards:
        if refresh:
            session.execute(delete(ResearchSignalExtract).where(ResearchSignalExtract.research_card_id == card.id))
        elif _has_extracts(session, card.id):
            skipped_existing += 1
            continue
        rows = extract_signals_from_card(card, paper)
        if not rows:
            cards_without_extracts += 1
            continue
        session.add_all(rows)
        extracts_created += len(rows)
    session.commit()
    return SignalExtractResult(
        selected=len(cards),
        cards_processed=len(cards) - skipped_existing,
        extracts_created=extracts_created,
        cards_without_extracts=cards_without_extracts,
        skipped_existing=skipped_existing,
        dry_run=False,
    )


def extract_signals_from_card(card: PaperResearchCard, paper: Paper) -> list[ResearchSignalExtract]:
    rows: list[ResearchSignalExtract] = []
    seen: set[tuple[str, str, str]] = set()
    field_map = _supported_field_texts(card.fields or {})
    for pattern in _PATTERNS:
        for field_name in pattern.fields:
            field = field_map.get(field_name)
            if field is None or not _contains_any(field.evidence_text, pattern.terms):
                continue
            normalized_label = _normalize_label(pattern.label)
            key = (pattern.signal_type, normalized_label, field_name)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                ResearchSignalExtract(
                    research_card_id=card.id,
                    paper_id=paper.id,
                    signal_type=pattern.signal_type,
                    label=pattern.label,
                    normalized_label=normalized_label,
                    field_name=field_name,
                    evidence_text=_clip_evidence(field.evidence_text),
                    source_locator=field.source_locator,
                    chunk_id=field.chunk_id,
                    support_status=field.support_status,
                    extraction_version=SIGNAL_EXTRACT_VERSION,
                    extracted_at=datetime.now(UTC),
                )
            )
    return rows


def _select_cards(session: Session, *, limit: int, refresh: bool) -> list[tuple[PaperResearchCard, Paper]]:
    statement = select(PaperResearchCard, Paper).join(Paper, Paper.id == PaperResearchCard.paper_id)
    if not refresh:
        statement = statement.where(
            ~exists().where(ResearchSignalExtract.research_card_id == PaperResearchCard.id)
        )
    statement = statement.order_by(
        desc(Paper.publication_year).nullslast(),
        PaperResearchCard.created_at,
        PaperResearchCard.id,
    )
    return list(session.execute(statement.limit(limit)).all())


def _has_extracts(session: Session, card_id: uuid.UUID) -> bool:
    statement = select(ResearchSignalExtract.id).where(
        ResearchSignalExtract.research_card_id == card_id
    )
    return session.scalar(statement.limit(1)) is not None


@dataclass(frozen=True, slots=True)
class _FieldEvidence:
    evidence_text: str
    source_locator: str | None
    chunk_id: uuid.UUID | None
    support_status: str


def _supported_field_texts(fields: dict[str, object]) -> dict[str, _FieldEvidence]:
    supported: dict[str, _FieldEvidence] = {}
    for field_name in SIGNAL_FIELDS:
        raw = fields.get(field_name)
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("value_text") or "").strip()
        if not text:
            continue
        support_status = str(raw.get("support_status") or "insufficient_evidence")
        if support_status != "supported":
            continue
        source_locator = str(raw.get("source_locator") or "").strip() or None
        raw_chunk_id = raw.get("chunk_id")
        chunk_id = uuid.UUID(str(raw_chunk_id)) if raw_chunk_id else None
        supported[field_name] = _FieldEvidence(
            evidence_text=text,
            source_locator=source_locator,
            chunk_id=chunk_id,
            support_status=support_status,
        )
    return supported


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(term.lower() in normalized for term in terms)


def _normalize_label(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return normalized or "unclassified"


def _clip_evidence(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    return collapsed[:1_200]


def result_asdict(result: SignalExtractResult) -> dict[str, object]:
    return asdict(result)
