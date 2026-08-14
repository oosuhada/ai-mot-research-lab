from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import and_, desc, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from research_lab.models import (
    Author,
    AuthorInstitution,
    CitationSnapshot,
    FullTextQueueItem,
    IngestionRun,
    Institution,
    Paper,
    PaperAuthor,
    PaperChunk,
    PaperContentProfile,
    PaperLocalization,
    PaperNote,
    PaperTag,
    PaperTopic,
    ReadingQueue,
    SavedSearch,
    Tag,
    Topic,
    Venue,
)
from research_lab.retrieval import SearchFilters
from research_lab.schemas import (
    AuthorSummary,
    BrowseResponse,
    LandscapeAxis,
    LandscapeLeader,
    LandscapeResponse,
    LandscapeYear,
    PaperContentProfileResponse,
    PaperDetail,
    PaperLocalizationResponse,
    PaperNoteResponse,
    ReadingQueueState,
    SavedSearchCreate,
    SavedSearchResponse,
    SearchResponseItem,
    TagResponse,
    TopicSummary,
    VenueSummary,
)

ReadingStatus = Literal["unread", "skimming", "reading", "read", "archived"]


@dataclass(frozen=True, slots=True)
class BrowseCursor:
    created_at: datetime
    paper_id: uuid.UUID
    offset: int
    direction: Literal["after", "before"]


def encode_browse_cursor(cursor: BrowseCursor) -> str:
    payload = json.dumps(
        {
            "created_at": cursor.created_at.isoformat(),
            "paper_id": str(cursor.paper_id),
            "offset": cursor.offset,
            "direction": cursor.direction,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def decode_browse_cursor(value: str) -> BrowseCursor:
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding).decode("utf-8"))
        created_at = datetime.fromisoformat(str(payload["created_at"]))
        if created_at.tzinfo is None:
            raise ValueError("cursor timestamp must be timezone-aware")
        paper_id = uuid.UUID(str(payload["paper_id"]))
        offset = int(payload["offset"])
        direction = str(payload["direction"])
        if offset < 0 or direction not in {"after", "before"}:
            raise ValueError("cursor fields are invalid")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid paper browse cursor") from exc
    return BrowseCursor(
        created_at=created_at,
        paper_id=paper_id,
        offset=offset,
        direction=cast(Literal["after", "before"], direction),
    )


