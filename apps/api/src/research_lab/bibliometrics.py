from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import and_, case, desc, extract, func, select
from sqlalchemy.orm import Session, aliased

from research_lab.models import (
    Author,
    AuthorInstitution,
    Institution,
    Paper,
    PaperAuthor,
    PaperContentProfile,
    PaperTopic,
    PatentDocument,
    Topic,
    Venue,
)
from research_lab.schemas import (
    BibliometricEdge,
    BibliometricNode,
    BibliometricRelationsResponse,
    LandscapeAxis,
    LandscapeLeader,
    LandscapeYear,
    PaperPatentBridgeMetric,
    PatentMetric,
    PatentYearMetric,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "into",
    "using",
    "based",
    "research",
    "technology",
    "technologies",
    "management",
}


def get_bibliometric_relations(
    session: Session,
    *,
    topic_limit: int = 18,
    institution_limit: int = 14,
    edge_limit: int = 48,
    patent_sample_limit: int = 50_000,
) -> BibliometricRelationsResponse:
    total_papers = session.scalar(select(func.count()).select_from(Paper)) or 0
    full_text_papers = session.scalar(
        select(func.count())
        .select_from(PaperContentProfile)
        .where(PaperContentProfile.full_text_status == "available")
    ) or 0
    latest_year = session.scalar(select(func.max(Paper.publication_year)))
    latest_year = int(latest_year) if latest_year else datetime.now(UTC).year
    recent_from = latest_year - 1

    axes = _overview_topics(session, kind="research_axis", limit=14)
    subaxes = _overview_topics(session, kind="research_subaxis", limit=30)
    year_rows = session.execute(
        select(Paper.publication_year, func.count(Paper.id))
        .where(Paper.publication_year.is_not(None))
        .group_by(Paper.publication_year)
        .order_by(Paper.publication_year)
    ).all()
    author_rows = session.execute(
        select(
            Author.display_name,
            func.count(func.distinct(PaperAuthor.paper_id)).label("paper_count"),
        )
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .group_by(Author.id, Author.display_name)
        .order_by(desc("paper_count"), Author.display_name)
        .limit(10)
    ).all()
    venue_rows = session.execute(
        select(Venue.name, func.count(Paper.id).label("paper_count"))
        .join(Paper, Paper.venue_id == Venue.id)
        .group_by(Venue.id, Venue.name)
        .order_by(desc("paper_count"), Venue.name)
        .limit(10)
    ).all()

    topic_rows = _top_topics(session, recent_from=recent_from, limit=topic_limit)
    topic_nodes = [
        BibliometricNode(
            id=str(topic_id),
            label=display_name,
            count=int(paper_count),
            recent_count=int(recent_count),
            kind="topic",
        )
        for topic_id, _slug, display_name, paper_count, recent_count in topic_rows
    ]
    topic_ids = [row[0] for row in topic_rows]
    topic_edges = _topic_edges(session, topic_ids=topic_ids, limit=edge_limit)

    institution_rows = session.execute(
        select(
            Institution.id,
            Institution.name,
            Institution.country_code,
            func.count(func.distinct(PaperAuthor.paper_id)).label("paper_count"),
            func.count(
                func.distinct(
                    case((Paper.publication_year >= recent_from, PaperAuthor.paper_id))
                )
            ).label("recent_count"),
        )
        .join(AuthorInstitution, AuthorInstitution.institution_id == Institution.id)
        .join(PaperAuthor, PaperAuthor.author_id == AuthorInstitution.author_id)
        .join(Paper, Paper.id == PaperAuthor.paper_id)
        .group_by(Institution.id, Institution.name, Institution.country_code)
        .order_by(desc("paper_count"), Institution.name)
        .limit(institution_limit)
    ).all()
    institution_nodes = [
        BibliometricNode(
            id=str(institution_id),
            label=name,
            count=int(paper_count),
            recent_count=int(recent_count),
            country_code=country_code,
            kind="institution",
        )
        for institution_id, name, country_code, paper_count, recent_count in institution_rows
    ]
    institution_ids = [row[0] for row in institution_rows]
    institution_edges = _institution_edges(
        session,
        institution_ids=institution_ids,
        limit=edge_limit,
    )

    patent_total = session.scalar(select(func.count()).select_from(PatentDocument)) or 0
    patent_years = _patent_years(session)
    patent_jurisdictions = _patent_jurisdictions(session)
    patent_rows = session.execute(
        select(
            PatentDocument.applicants,
            PatentDocument.cpc_codes,
            PatentDocument.title,
            PatentDocument.abstract,
        ).limit(patent_sample_limit)
    ).all()
    applicant_counts: Counter[str] = Counter()
    cpc_counts: Counter[str] = Counter()
    for applicants, cpc_codes, _title, _abstract in patent_rows:
        applicant_counts.update({str(value).strip() for value in applicants or [] if str(value).strip()})
        cpc_counts.update(
            {
                normalized
                for value in cpc_codes or []
                if (normalized := _normalize_cpc(str(value)))
            }
        )

    paper_patent_bridge = _paper_patent_bridge(topic_rows, patent_rows)
    caveats = [
        (
            "Topic-network edges are corpus-local co-occurrence links between stored taxonomy "
            "assignments; they are not author-declared conceptual relationships."
        ),
        (
            "Institution links represent shared-paper collaboration footprints. AuthorInstitution "
            "does not preserve year-specific affiliation history, so this view must not be "
            "interpreted as brain drain or researcher migration."
        ),
        (
            "Patent analytics activate only for imported PatentDocument records. WIPS ON imports "
            "are currently the supported patent evidence path."
        ),
        (
            "Paper-patent bridge rows use conservative lexical topic matching and are discovery "
            "leads, not proof of science-to-technology causality."
        ),
    ]
    if patent_total > len(patent_rows):
        caveats.append(
            "Applicant, CPC, and lexical bridge metrics use the first "
            f"{len(patent_rows):,} patent rows out of {patent_total:,}."
        )

    return BibliometricRelationsResponse(
        generated_at=datetime.now(UTC),
        recent_window=f"{recent_from}–{latest_year}",
        total_papers=int(total_papers),
        full_text_papers=int(full_text_papers),
        axes=axes,
        subaxes=subaxes,
        years=[
            LandscapeYear(year=int(year), paper_count=int(count))
            for year, count in year_rows
            if year is not None
        ],
        top_authors=[LandscapeLeader(name=name, paper_count=int(count)) for name, count in author_rows],
        top_institutions=[
            LandscapeLeader(name=name, paper_count=int(count))
            for _institution_id, name, _country_code, count, _recent in institution_rows[:10]
        ],
        top_venues=[LandscapeLeader(name=name, paper_count=int(count)) for name, count in venue_rows],
        topic_nodes=topic_nodes,
        topic_edges=topic_edges,
        institution_nodes=institution_nodes,
        institution_edges=institution_edges,
        patent_total=int(patent_total),
        patent_years=patent_years,
        patent_jurisdictions=patent_jurisdictions,
        patent_applicants=[
            PatentMetric(label=label, count=count)
            for label, count in applicant_counts.most_common(12)
        ],
        patent_cpc=[
            PatentMetric(label=label, count=count) for label, count in cpc_counts.most_common(14)
        ],
        paper_patent_bridge=paper_patent_bridge,
        caveats=caveats,
    )


