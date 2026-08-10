from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.models import (
    ComparisonCell,
    ComparisonSet,
    ComparisonSetPaper,
    EvidenceClaim,
    EvidenceLink,
    Paper,
)
from research_lab.schemas import (
    ComparisonCellResponse,
    ComparisonPaperResponse,
    ComparisonSetCreate,
    ComparisonSetResponse,
    EvidenceLinkResponse,
)

COMPARISON_FIELDS: tuple[str, ...] = (
    "research_question",
    "theoretical_lens",
    "unit_of_analysis",
    "context_industry_country",
    "dataset_and_sample",
    "methodology",
    "variables_or_constructs",
    "findings",
    "limitations",
    "claimed_contribution",
    "future_research",
)


@dataclass(frozen=True, slots=True)
class ExtractedField:
    value_text: str
    support_status: str
    claim_kind: str
    source_locator: str | None = None


def create_comparison_set(session: Session, payload: ComparisonSetCreate) -> ComparisonSetResponse:
    papers_by_id = _load_papers(session, payload.paper_ids)
    comparison_set = ComparisonSet(name=payload.name, description=payload.description)
    session.add(comparison_set)
    session.flush()

    for position, paper_id in enumerate(payload.paper_ids):
        session.add(
            ComparisonSetPaper(
                comparison_set_id=comparison_set.id,
                paper_id=paper_id,
                position=position,
            )
        )
        paper = papers_by_id[paper_id]
        extracted = extract_comparison_fields(paper)
        for field_name in COMPARISON_FIELDS:
            field = extracted[field_name]
            cell = ComparisonCell(
                comparison_set_id=comparison_set.id,
                paper_id=paper.id,
                field_name=field_name,
                value_text=field.value_text,
                support_status=field.support_status,
            )
            session.add(cell)
            session.flush()

            claim = EvidenceClaim(
                claim_text=field.value_text,
                claim_kind=field.claim_kind,
                support_status=field.support_status,
                scope_type="comparison_cell",
                scope_id=cell.id,
                comparison_cell_id=cell.id,
            )
            session.add(claim)
            session.flush()

            if field.support_status != "insufficient_evidence":
                session.add(
                    EvidenceLink(
                        claim_id=claim.id,
                        paper_id=paper.id,
                        relation="supports",
                        source_locator=field.source_locator,
                    )
                )

    session.commit()
    return get_comparison_set(session, comparison_set.id)


def get_comparison_set(session: Session, comparison_set_id: uuid.UUID) -> ComparisonSetResponse:
    comparison_set = session.get(ComparisonSet, comparison_set_id)
    if comparison_set is None:
        raise HTTPException(status_code=404, detail="Comparison set not found")

    paper_rows = session.execute(
        select(ComparisonSetPaper, Paper)
        .join(Paper, Paper.id == ComparisonSetPaper.paper_id)
        .where(ComparisonSetPaper.comparison_set_id == comparison_set_id)
        .order_by(ComparisonSetPaper.position)
    ).all()
    papers = [
        ComparisonPaperResponse(
            id=paper.id,
            title=paper.title,
            doi=paper.doi,
            publication_year=paper.publication_year,
        )
        for _, paper in paper_rows
    ]

    cells: list[ComparisonCellResponse] = []
    cell_rows = session.scalars(
        select(ComparisonCell)
        .where(ComparisonCell.comparison_set_id == comparison_set_id)
        .order_by(ComparisonCell.field_name, ComparisonCell.paper_id)
    ).all()
    paper_lookup = {paper.id: paper for _, paper in paper_rows}

    for cell in cell_rows:
        claim = session.scalar(
            select(EvidenceClaim).where(EvidenceClaim.comparison_cell_id == cell.id)
        )
        if claim is None:
            raise RuntimeError(f"Comparison cell {cell.id} has no evidence claim")
        evidence = _evidence_links(session, claim.id, paper_lookup)
        cells.append(
            ComparisonCellResponse(
                id=cell.id,
                paper_id=cell.paper_id,
                field_name=cell.field_name,
                value_text=cell.value_text,
                support_status=cell.support_status,
                claim_kind=claim.claim_kind,
                evidence=evidence,
            )
        )

    return ComparisonSetResponse(
        id=comparison_set.id,
        name=comparison_set.name,
        description=comparison_set.description,
        papers=papers,
        cells=cells,
    )


