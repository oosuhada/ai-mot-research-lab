from __future__ import annotations

import uuid
from collections import Counter

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.models import (
    EvidenceClaim,
    EvidenceLink,
    GapAnalysis,
    Paper,
    PaperTopic,
    ResearchQuestion,
    Topic,
)
from research_lab.retrieval import HybridRetrievalService
from research_lab.schemas import (
    EvidenceLinkResponse,
    GapAnalysisCreate,
    GapAnalysisResponse,
    GapAnalysisUpdate,
    GapEvidenceClaimResponse,
)


def create_gap_analysis(session: Session, payload: GapAnalysisCreate) -> GapAnalysisResponse:
    rows = HybridRetrievalService(session).search(
        payload.topic,
        mode="hybrid",
        limit=payload.retrieval_limit,
    )
    paper_ids = [row.id for row in rows]
    if not paper_ids:
        raise HTTPException(status_code=422, detail="No papers were retrieved for this topic")

    research_question = ResearchQuestion(
        title=payload.title or payload.topic[:500],
        question_text=payload.topic,
        motivation="User-created exploration seeded from the local AI × MOT corpus.",
        scope_notes=f"Hybrid retrieval over {len(paper_ids)} seed-corpus papers.",
        status="exploring",
    )
    session.add(research_question)
    session.flush()

    axis_counts = _axis_counts(session, paper_ids)
    cluster_text = _cluster_text(axis_counts, len(paper_ids))
    coverage_signal = _coverage_signal(axis_counts, len(paper_ids))
    theoretical_lenses = _candidate_theoretical_lenses(payload.topic)
    methods = _candidate_methods(payload.topic)

    analysis = GapAnalysis(
        research_question_id=research_question.id,
        search_strategy=(
            f"Hybrid retrieval (PostgreSQL FTS + pgvector + RRF) for: {payload.topic!r}; "
            f"review the top {len(paper_ids)} records before accepting any synthesis."
        ),
        inclusion_criteria=(
            "AI must be connected to organization, industry, innovation, operations, governance, "
            "or enterprise workflow questions; default publication year is 2018 onward."
        ),
        exclusion_criteria=(
            "Exclude model-performance-only work without a direct management/organizational link, "
            "and exclude unlicensed full text that was not supplied by the user."
        ),
        research_clusters=cluster_text,
        agreements="Insufficient evidence: abstract-level retrieval is not enough to assert consensus.",
        conflicts="Insufficient evidence: contradiction polarity requires claim-level review.",
        under_studied_contexts=coverage_signal,
        gap_candidates=(
            "Candidate hypothesis only: inspect the lowest-coverage clusters and contexts in this "
            "retrieved set, then test whether the apparent sparsity remains after broader searching."
        ),
        falsifiability_notes=(
            "Falsify the candidate gap by expanding synonyms, adjacent MOT theories, venues, years, "
            "and citation chains; reject it if substantial directly relevant evidence appears."
        ),
        follow_up_questions=(
            f"1. Under what organizational conditions does {payload.topic} change measurable outcomes?\n"
            f"2. Which mechanisms mediate or moderate the effect of {payload.topic}?\n"
            f"3. Does the effect differ by industry, country, firm size, or decision level?"
        ),
        theoretical_lenses=theoretical_lenses,
        candidate_data_methods=methods,
        status="draft",
    )
    session.add(analysis)
    session.flush()

    evidence_claim = EvidenceClaim(
        claim_text=(
            f"The current hybrid search retrieved {len(paper_ids)} papers; research-axis coverage is: "
            f"{cluster_text}"
        ),
        claim_kind="fact",
        support_status="supported",
        scope_type="gap_analysis",
        scope_id=analysis.id,
        gap_analysis_id=analysis.id,
    )
    session.add(evidence_claim)
    session.flush()
    for paper_id in paper_ids[:10]:
        session.add(
            EvidenceLink(
                claim_id=evidence_claim.id,
                paper_id=paper_id,
                relation="supports",
                source_locator="metadata + abstract retrieval result",
            )
        )

    candidate_claim = EvidenceClaim(
        claim_text=analysis.gap_candidates or "Candidate research gap",
        claim_kind="system_inference",
        support_status="insufficient_evidence",
        scope_type="gap_analysis",
        scope_id=analysis.id,
        gap_analysis_id=analysis.id,
    )
    session.add(candidate_claim)
    session.commit()
    return get_gap_analysis(session, analysis.id)


