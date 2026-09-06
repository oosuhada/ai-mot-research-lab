import csv
import io
import zipfile
from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from research_lab.models import Base, Citation, Paper
from research_lab.opencitations_index import OpenCitationsIndexImporter, parse_index_identifier


def _paper(*, doi: str, openalex: str, omid: str) -> Paper:
    return Paper(
        doi=doi,
        openalex_id=openalex,
        opencitations_omid=omid,
        title=doi,
        publication_year=2025,
        work_type="article",
        is_oa=False,
        retraction_status="none",
        correction_status="none",
        primary_source="test",
        source_record_id=omid,
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_parse_index_identifier_supports_mixed_and_legacy_values() -> None:
    mixed = parse_index_identifier("omid:br/1 doi:10.1/ABC openalex:W123")
    assert mixed == {"omid": "br/1", "doi": "10.1/abc", "openalex": "W123"}
    assert parse_index_identifier("10.2/Legacy") == {"doi": "10.2/legacy"}


def test_index_zip_import_keeps_only_local_to_local_edges(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    zip_path = tmp_path / "0_0.zip"
    content = io.StringIO()
    writer = csv.DictWriter(
        content,
        fieldnames=["oci", "citing", "cited", "creation", "timespan", "journal_sc", "author_sc"],
    )
    writer.writeheader()
    writer.writerow(
        {
            "oci": "1-2",
            "citing": "omid:br/1 doi:10.1/a openalex:W1",
            "cited": "omid:br/2 doi:10.1/b openalex:W2",
            "creation": "2025",
            "timespan": "P1Y",
            "journal_sc": "no",
            "author_sc": "no",
        }
    )
    writer.writerow(
        {
            "oci": "3-2",
            "citing": "omid:br/3 doi:10.1/c",
            "cited": "omid:br/2 doi:10.1/b",
            "creation": "2025",
            "timespan": "P1Y",
            "journal_sc": "no",
            "author_sc": "no",
        }
    )
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("part.csv", content.getvalue())

    with Session(engine) as session:
        first = _paper(doi="10.1/a", openalex="W1", omid="br/1")
        second = _paper(doi="10.1/b", openalex="W2", omid="br/2")
        session.add_all([first, second])
        session.commit()
        first_id = first.id
        second_id = second.id
        result = OpenCitationsIndexImporter(session, batch_size=100).run(zip_path)
        count = session.scalar(select(func.count()).select_from(Citation))
        edge = session.scalar(select(Citation))

    assert result.records_scanned == 2
    assert result.local_edges == 1
    assert result.inserted_edges == 1
    assert result.skipped_nonlocal == 1
    assert count == 1
    assert edge is not None
    assert edge.citing_paper_id == first_id
    assert edge.cited_paper_id == second_id
    assert edge.cited_external_id == "omid:br/2"
