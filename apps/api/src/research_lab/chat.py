from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.models import ComparisonSetPaper, Paper
from research_lab.retrieval import HybridRetrievalService
from research_lab.schemas import (
    ChatCitationResponse,
    ChatParagraphResponse,
    ChatRequest,
    ChatResponse,
)


@dataclass(frozen=True, slots=True)
class EvidenceSnippet:
    paper: Paper
    excerpt: str
    overlap_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedParagraph:
    text: str
    claim_kind: str
    support_status: str
    citation_indexes: tuple[int, ...]


class GroundedAnswerProvider(Protocol):
    name: str

    def generate(
        self,
        question: str,
        evidence: list[EvidenceSnippet],
    ) -> list[GeneratedParagraph]: ...


class DeterministicEvidenceProvider:
    """No-key provider that only reports evidence it can point back to.

    This is intentionally not a language-model substitute. It exists so the
    retrieval/citation contract and UI can be tested without external cost or
    secret keys.
    """

    name = "deterministic_evidence_v1"

    def generate(
        self,
        question: str,
        evidence: list[EvidenceSnippet],
    ) -> list[GeneratedParagraph]:
        if not evidence:
            return [
                GeneratedParagraph(
                    text=(
                        "Insufficient evidence: no scoped paper with usable abstract evidence "
                        "was retrieved for this question."
                    ),
                    claim_kind="system_inference",
                    support_status="insufficient_evidence",
                    citation_indexes=(),
                )
            ]

        paragraphs: list[GeneratedParagraph] = []
        for index, snippet in enumerate(evidence, start=1):
            terms = ", ".join(snippet.overlap_terms[:5]) or "the query context"
            paragraphs.append(
                GeneratedParagraph(
                    text=(
                        f"{snippet.paper.title} is directly relevant at the abstract level because "
                        f"the retrieved evidence overlaps with: {terms}. [{index}]"
                    ),
                    claim_kind="fact",
                    support_status="supported",
                    citation_indexes=(index,),
                )
            )

        if _asks_for_contradiction(question):
            contradiction_indexes = tuple(
                index
                for index, snippet in enumerate(evidence, start=1)
                if _contains_contradiction_signal(snippet.excerpt)
            )
            if contradiction_indexes:
                paragraphs.append(
                    GeneratedParagraph(
                        text=(
                            "Potential opposing/limiting language appears in the cited abstract evidence. "
                            "Treat this as a review lead, not a verified contradiction. "
                            + " ".join(f"[{index}]" for index in contradiction_indexes)
                        ),
                        claim_kind="system_inference",
                        support_status="mixed",
                        citation_indexes=contradiction_indexes,
                    )
                )
            else:
                paragraphs.append(
                    GeneratedParagraph(
                        text=(
                            "Insufficient evidence: the retrieved abstract snippets do not contain a clear "
                            "contradiction signal. Claim-level full-text review is required."
                        ),
                        claim_kind="system_inference",
                        support_status="insufficient_evidence",
                        citation_indexes=(),
                    )
                )
        return paragraphs


def answer_chat(
    session: Session,
    payload: ChatRequest,
    provider: GroundedAnswerProvider | None = None,
) -> ChatResponse:
    provider = provider or DeterministicEvidenceProvider()
    papers = _scope_papers(session, payload)
    evidence = _build_evidence(payload.question, papers, payload.max_papers)
    paragraphs = provider.generate(payload.question, evidence)
    citations = [
        ChatCitationResponse(
            index=index,
            paper_id=snippet.paper.id,
            paper_title=snippet.paper.title,
            publication_year=snippet.paper.publication_year,
            doi=snippet.paper.doi,
            primary_url=snippet.paper.primary_url,
            source_locator="abstract",
            excerpt=snippet.excerpt,
        )
        for index, snippet in enumerate(evidence, start=1)
    ]
    structural_rate = structural_unsupported_claim_rate(paragraphs)
    return ChatResponse(
        question=payload.question,
        scope_type=payload.scope_type,
        provider=provider.name,
        paragraphs=[
            ChatParagraphResponse(
                text=paragraph.text,
                claim_kind=paragraph.claim_kind,
                support_status=paragraph.support_status,
                citation_indexes=list(paragraph.citation_indexes),
            )
            for paragraph in paragraphs
        ],
        citations=citations,
        structural_unsupported_claim_rate=structural_rate,
        limitations=[
            "The no-key provider does not synthesize novel scholarly claims; "
            "it reports traceable abstract-level evidence.",
            "Contradiction detection is a lexical review signal, not semantic claim verification.",
            "Page-level locators require legally available or user-supplied full text.",
        ],
    )