def _overview_topics(session: Session, *, kind: str, limit: int) -> list[LandscapeAxis]:
    rows = session.execute(
        select(
            Topic.id,
            Topic.slug,
            Topic.display_name,
            func.count(func.distinct(PaperTopic.paper_id)).label("paper_count"),
        )
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .where(Topic.kind == kind)
        .group_by(Topic.id, Topic.slug, Topic.display_name)
        .order_by(desc("paper_count"), Topic.display_name)
        .limit(limit)
    ).all()
    topic_ids = [row[0] for row in rows]
    years_by_topic: dict[object, list[LandscapeYear]] = {topic_id: [] for topic_id in topic_ids}
    if topic_ids:
        year_rows = session.execute(
            select(
                PaperTopic.topic_id,
                Paper.publication_year,
                func.count(func.distinct(Paper.id)).label("paper_count"),
            )
            .join(Paper, Paper.id == PaperTopic.paper_id)
            .where(
                PaperTopic.topic_id.in_(topic_ids),
                Paper.publication_year.is_not(None),
            )
            .group_by(PaperTopic.topic_id, Paper.publication_year)
            .order_by(PaperTopic.topic_id, Paper.publication_year)
        ).all()
        for topic_id, year, count in year_rows:
            if year is not None:
                years_by_topic.setdefault(topic_id, []).append(
                    LandscapeYear(year=int(year), paper_count=int(count))
                )
    return [
        LandscapeAxis(
            slug=slug,
            display_name=display_name,
            paper_count=int(paper_count),
            years=years_by_topic.get(topic_id, []),
        )
        for topic_id, slug, display_name, paper_count in rows
    ]


def _top_topics(session: Session, *, recent_from: int, limit: int):
    def query(kind: str):
        return session.execute(
            select(
                Topic.id,
                Topic.slug,
                Topic.display_name,
                func.count(func.distinct(PaperTopic.paper_id)).label("paper_count"),
                func.count(
                    func.distinct(case((Paper.publication_year >= recent_from, Paper.id)))
                ).label("recent_count"),
            )
            .join(PaperTopic, PaperTopic.topic_id == Topic.id)
            .join(Paper, Paper.id == PaperTopic.paper_id)
            .where(Topic.kind == kind)
            .group_by(Topic.id, Topic.slug, Topic.display_name)
            .order_by(desc("paper_count"), Topic.display_name)
            .limit(limit)
        ).all()

    rows = query("research_subaxis")
    if not rows:
        rows = query("research_axis")
    return rows


