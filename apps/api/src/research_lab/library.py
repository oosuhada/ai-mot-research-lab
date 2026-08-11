from __future__ import annotations

import uuid
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from research_lab.models import (
    Author,
    AuthorInstitution,
    CitationSnapshot,
    Institution,
    Paper,
    PaperAuthor,
    PaperNote,
    PaperTag,
    PaperTopic,
    ReadingQueue,
    SavedSearch,
    Tag,
    Topic,
    Venue,
)
from research_lab.schemas import (
    AuthorSummary,
    LandscapeAxis,
    LandscapeLeader,
    LandscapeResponse,
    LandscapeYear,
    PaperDetail,
    PaperNoteResponse,
    ReadingQueueState,
    SavedSearchCreate,
    SavedSearchResponse,
    TagResponse,
    TopicSummary,
    VenueSummary,
)

ReadingStatus = Literal["unread", "skimming", "reading", "read", "archived"]


def get_landscape(session: Session) -> LandscapeResponse:
    total_papers = session.scalar(select(func.count()).select_from(Paper)) or 0
    oa_papers = session.scalar(select(func.count()).select_from(Paper).where(Paper.is_oa.is_(True))) or 0

    axis_rows = session.execute(
        select(Topic.slug, Topic.display_name, func.count(func.distinct(PaperTopic.paper_id)))
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == "research_axis")
        .group_by(Topic.slug, Topic.display_name)
        .order_by(Topic.display_name)
    ).all()
    year_rows = session.execute(
        select(Paper.publication_year, func.count(Paper.id))
        .where(Paper.publication_year.is_not(None))
        .group_by(Paper.publication_year)
        .order_by(Paper.publication_year)
    ).all()
    author_rows = session.execute(
        select(Author.display_name, func.count(func.distinct(PaperAuthor.paper_id)).label("paper_count"))
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .group_by(Author.id, Author.display_name)
        .order_by(desc("paper_count"), Author.display_name)
        .limit(10)
    ).all()
    institution_rows = session.execute(
        select(
            Institution.name,
            func.count(func.distinct(PaperAuthor.paper_id)).label("paper_count"),
        )
        .join(AuthorInstitution, AuthorInstitution.institution_id == Institution.id)
        .join(PaperAuthor, PaperAuthor.author_id == AuthorInstitution.author_id)
        .group_by(Institution.id, Institution.name)
        .order_by(desc("paper_count"), Institution.name)
        .limit(10)
    ).all()
    venue_rows = session.execute(
        select(Venue.name, func.count(Paper.id).label("paper_count"))
        .join(Paper, Paper.venue_id == Venue.id)
        .group_by(Venue.id, Venue.name)
        .order_by(desc("paper_count"), Venue.name)
        .limit(10)
    ).all()

    return LandscapeResponse(
        total_papers=total_papers,
        oa_papers=oa_papers,
        axes=[
            LandscapeAxis(slug=slug, display_name=display_name, paper_count=int(count))
            for slug, display_name, count in axis_rows
        ],
        years=[
            LandscapeYear(year=int(year), paper_count=int(count))
            for year, count in year_rows
            if year is not None
        ],
        top_authors=[LandscapeLeader(name=name, paper_count=int(count)) for name, count in author_rows],
        top_institutions=[
            LandscapeLeader(name=name, paper_count=int(count)) for name, count in institution_rows
        ],
        top_venues=[LandscapeLeader(name=name, paper_count=int(count)) for name, count in venue_rows],
    )


