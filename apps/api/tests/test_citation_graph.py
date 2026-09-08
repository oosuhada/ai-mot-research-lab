from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.citation_graph import resolve_local_citation_edges
from research_lab.models import Base, Citation, Paper


def _paper(*, source_id: str, openalex_id: str | None = None) -> Paper:
    return Paper(
        title=source_id,
        publication_year=2025,
        work_type="article",
        is_oa=False,
        retraction_status="none",
        correction_status="none",
        primary_source="openalex",
        source_record_id=source_id,
        openalex_id=openalex_id,
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_resolve_local_citation_edges_updates_all_matches_in_one_pass() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        citing = _paper(source_id="W1", openalex_id="W1")
        cited = _paper(source_id="W2", openalex_id="W2")
        session.add_all([citing, cited])
        session.flush()
        cited_id = cited.id
        session.add_all(
            [
                Citation(
                    citing_paper_id=citing.id,
                    cited_external_id="W2",
                    source="openalex",
                ),
                Citation(
                    citing_paper_id=citing.id,
                    cited_external_id="W999",
                    source="openalex",
                ),
            ]
        )
        session.commit()

        result = resolve_local_citation_edges(session)
        edges = list(session.scalars(select(Citation).order_by(Citation.cited_external_id)))

    assert result.matched_edges == 1
    assert result.remaining_external_edges == 1
    assert edges[0].cited_external_id == "W2"
    assert edges[0].cited_paper_id == cited_id
    assert edges[1].cited_external_id == "W999"
    assert edges[1].cited_paper_id is None