def _topic_edges(session: Session, *, topic_ids: list[object], limit: int) -> list[BibliometricEdge]:
    if len(topic_ids) < 2:
        return []
    left = aliased(PaperTopic)
    right = aliased(PaperTopic)
    rows = session.execute(
        select(
            left.topic_id,
            right.topic_id,
            func.count(func.distinct(left.paper_id)).label("weight"),
        )
        .join(
            right,
            and_(
                right.paper_id == left.paper_id,
                right.topic_id > left.topic_id,
            ),
        )
        .where(left.topic_id.in_(topic_ids), right.topic_id.in_(topic_ids))
        .group_by(left.topic_id, right.topic_id)
        .order_by(desc("weight"))
        .limit(limit)
    ).all()
    return [
        BibliometricEdge(
            source=str(source),
            target=str(target),
            weight=int(weight),
            kind="topic_cooccurrence",
        )
        for source, target, weight in rows
    ]


def _institution_edges(
    session: Session,
    *,
    institution_ids: list[object],
    limit: int,
) -> list[BibliometricEdge]:
    if len(institution_ids) < 2:
        return []
    paper_institution = (
        select(
            PaperAuthor.paper_id.label("paper_id"),
            AuthorInstitution.institution_id.label("institution_id"),
        )
        .join(AuthorInstitution, AuthorInstitution.author_id == PaperAuthor.author_id)
        .where(AuthorInstitution.institution_id.in_(institution_ids))
        .distinct()
        .subquery()
    )
    left = paper_institution.alias("left_institution")
    right = paper_institution.alias("right_institution")
    rows = session.execute(
        select(
            left.c.institution_id,
            right.c.institution_id,
            func.count(func.distinct(left.c.paper_id)).label("weight"),
        )
        .join(
            right,
            and_(
                right.c.paper_id == left.c.paper_id,
                right.c.institution_id > left.c.institution_id,
            ),
        )
        .group_by(left.c.institution_id, right.c.institution_id)
        .order_by(desc("weight"))
        .limit(limit)
    ).all()
    return [
        BibliometricEdge(
            source=str(source),
            target=str(target),
            weight=int(weight),
            kind="institution_collaboration",
        )
        for source, target, weight in rows
    ]


def _patent_years(session: Session) -> list[PatentYearMetric]:
    rows = session.execute(
        select(
            extract("year", PatentDocument.filing_date).label("year"),
            func.count(PatentDocument.id),
        )
        .where(PatentDocument.filing_date.is_not(None))
        .group_by("year")
        .order_by("year")
    ).all()
    return [PatentYearMetric(year=int(year), count=int(count)) for year, count in rows if year]


def _patent_jurisdictions(session: Session) -> list[PatentMetric]:
    rows = session.execute(
        select(PatentDocument.jurisdiction, func.count(PatentDocument.id).label("count"))
        .where(PatentDocument.jurisdiction.is_not(None))
        .group_by(PatentDocument.jurisdiction)
        .order_by(desc("count"))
        .limit(12)
    ).all()
    return [PatentMetric(label=str(label), count=int(count)) for label, count in rows if label]


def _normalize_cpc(value: str) -> str:
    compact = re.sub(r"\s+", "", value.upper())
    if not compact:
        return ""
    return compact.split("/")[0][:12]


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _paper_patent_bridge(topic_rows, patent_rows) -> list[PaperPatentBridgeMetric]:
    if not topic_rows or not patent_rows:
        return []
    topic_tokens = [(display_name, _tokens(display_name)) for _, _, display_name, _, _ in topic_rows]
    counts: Counter[tuple[str, str]] = Counter()
    for _applicants, cpc_codes, title, abstract in patent_rows:
        text_tokens = _tokens(f"{title or ''} {abstract or ''}")
        if not text_tokens:
            continue
        patent_concept = next(
            (_normalize_cpc(str(value)) for value in cpc_codes or [] if _normalize_cpc(str(value))),
            "Unclassified patent text",
        )
        for topic_label, tokens in topic_tokens:
            if not tokens:
                continue
            required = 1 if len(tokens) == 1 else min(2, len(tokens))
            if len(tokens & text_tokens) >= required:
                counts[(topic_label, patent_concept)] += 1
    return [
        PaperPatentBridgeMetric(
            paper_topic=topic,
            patent_concept=concept,
            count=count,
        )
        for (topic, concept), count in counts.most_common(24)
    ]