def get_paper_detail(session: Session, paper_id: uuid.UUID) -> PaperDetail:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    venue = session.get(Venue, paper.venue_id) if paper.venue_id else None
    author_rows = session.execute(
        select(Author)
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .where(PaperAuthor.paper_id == paper.id)
        .order_by(PaperAuthor.author_position, Author.display_name)
    ).scalars()
    topic_rows = session.execute(
        select(Topic, PaperTopic.assignment_source)
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(PaperTopic.paper_id == paper.id)
        .order_by(Topic.kind, Topic.display_name)
    ).all()
    reading = session.scalar(select(ReadingQueue).where(ReadingQueue.paper_id == paper.id))
    notes = list(
        session.scalars(
            select(PaperNote)
            .where(PaperNote.paper_id == paper.id)
            .order_by(PaperNote.created_at.desc())
        )
    )
    tags = list(
        session.scalars(
            select(Tag)
            .join(PaperTag, PaperTag.tag_id == Tag.id)
            .where(PaperTag.paper_id == paper.id)
            .order_by(Tag.name)
        )
    )
    latest_snapshot = session.scalar(
        select(CitationSnapshot)
        .where(CitationSnapshot.paper_id == paper.id)
        .order_by(CitationSnapshot.captured_at.desc())
        .limit(1)
    )

    return PaperDetail(
        id=paper.id,
        doi=paper.doi,
        openalex_id=paper.openalex_id,
        title=paper.title,
        abstract=paper.abstract,
        publication_date=paper.publication_date,
        publication_year=paper.publication_year,
        work_type=paper.work_type,
        oa_status=paper.oa_status,
        is_oa=paper.is_oa,
        primary_url=paper.primary_url,
        pdf_url=paper.pdf_url,
        license=paper.license,
        language=paper.language,
        publisher=paper.publisher,
        retraction_status=paper.retraction_status,
        correction_status=paper.correction_status,
        primary_source=paper.primary_source,
        source_record_id=paper.source_record_id,
        retrieved_at=paper.retrieved_at,
        provenance=paper.provenance,
        venue=(
            VenueSummary(
                id=venue.id,
                name=venue.name,
                publisher=venue.publisher,
                venue_type=venue.venue_type,
            )
            if venue
            else None
        ),
        authors=[
            AuthorSummary(
                id=author.id,
                display_name=author.display_name,
                openalex_id=author.openalex_id,
                orcid=author.orcid,
            )
            for author in author_rows
        ],
        topics=[
            TopicSummary(
                slug=topic.slug,
                display_name=topic.display_name,
                kind=topic.kind,
                assignment_source=assignment_source,
            )
            for topic, assignment_source in topic_rows
        ],
        reading=(
            ReadingQueueState(status=cast(ReadingStatus, reading.status), priority=reading.priority)
            if reading
            else None
        ),
        notes=[
            PaperNoteResponse(
                id=note.id,
                note_markdown=note.note_markdown,
                source_locator=note.source_locator,
                created_at=note.created_at,
                updated_at=note.updated_at,
            )
            for note in notes
        ],
        tags=[TagResponse(id=tag.id, name=tag.name) for tag in tags],
        latest_citation_count=latest_snapshot.citation_count if latest_snapshot else None,
        latest_citation_snapshot_at=latest_snapshot.captured_at if latest_snapshot else None,
    )


def set_reading_state(
    session: Session,
    paper_id: uuid.UUID,
    *,
    status: str,
    priority: int,
) -> ReadingQueueState:
    _require_paper(session, paper_id)
    row = session.scalar(select(ReadingQueue).where(ReadingQueue.paper_id == paper_id))
    if row is None:
        row = ReadingQueue(paper_id=paper_id, status=status, priority=priority)
        session.add(row)
    else:
        row.status = status
        row.priority = priority
    session.commit()
    return ReadingQueueState(status=cast(ReadingStatus, row.status), priority=row.priority)


def add_note(
    session: Session,
    paper_id: uuid.UUID,
    *,
    note_markdown: str,
    source_locator: str | None,
) -> PaperNoteResponse:
    _require_paper(session, paper_id)
    note = PaperNote(
        paper_id=paper_id,
        note_markdown=note_markdown,
        source_locator=source_locator,
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return PaperNoteResponse(
        id=note.id,
        note_markdown=note.note_markdown,
        source_locator=note.source_locator,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def delete_note(session: Session, note_id: uuid.UUID) -> None:
    note = session.get(PaperNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    session.delete(note)
    session.commit()


def assign_tag(session: Session, paper_id: uuid.UUID, name: str) -> TagResponse:
    _require_paper(session, paper_id)
    normalized_name = " ".join(name.strip().split())
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Tag name cannot be empty")
    tag = session.scalar(select(Tag).where(func.lower(Tag.name) == normalized_name.lower()))
    if tag is None:
        tag = Tag(name=normalized_name)
        session.add(tag)
        session.flush()
    link = session.get(PaperTag, {"paper_id": paper_id, "tag_id": tag.id})
    if link is None:
        session.add(PaperTag(paper_id=paper_id, tag_id=tag.id))
    session.commit()
    return TagResponse(id=tag.id, name=tag.name)


def remove_tag(session: Session, paper_id: uuid.UUID, tag_name: str) -> None:
    tag = session.scalar(select(Tag).where(func.lower(Tag.name) == tag_name.lower()))
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    link = session.get(PaperTag, {"paper_id": paper_id, "tag_id": tag.id})
    if link is None:
        raise HTTPException(status_code=404, detail="Tag is not assigned to this paper")
    session.delete(link)
    session.commit()


def create_saved_search(session: Session, payload: SavedSearchCreate) -> SavedSearchResponse:
    saved = SavedSearch(name=payload.name, query_text=payload.query_text, filters=dict(payload.filters))
    session.add(saved)
    session.commit()
    session.refresh(saved)
    return _saved_search_response(saved)


def list_saved_searches(session: Session) -> list[SavedSearchResponse]:
    rows = session.scalars(select(SavedSearch).order_by(SavedSearch.created_at.desc())).all()
    return [_saved_search_response(saved) for saved in rows]


def _saved_search_response(saved: SavedSearch) -> SavedSearchResponse:
    return SavedSearchResponse(
        id=saved.id,
        name=saved.name,
        query_text=saved.query_text,
        filters=dict(saved.filters),
        created_at=saved.created_at,
    )


def _require_paper(session: Session, paper_id: uuid.UUID) -> Paper:
    paper = session.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper

