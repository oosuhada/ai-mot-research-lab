from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.bibliometrics import get_bibliometric_relations
from research_lab.models import (
    Author,
    AuthorInstitution,
    Base,
    Institution,
    Paper,
    PaperAuthor,
    PaperTopic,
    PatentDocument,
    Topic,
)


def _paper(title: str, year: int) -> Paper:
    return Paper(
        title=title,
        abstract=f"{title} abstract",
        publication_year=year,
        primary_source="test",
        source_record_id=f"paper-{title}",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_bibliometric_relations_builds_networks_and_patent_metrics() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        topics = [
            Topic(slug="ai-management", display_name="AI Management", kind="research_axis"),
            Topic(slug="agentic-ai", display_name="Agentic AI", kind="research_subaxis"),
            Topic(slug="ai-governance", display_name="AI Governance", kind="research_subaxis"),
            Topic(slug="human-ai-trust", display_name="Human AI Trust", kind="research_subaxis"),
            Topic(slug="ai-capability", display_name="AI Capability", kind="research_subaxis"),
            Topic(slug="ai-adoption", display_name="AI Adoption", kind="research_subaxis"),
            Topic(slug="decision-quality", display_name="Decision Quality", kind="research_subaxis"),
        ]
        institutions = [
            Institution(name="Institute A", country_code="KR"),
            Institution(name="Institute B", country_code="US"),
            Institution(name="Institute C", country_code="DE"),
        ]
        authors = [Author(display_name=f"Author {index}") for index in range(3)]
        session.add_all([*topics, *institutions, *authors])
        session.flush()
        for topic in topics[1:]:
            topic.parent_topic_id = topics[0].id

        papers = [_paper(f"Study {index}", 2026 if index < 3 else 2024) for index in range(5)]
        non_scholarly = _paper("Web-like noise", 2026)
        non_scholarly.work_type = "other"
        future_dated = _paper("Future-dated article", 2027)
        future_dated.work_type = "article"
        session.add_all(papers)
        session.add_all([non_scholarly, future_dated])
        session.flush()
        for index, paper in enumerate(papers):
            session.add(PaperTopic(paper_id=paper.id, topic_id=topics[0].id, assignment_source="test"))
            session.add(PaperTopic(paper_id=paper.id, topic_id=topics[1].id, assignment_source="test"))
            session.add(PaperTopic(paper_id=paper.id, topic_id=topics[2].id, assignment_source="test"))
            if index < 3:
                session.add(PaperTopic(paper_id=paper.id, topic_id=topics[3].id, assignment_source="test"))
                session.add(
                    PaperAuthor(
                        paper_id=paper.id,
                        author_id=authors[index % len(authors)].id,
                        author_position=0,
                        raw_affiliation=institutions[index % len(institutions)].name,
                    )
                )
                session.add(
                    PaperAuthor(
                        paper_id=paper.id,
                        author_id=authors[(index + 1) % len(authors)].id,
                        author_position=1,
                        raw_affiliation=institutions[(index + 1) % len(institutions)].name,
                    )
                )

        for author, institution in zip(authors, institutions, strict=True):
            session.add(
                AuthorInstitution(
                    author_id=author.id,
                    institution_id=institution.id,
                    source="test",
                )
            )

        session.add(
            PatentDocument(
                title="Agentic AI orchestration system",
                abstract="An agentic AI workflow for enterprise automation.",
                filing_date=date(2025, 5, 1),
                jurisdiction="US",
                applicants=["Example Corp"],
                inventors=["Inventor A"],
                ipc_codes=["G06F"],
                cpc_codes=["G06F 9/50"],
                primary_source="test",
                source_record_id="patent-1",
                retrieved_at=datetime.now(UTC),
                provenance={},
            )
        )
        session.commit()

    response = get_bibliometric_relations(
        session,
        topic_limit=8,
        institution_limit=6,
        edge_limit=12,
    )

    assert response.total_papers == 5
    assert response.corpus_total_papers == 7
    assert response.excluded_non_scholarly == 1
    assert response.future_dated_records == 1
    assert response.full_text_papers == 0
    assert response.axes
    assert response.subaxes
    assert response.years
    assert response.top_authors
    assert response.top_institutions
    assert response.topic_nodes
    assert any(node.label == "Agentic AI" for node in response.topic_nodes)
    assert any(node.group_label == "AI Management" for node in response.topic_nodes)
    assert response.topic_edges
    assert all(edge.strength >= 0 for edge in response.topic_edges)
    assert response.institution_nodes
    assert response.institution_edges
    assert response.complete_through_year <= response.observed_latest_year
    assert response.recent_window
    assert response.prior_window
    assert response.top_authors[0].recent_count >= 0
    assert response.patent_total == 1
    assert response.patent_years[0].year == 2025
    assert response.patent_jurisdictions[0].label == "US"
    assert response.patent_applicants[0].label == "Example Corp"
    assert response.patent_cpc[0].label == "G06F9"
    assert any(item.paper_topic == "Agentic AI" for item in response.paper_patent_bridge)
    assert response.caveats