def browse_papers(
    session: Session,
    *,
    limit: int,
    cursor: str | None,
    filters: SearchFilters,
) -> BrowseResponse:
    clauses = _browse_filter_clauses(filters)
    parsed_cursor = decode_browse_cursor(cursor) if cursor else None
    offset = parsed_cursor.offset if parsed_cursor else 0

    venue_name = (
        select(Venue.name)
        .where(Venue.id == Paper.venue_id)
        .limit(1)
        .scalar_subquery()
    )
    citation_count = (
        select(CitationSnapshot.citation_count)
        .where(CitationSnapshot.paper_id == Paper.id)
        .order_by(CitationSnapshot.captured_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    reading_priority = (
        select(ReadingQueue.priority)
        .where(ReadingQueue.paper_id == Paper.id)
        .limit(1)
        .scalar_subquery()
    )

    total = session.scalar(select(func.count(Paper.id)).where(*clauses)) or 0
    statement = select(
        Paper,
        venue_name.label("venue_name"),
        func.coalesce(citation_count, 0).label("citation_count"),
        func.coalesce(reading_priority, 0).label("reading_priority"),
    ).where(*clauses)

    if parsed_cursor is not None:
        if parsed_cursor.direction == "after":
            statement = statement.where(
                or_(
                    Paper.created_at < parsed_cursor.created_at,
                    and_(
                        Paper.created_at == parsed_cursor.created_at,
                        Paper.id < parsed_cursor.paper_id,
                    ),
                )
            ).order_by(Paper.created_at.desc(), Paper.id.desc())
        else:
            statement = statement.where(
                or_(
                    Paper.created_at > parsed_cursor.created_at,
                    and_(
                        Paper.created_at == parsed_cursor.created_at,
                        Paper.id > parsed_cursor.paper_id,
                    ),
                )
            ).order_by(Paper.created_at.asc(), Paper.id.asc())
    else:
        statement = statement.order_by(Paper.created_at.desc(), Paper.id.desc())

    rows = list(session.execute(statement.limit(limit)).all())
    if parsed_cursor is not None and parsed_cursor.direction == "before":
        rows.reverse()

    items = [
        SearchResponseItem(
            id=paper.id,
            doi=paper.doi,
            openalex_id=paper.openalex_id,
            title=paper.title,
            abstract=paper.abstract,
            publication_date=paper.publication_date,
            publication_year=paper.publication_year,
            work_type=paper.work_type,
            venue_name=row.venue_name,
            oa_status=paper.oa_status,
            is_oa=paper.is_oa,
            primary_url=paper.primary_url,
            pdf_url=paper.pdf_url,
            license=paper.license,
            lexical_rank=None,
            semantic_rank=None,
            fused_score=0.0,
            rerank_score=None,
            matched_source="metadata",
            matched_locator=None,
            matched_excerpt=None,
            citation_count=int(row.citation_count),
            reading_priority=int(row.reading_priority),
        )
        for row in rows
        for paper in [row.Paper]
    ]

    has_previous = offset > 0 and bool(rows)
    has_more = offset + len(rows) < total
    previous_cursor = None
    next_cursor = None
    if rows and has_previous:
        first_paper = rows[0].Paper
        previous_cursor = encode_browse_cursor(
            BrowseCursor(
                created_at=first_paper.created_at,
                paper_id=first_paper.id,
                offset=max(0, offset - limit),
                direction="before",
            )
        )
    if rows and has_more:
        last_paper = rows[-1].Paper
        next_cursor = encode_browse_cursor(
            BrowseCursor(
                created_at=last_paper.created_at,
                paper_id=last_paper.id,
                offset=offset + len(rows),
                direction="after",
            )
        )

    return BrowseResponse(
        total=total,
        offset=offset,
        limit=limit,
        has_previous=has_previous,
        has_more=has_more,
        previous_cursor=previous_cursor,
        next_cursor=next_cursor,
        items=items,
    )


def _browse_filter_clauses(filters: SearchFilters) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if filters.year_from is not None:
        clauses.append(Paper.publication_year >= filters.year_from)
    if filters.year_to is not None:
        clauses.append(Paper.publication_year <= filters.year_to)
    if filters.work_type:
        clauses.append(Paper.work_type == filters.work_type)
    if filters.is_oa is not None:
        clauses.append(Paper.is_oa.is_(filters.is_oa))
    if filters.venue:
        clauses.append(
            exists(
                select(Venue.id).where(
                    Venue.id == Paper.venue_id,
                    Venue.name.ilike(f"%{filters.venue}%"),
                )
            )
        )
    if filters.author:
        clauses.append(
            exists(
                select(PaperAuthor.paper_id)
                .join(Author, Author.id == PaperAuthor.author_id)
                .where(PaperAuthor.paper_id == Paper.id, Author.display_name.ilike(f"%{filters.author}%"))
            )
        )
    if filters.axis:
        clauses.append(
            exists(
                select(PaperTopic.paper_id)
                .join(Topic, Topic.id == PaperTopic.topic_id)
                .where(
                    PaperTopic.paper_id == Paper.id,
                    Topic.kind == "research_axis",
                    Topic.slug == filters.axis,
                )
            )
        )
    if filters.methodology:
        methodology_slug = filters.methodology
        if not methodology_slug.startswith("methodology-"):
            methodology_slug = f"methodology-{methodology_slug}"
        clauses.append(
            exists(
                select(PaperTopic.paper_id)
                .join(Topic, Topic.id == PaperTopic.topic_id)
                .where(
                    PaperTopic.paper_id == Paper.id,
                    Topic.kind == "methodology",
                    Topic.slug == methodology_slug,
                )
            )
        )
    if filters.reading_status:
        clauses.append(
            exists(
                select(ReadingQueue.paper_id).where(
                    ReadingQueue.paper_id == Paper.id,
                    ReadingQueue.status == filters.reading_status,
                )
            )
        )
    if filters.tag:
        clauses.append(
            exists(
                select(PaperTag.paper_id)
                .join(Tag, Tag.id == PaperTag.tag_id)
                .where(PaperTag.paper_id == Paper.id, Tag.name.ilike(f"%{filters.tag}%"))
            )
        )
    return clauses


def get_landscape(session: Session) -> LandscapeResponse:
    total_papers = session.scalar(select(func.count()).select_from(Paper)) or 0
    oa_papers = session.scalar(select(func.count()).select_from(Paper).where(Paper.is_oa.is_(True))) or 0
    abstract_papers = session.scalar(
        select(func.count())
        .select_from(Paper)
        .where(Paper.abstract.is_not(None), func.length(func.trim(Paper.abstract)) > 0)
    ) or 0
    full_text_papers = session.scalar(select(func.count(func.distinct(PaperChunk.paper_id)))) or 0
    full_text_queued = session.scalar(
        select(func.count()).select_from(FullTextQueueItem).where(
            FullTextQueueItem.status.in_(["pending", "processing"])
        )
    ) or 0

    axis_rows = session.execute(
        select(Topic.slug, Topic.display_name, func.count(func.distinct(PaperTopic.paper_id)))
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == "research_axis")
        .group_by(Topic.slug, Topic.display_name)
        .order_by(Topic.display_name)
    ).all()
    methodology_rows = session.execute(
        select(Topic.slug, Topic.display_name, func.count(func.distinct(PaperTopic.paper_id)))
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == "methodology")
        .group_by(Topic.slug, Topic.display_name)
        .order_by(desc(func.count(func.distinct(PaperTopic.paper_id))), Topic.display_name)
    ).all()
    subaxis_rows = session.execute(
        select(Topic.slug, Topic.display_name, func.count(func.distinct(PaperTopic.paper_id)))
        .outerjoin(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == "research_subaxis")
        .group_by(Topic.slug, Topic.display_name)
        .order_by(desc(func.count(func.distinct(PaperTopic.paper_id))), Topic.display_name)
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
    last_ingestion_at = session.scalar(
        select(func.max(IngestionRun.finished_at)).where(
            IngestionRun.status.in_(["completed", "completed_with_errors"])
        )
    )

    return LandscapeResponse(
        total_papers=total_papers,
        abstract_papers=abstract_papers,
        full_text_papers=full_text_papers,
        full_text_queued=full_text_queued,
        oa_papers=oa_papers,
        axes=[
            LandscapeAxis(slug=slug, display_name=display_name, paper_count=int(count))
            for slug, display_name, count in axis_rows
        ],
        subaxes=[
            LandscapeAxis(slug=slug, display_name=display_name, paper_count=int(count))
            for slug, display_name, count in subaxis_rows
        ],
        methodologies=[
            LandscapeAxis(slug=slug, display_name=display_name, paper_count=int(count))
            for slug, display_name, count in methodology_rows
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
        last_ingestion_at=last_ingestion_at,
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
    content_profile = session.get(PaperContentProfile, paper.id)
    localizations = list(
        session.scalars(
            select(PaperLocalization)
            .where(PaperLocalization.paper_id == paper.id)
            .order_by(PaperLocalization.locale)
        )
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
        content_profile=PaperContentProfileResponse(
            abstract_status=(
                content_profile.abstract_status
                if content_profile
                else "available"
                if paper.abstract
                else "missing"
            ),
            full_text_status=content_profile.full_text_status if content_profile else "not_requested",
            full_text_access=content_profile.full_text_access if content_profile else "unknown",
            rights_status=content_profile.rights_status if content_profile else "unknown",
            full_text_priority=content_profile.full_text_priority if content_profile else 0,
        ),
        localizations=[
            PaperLocalizationResponse(
                locale=localization.locale,
                title=localization.title,
                abstract=localization.abstract,
                keywords=list(localization.keywords),
                status=localization.status,
                provider=localization.provider,
                model=localization.model,
                translated_at=localization.translated_at,
            )
            for localization in localizations
        ],
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