def structural_unsupported_claim_rate(paragraphs: list[GeneratedParagraph]) -> float:
    assertive = [p for p in paragraphs if p.support_status != "insufficient_evidence"]
    if not assertive:
        return 0.0
    unsupported = [p for p in assertive if not p.citation_indexes]
    return len(unsupported) / len(assertive)


def _scope_papers(session: Session, payload: ChatRequest) -> list[Paper]:
    if payload.scope_type == "corpus":
        ranked = HybridRetrievalService(session).search(
            payload.question,
            mode="hybrid",
            limit=payload.max_papers,
        )
        ids = [row.id for row in ranked]
        papers = session.scalars(select(Paper).where(Paper.id.in_(ids))).all()
        lookup = {paper.id: paper for paper in papers}
        return [lookup[paper_id] for paper_id in ids if paper_id in lookup]

    if payload.scope_type == "papers":
        if not payload.scope_ids:
            raise HTTPException(status_code=422, detail="Paper scope requires scope_ids")
        papers = session.scalars(select(Paper).where(Paper.id.in_(payload.scope_ids))).all()
        return _rank_papers(payload.question, papers)[: payload.max_papers]

    if payload.scope_type == "comparison_set":
        if len(payload.scope_ids) != 1:
            raise HTTPException(status_code=422, detail="Comparison scope requires exactly one scope_id")
        paper_ids = session.scalars(
            select(ComparisonSetPaper.paper_id)
            .where(ComparisonSetPaper.comparison_set_id == payload.scope_ids[0])
            .order_by(ComparisonSetPaper.position)
        ).all()
        if not paper_ids:
            raise HTTPException(status_code=404, detail="Comparison set not found or empty")
        papers = session.scalars(select(Paper).where(Paper.id.in_(paper_ids))).all()
        return _rank_papers(payload.question, papers)[: payload.max_papers]

    raise HTTPException(status_code=422, detail="scope_type must be corpus, papers, or comparison_set")


def _build_evidence(
    question: str,
    papers: list[Paper],
    max_papers: int,
) -> list[EvidenceSnippet]:
    tokens = _query_tokens(question)
    evidence: list[EvidenceSnippet] = []
    for paper in papers[:max_papers]:
        abstract = (paper.abstract or "").strip()
        if not abstract:
            continue
        sentence = _best_sentence(abstract, tokens)
        if not sentence:
            continue
        excerpt = _limit_words(sentence, 28)
        overlap = tuple(sorted(tokens & set(_query_tokens(sentence))))
        evidence.append(EvidenceSnippet(paper=paper, excerpt=excerpt, overlap_terms=overlap))
    return evidence


def _rank_papers(question: str, papers: Sequence[Paper]) -> list[Paper]:
    query_tokens = _query_tokens(question)
    return sorted(
        papers,
        key=lambda paper: (
            -len(query_tokens & set(_query_tokens(f"{paper.title} {paper.abstract or ''}"))),
            -(paper.publication_year or 0),
            str(paper.id),
        ),
    )


def _best_sentence(abstract: str, tokens: set[str]) -> str | None:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", abstract) if part.strip()]
    if not sentences:
        return None
    return max(
        sentences,
        key=lambda sentence: (
            len(tokens & set(_query_tokens(sentence))),
            min(len(sentence), 400),
        ),
    )


def _query_tokens(text: str) -> set[str]:
    stop = {
        "the",
        "and",
        "for",
        "with",
        "what",
        "which",
        "how",
        "does",
        "are",
        "about",
        "from",
        "this",
        "that",
        "artificial",
        "intelligence",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9-]+", text.lower())
        if len(token) > 2 and token not in stop
    }


def _limit_words(text: str, limit: int) -> str:
    words = text.split()
    return " ".join(words[:limit]) + ("…" if len(words) > limit else "")


def _asks_for_contradiction(question: str) -> bool:
    lowered = question.lower()
    return any(term in lowered for term in ("contradict", "opposing", "counter", "반대", "충돌"))


def _contains_contradiction_signal(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in ("not significant", "no significant", "negative", "however", "limited", "failed")
    )
