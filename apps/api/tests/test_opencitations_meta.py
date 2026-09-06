from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.models import Base, Paper
from research_lab.opencitations_meta import (
    OpenCitationsMetaImporter,
    is_ai_mot_title,
    parse_opencitations_meta_row,
)


def test_parse_opencitations_meta_row_extracts_canonical_ids() -> None:
    row = parse_opencitations_meta_row(
        {
            "id": "doi:10.1234/ABC openalex:W123 omid:br/060123",
            "title": "Artificial Intelligence and Innovation Management",
            "author": "Doe, Jane [orcid:0000 omid:ra/1]",
            "pub_date": "2026-04-03",
            "type": "journal article",
            "venue": "Technovation [issn:1234 omid:br/2]",
            "publisher": "Example Publisher [crossref:12 omid:ra/3]",
        }
    )
    assert row.doi == "10.1234/abc"
    assert row.openalex_id == "W123"
    assert row.omid == "br/060123"
    assert row.publication_year == 2026
    assert row.publisher == "Example Publisher"


def test_ai_mot_title_filter_requires_ai_and_management_context() -> None:
    assert is_ai_mot_title("Artificial intelligence adoption and firm performance")
    assert is_ai_mot_title("Agentic AI for enterprise workflow automation")
    assert not is_ai_mot_title("Artificial intelligence for stellar spectroscopy")
    assert not is_ai_mot_title("Innovation management in family firms")


def test_importer_enriches_existing_and_inserts_relevant_new(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    csv_path = tmp_path / "meta.csv"
    csv_path.write_text(
        "id,title,author,pub_date,issue,volume,venue,type,page,publisher,editor\n"
        "doi:10.1/existing openalex:W1 omid:br/1,Existing AI paper,,2025,,,,journal article,,,\n"
        "doi:10.1/new openalex:W2 omid:br/2,Artificial intelligence adoption and business value,,2026,,,,journal article,,Publisher,\n"
        "doi:10.1/irrelevant openalex:W3 omid:br/3,Artificial intelligence for galaxy classification,,2026,,,,journal article,,,\n",
        encoding="utf-8",
    )
    with Session(engine) as session:
        session.add(
            Paper(
                doi="10.1/existing",
                openalex_id="W1",
                title="Existing AI paper",
                publication_year=2025,
                work_type="article",
                is_oa=False,
                retraction_status="none",
                correction_status="none",
                primary_source="openalex",
                source_record_id="W1",
                retrieved_at=datetime.now(UTC),
                provenance={},
            )
        )
        session.commit()
        result = OpenCitationsMetaImporter(session, commit_every=100).run(csv_path)
        papers = session.scalars(select(Paper).order_by(Paper.doi)).all()

    assert result.scanned == 3
    assert result.matched_existing == 1
    assert result.inserted == 1
    assert len(papers) == 2
    existing = next(paper for paper in papers if paper.doi == "10.1/existing")
    added = next(paper for paper in papers if paper.doi == "10.1/new")
    assert existing.opencitations_omid == "br/1"
    assert added.opencitations_omid == "br/2"
    assert added.primary_source == "opencitations_meta_dump"


def test_importer_accepts_bulk_rows_larger_than_python_csv_default(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    csv_path = tmp_path / "large-field.csv"
    large_author_field = "A" * 200_000
    csv_path.write_text(
        "id,title,author,pub_date,issue,volume,venue,type,page,publisher,editor\n"
        f"doi:10.1/large omid:br/large,Artificial intelligence adoption and business value,{large_author_field},2026,,,,journal article,,,\n",
        encoding="utf-8",
    )

    with Session(engine) as session:
        result = OpenCitationsMetaImporter(session, commit_every=100).run(csv_path)
        paper = session.scalar(select(Paper).where(Paper.doi == "10.1/large"))

    assert result.scanned == 1
    assert result.inserted == 1
    assert paper is not None
    assert paper.opencitations_omid == "br/large"