def update_gap_analysis(
    session: Session,
    analysis_id: uuid.UUID,
    payload: GapAnalysisUpdate,
) -> GapAnalysisResponse:
    analysis = session.get(GapAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Gap analysis not found")

    changes = payload.model_dump(exclude_unset=True)
    for field_name, value in changes.items():
        setattr(analysis, field_name, value)
        if field_name != "status" and value:
            session.add(
                EvidenceClaim(
                    claim_text=f"User-edited {field_name}: {value}",
                    claim_kind="user_note",
                    support_status="insufficient_evidence",
                    scope_type="gap_analysis",
                    scope_id=analysis.id,
                    gap_analysis_id=analysis.id,
                )
            )
    session.commit()
    return get_gap_analysis(session, analysis.id)


def get_gap_analysis(session: Session, analysis_id: uuid.UUID) -> GapAnalysisResponse:
    analysis = session.get(GapAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Gap analysis not found")
    question = session.get(ResearchQuestion, analysis.research_question_id)
    if question is None:
        raise RuntimeError(f"Research question {analysis.research_question_id} is missing")

    claims = session.scalars(
        select(EvidenceClaim)
        .where(EvidenceClaim.gap_analysis_id == analysis.id)
        .order_by(EvidenceClaim.created_at, EvidenceClaim.id)
    ).all()
    return GapAnalysisResponse(
        id=analysis.id,
        research_question_id=question.id,
        research_question=question.question_text,
        status=analysis.status,
        search_strategy=analysis.search_strategy,
        inclusion_criteria=analysis.inclusion_criteria,
        exclusion_criteria=analysis.exclusion_criteria,
        research_clusters=analysis.research_clusters,
        agreements=analysis.agreements,
        conflicts=analysis.conflicts,
        under_studied_contexts=analysis.under_studied_contexts,
        gap_candidates=analysis.gap_candidates,
        falsifiability_notes=analysis.falsifiability_notes,
        follow_up_questions=analysis.follow_up_questions,
        theoretical_lenses=analysis.theoretical_lenses,
        candidate_data_methods=analysis.candidate_data_methods,
        evidence_claims=[_claim_response(session, claim) for claim in claims],
    )


def _axis_counts(session: Session, paper_ids: list[uuid.UUID]) -> Counter[str]:
    rows = session.execute(
        select(Topic.display_name)
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(
            PaperTopic.paper_id.in_(paper_ids),
            Topic.kind == "research_axis",
        )
    ).all()
    return Counter(name for (name,) in rows)


def _cluster_text(axis_counts: Counter[str], retrieved_count: int) -> str:
    if not axis_counts:
        return f"No research-axis labels found across {retrieved_count} retrieved papers."
    return "; ".join(
        f"{name}: {count}/{retrieved_count}"
        for name, count in axis_counts.most_common()
    )


def _coverage_signal(axis_counts: Counter[str], retrieved_count: int) -> str:
    if not axis_counts:
        return "Insufficient evidence: no axis coverage data is available."
    name, count = min(axis_counts.items(), key=lambda item: (item[1], item[0]))
    return (
        f"Candidate coverage signal only: {name} appears in {count}/{retrieved_count} retrieved papers. "
        "Sparse retrieval is not itself a research gap and must be falsified with broader searches."
    )


def _candidate_theoretical_lenses(topic: str) -> str:
    lowered = topic.lower()
    candidates: list[str] = []
    if any(term in lowered for term in ("capability", "performance", "advantage")):
        candidates.extend(["Resource-based view", "Dynamic capabilities"])
    if any(term in lowered for term in ("adoption", "diffusion", "implementation")):
        candidates.extend(["Technology–Organization–Environment", "Diffusion of innovations"])
    if any(term in lowered for term in ("work", "human", "organization", "collaboration")):
        candidates.append("Socio-technical systems")
    if any(term in lowered for term in ("governance", "regulation", "responsible", "accountability")):
        candidates.append("Institutional theory")
    if not candidates:
        candidates.extend(["Dynamic capabilities", "Socio-technical systems"])
    return (
        "Candidate lenses to evaluate, not paper-backed conclusions: "
        + "; ".join(dict.fromkeys(candidates))
    )


def _candidate_methods(topic: str) -> str:
    lowered = topic.lower()
    if any(term in lowered for term in ("performance", "productivity", "roi", "value")):
        return "Candidate methods: panel/longitudinal design, quasi-experiment, matched firm-level data."
    if any(term in lowered for term in ("work", "human", "collaboration", "decision")):
        return "Candidate methods: field experiment, survey + behavioral trace data, mixed-method case study."
    if any(term in lowered for term in ("factory", "manufacturing", "operations")):
        return "Candidate methods: operational event logs, before/after deployment design, multi-site case comparison."
    return "Candidate methods: systematic review followed by a context-specific empirical design."


def _claim_response(session: Session, claim: EvidenceClaim) -> GapEvidenceClaimResponse:
    links = session.scalars(select(EvidenceLink).where(EvidenceLink.claim_id == claim.id)).all()
    evidence: list[EvidenceLinkResponse] = []
    for link in links:
        paper = session.get(Paper, link.paper_id)
        if paper is None:
            continue
        evidence.append(
            EvidenceLinkResponse(
                paper_id=paper.id,
                paper_title=paper.title,
                doi=paper.doi,
                primary_url=paper.primary_url,
                relation=link.relation,
                source_locator=link.source_locator,
            )
        )
    return GapEvidenceClaimResponse(
        id=claim.id,
        claim_text=claim.claim_text,
        claim_kind=claim.claim_kind,
        support_status=claim.support_status,
        evidence=evidence,
    )
