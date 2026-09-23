from __future__ import annotations

import hashlib
import uuid
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from research_lab.models import Paper, PaperTopic, PaperTopicAssignmentEvidence, Topic
from research_lab.mot_taxonomy import (
    ALL_MOT_CONCEPTS,
    MOT_TAXONOMY_VERSION,
    MotAssignmentCandidate,
    infer_mot_assignments,
)


@dataclass(slots=True)
class MotBackfillResult:
    scanned: int = 0
    papers_with_problem: int = 0
    links_created: int = 0
    evidence_created: int = 0
    assignments_by_kind: dict[str, int] = field(default_factory=dict)
    assignments_by_slug: dict[str, int] = field(default_factory=dict)


def ensure_mot_topics(session: Session) -> dict[str, Topic]:
    existing = {
        topic.slug: topic
        for topic in session.scalars(
            select(Topic).where(Topic.slug.in_([concept.slug for concept in ALL_MOT_CONCEPTS]))
        )
    }
    for concept in ALL_MOT_CONCEPTS:
        topic = existing.get(concept.slug)
        if topic is None:
            topic = Topic(
                slug=concept.slug,
                display_name=concept.display_name,
                kind=concept.kind,
                source="mot_operational_taxonomy",
                source_record_id=MOT_TAXONOMY_VERSION,
                description=concept.description,
            )
            session.add(topic)
            session.flush()
            existing[concept.slug] = topic
            continue
        # Updating the definition metadata is safe: historical assignment
        # evidence keeps its own taxonomy_version and rule_id.
        topic.display_name = concept.display_name
        topic.kind = concept.kind
        topic.source = "mot_operational_taxonomy"
        topic.source_record_id = MOT_TAXONOMY_VERSION
        topic.description = concept.description
    return existing


def classify_paper_mot(
    session: Session,
    paper: Paper,
    *,
    topics_by_slug: dict[str, Topic] | None = None,
    assignment_source: str = "mot_keyword_candidate",
) -> tuple[int, int, list[MotAssignmentCandidate]]:
    topics = topics_by_slug or ensure_mot_topics(session)
    candidates = infer_mot_assignments(paper.title, paper.abstract)
    links_created = 0
    evidence_created = 0

    for candidate in candidates:
        topic = topics[candidate.slug]
        if _human_rejected_current_assignment(session, paper.id, topic.id):
            continue

        link = session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id})
        if link is None:
            session.add(
                PaperTopic(
                    paper_id=paper.id,
                    topic_id=topic.id,
                    score=None,
                    assignment_source=f"{assignment_source}:{MOT_TAXONOMY_VERSION}",
                )
            )
            links_created += 1

        assignment_key = _assignment_key(paper.id, topic.id, candidate)
        existing = session.scalar(
            select(PaperTopicAssignmentEvidence).where(
                PaperTopicAssignmentEvidence.assignment_key == assignment_key
            )
        )
        if existing is None:
            session.add(
                PaperTopicAssignmentEvidence(
                    paper_id=paper.id,
                    topic_id=topic.id,
                    assignment_key=assignment_key,
                    taxonomy_version=MOT_TAXONOMY_VERSION,
                    assignment_source=assignment_source,
                    rule_id=candidate.rule_id,
                    evidence_kind=candidate.evidence_kind,
                    evidence_text=candidate.evidence_text or None,
                    source_locator=candidate.source_locator,
                    matched_terms=list(candidate.matched_terms),
                    review_status="automatic_candidate",
                )
            )
            evidence_created += 1

    return links_created, evidence_created, candidates


def backfill_mot_taxonomy(
    session: Session,
    *,
    limit: int = 0,
    commit_every: int = 500,
    dry_run: bool = False,
) -> MotBackfillResult:
    topics = ensure_mot_topics(session)
    statement = select(Paper).order_by(Paper.id)
    if limit > 0:
        statement = statement.limit(limit)

    result = MotBackfillResult()
    kind_counts: Counter[str] = Counter()
    slug_counts: Counter[str] = Counter()
    for paper in session.scalars(statement).yield_per(max(50, min(commit_every, 1000))):
        links, evidence, candidates = classify_paper_mot(
            session,
            paper,
            topics_by_slug=topics,
        )
        result.scanned += 1
        result.links_created += links
        result.evidence_created += evidence
        if any(candidate.kind == "mot_problem" for candidate in candidates):
            result.papers_with_problem += 1
        for candidate in candidates:
            kind_counts[candidate.kind] += 1
            slug_counts[candidate.slug] += 1

        if not dry_run and commit_every > 0 and result.scanned % commit_every == 0:
            session.commit()

    result.assignments_by_kind = dict(sorted(kind_counts.items()))
    result.assignments_by_slug = dict(sorted(slug_counts.items()))
    if dry_run:
        session.rollback()
    else:
        session.commit()
    return result


def remove_current_automatic_mot_assignments(session: Session, paper_id: uuid.UUID) -> int:
    """Remove only current automatic MOT links for one paper.

    Historical evidence rows are intentionally retained. Human-confirmed links,
    legacy research axes, notes, cards, saved searches and user state are not
    touched. This is useful before re-running a changed taxonomy for a paper.
    """
    automatic_topic_ids = select(PaperTopicAssignmentEvidence.topic_id).where(
        PaperTopicAssignmentEvidence.paper_id == paper_id,
        PaperTopicAssignmentEvidence.taxonomy_version == MOT_TAXONOMY_VERSION,
        PaperTopicAssignmentEvidence.review_status == "automatic_candidate",
    )
    result = session.execute(
        delete(PaperTopic).where(
            PaperTopic.paper_id == paper_id,
            PaperTopic.topic_id.in_(automatic_topic_ids),
            PaperTopic.assignment_source.in_(
                (
                    f"mot_keyword_candidate:{MOT_TAXONOMY_VERSION}",
                    f"mot_pilot_keyword_candidate:{MOT_TAXONOMY_VERSION}",
                )
            ),
        )
    )
    return int(getattr(result, "rowcount", 0) or 0)


def _human_rejected_current_assignment(
    session: Session,
    paper_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> bool:
    return (
        session.scalar(
            select(PaperTopicAssignmentEvidence.id)
            .where(
                PaperTopicAssignmentEvidence.paper_id == paper_id,
                PaperTopicAssignmentEvidence.topic_id == topic_id,
                PaperTopicAssignmentEvidence.taxonomy_version == MOT_TAXONOMY_VERSION,
                PaperTopicAssignmentEvidence.review_status == "human_rejected",
            )
            .limit(1)
        )
        is not None
    )


def _assignment_key(
    paper_id: uuid.UUID,
    topic_id: uuid.UUID,
    candidate: MotAssignmentCandidate,
) -> str:
    payload = "|".join(
        (
            str(paper_id),
            str(topic_id),
            MOT_TAXONOMY_VERSION,
            candidate.rule_id,
            candidate.source_locator,
            *candidate.matched_terms,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