def extract_comparison_fields(paper: Paper) -> dict[str, ExtractedField]:
    abstract = (paper.abstract or "").strip()
    sentences = _sentences(abstract)
    missing = ExtractedField(
        value_text="Insufficient evidence in available abstract/metadata; inspect the full text.",
        support_status="insufficient_evidence",
        claim_kind="system_inference",
    )
    result = {field_name: missing for field_name in COMPARISON_FIELDS}
    if not abstract:
        return result

    sentence_patterns: dict[str, tuple[str, ...]] = {
        "research_question": (
            "aim",
            "purpose",
            "investigat",
            "examin",
            "explor",
            "this study",
            "this paper",
        ),
        "findings": ("find", "result", "show", "reveal", "demonstrat", "suggest"),
        "limitations": ("limitation", "limited by", "caution"),
        "claimed_contribution": ("contribut", "novel", "extends", "advance"),
        "future_research": ("future research", "further research", "future work"),
        "variables_or_constructs": ("variable", "construct", "mediator", "moderator"),
    }
    for field_name, patterns in sentence_patterns.items():
        sentence = _first_sentence_matching(sentences, patterns)
        if sentence:
            result[field_name] = _supported(sentence)

    theory_terms = (
        "resource-based view",
        "dynamic capabilities",
        "dynamic capability",
        "absorptive capacity",
        "institutional theory",
        "technology acceptance model",
        "diffusion of innovations",
        "socio-technical",
        "technology-organization-environment",
        "toe framework",
    )
    theories = _matched_terms(abstract, theory_terms)
    if theories:
        result["theoretical_lens"] = _supported("; ".join(theories))

    methodology_terms = (
        "systematic review",
        "literature review",
        "bibliometric",
        "case study",
        "cross-case",
        "survey",
        "experiment",
        "regression",
        "structural equation",
        "sem",
        "interview",
        "qualitative",
        "quantitative",
        "panel data",
        "scoping review",
    )
    methods = _matched_terms(abstract, methodology_terms)
    if methods:
        result["methodology"] = _supported("; ".join(methods))

    unit_terms = (
        "firm",
        "organization",
        "employee",
        "worker",
        "team",
        "manager",
        "factory",
        "supply chain",
        "industry",
    )
    units = _matched_terms(abstract, unit_terms)
    if units:
        result["unit_of_analysis"] = _supported("Abstract mentions: " + "; ".join(units))

    context_terms = (
        "manufacturing",
        "healthcare",
        "health care",
        "banking",
        "finance",
        "retail",
        "e-commerce",
        "supply chain",
        "education",
        "public sector",
        "united states",
        "china",
        "india",
        "europe",
        "korea",
    )
    contexts = _matched_terms(abstract, context_terms)
    if contexts:
        result["context_industry_country"] = _supported(
            "Abstract mentions: " + "; ".join(contexts)
        )

    sample = re.search(
        r"\b(?:sample of\s+\d[\d,]*|n\s*=\s*\d[\d,]*|\d[\d,]*\s+"
        r"(?:firms|companies|employees|participants|respondents|organizations))\b",
        abstract,
        flags=re.IGNORECASE,
    )
    if sample:
        result["dataset_and_sample"] = _supported(sample.group(0))

    return result


def _load_papers(session: Session, paper_ids: list[uuid.UUID]) -> dict[uuid.UUID, Paper]:
    unique_ids = list(dict.fromkeys(paper_ids))
    if len(unique_ids) != len(paper_ids):
        raise HTTPException(status_code=422, detail="Duplicate paper IDs are not allowed")
    papers = session.scalars(select(Paper).where(Paper.id.in_(paper_ids))).all()
    found = {paper.id: paper for paper in papers}
    missing = [str(paper_id) for paper_id in paper_ids if paper_id not in found]
    if missing:
        raise HTTPException(status_code=404, detail={"missing_paper_ids": missing})
    return found


def _evidence_links(
    session: Session,
    claim_id: uuid.UUID,
    paper_lookup: dict[uuid.UUID, Paper],
) -> list[EvidenceLinkResponse]:
    links = session.scalars(select(EvidenceLink).where(EvidenceLink.claim_id == claim_id)).all()
    result: list[EvidenceLinkResponse] = []
    for link in links:
        paper = paper_lookup.get(link.paper_id) or session.get(Paper, link.paper_id)
        if paper is None:
            continue
        result.append(
            EvidenceLinkResponse(
                paper_id=paper.id,
                paper_title=paper.title,
                doi=paper.doi,
                primary_url=paper.primary_url,
                relation=link.relation,
                source_locator=link.source_locator,
            )
        )
    return result


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _first_sentence_matching(sentences: list[str], patterns: tuple[str, ...]) -> str | None:
    for sentence in sentences:
        lowered = sentence.lower()
        if any(pattern in lowered for pattern in patterns):
            return sentence
    return None


def _matched_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term in lowered]


def _supported(value: str) -> ExtractedField:
    return ExtractedField(
        value_text=value,
        support_status="supported",
        claim_kind="paper_claim",
        source_locator="abstract",
    )
