import gzip
import json
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.models import Base, Paper
from research_lab.semantic_scholar_bulk import SemanticScholarPapersMapper, semantic_scholar_ids


def test_semantic_scholar_ids_extract_hash_and_corpus_id() -> None:
    paper_id, corpus_id = semantic_scholar_ids(
        {
            "corpusid": 94932690,
            "url": "https://www.semanticscholar.org/paper/52c3519026633d3db98c375970d2c2e92733841a",
        }
    )
    assert paper_id == "52c3519026633d3db98c375970d2c2e92733841a"
    assert corpus_id == "94932690"


def test_papers_mapper_backfills_ids_by_doi(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    shard = tmp_path / "papers.jsonl.gz"
    record = {
        "corpusid": 94932690,
        "externalids": {"DOI": "10.1007/BF02035256"},
        "url": "https://www.semanticscholar.org/paper/52c3519026633d3db98c375970d2c2e92733841a",
        "title": "Example",
        "citationcount": 12,
        "referencecount": 8,
        "isopenaccess": False,
    }
    with gzip.open(shard, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")

    with Session(engine) as session:
        session.add(
            Paper(
                doi="10.1007/bf02035256",
                title="Example",
                publication_year=1997,
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
        result = SemanticScholarPapersMapper(session, commit_every=1000).run(shard)
        paper = session.scalar(select(Paper))

    assert result.matched == 1
    assert result.updated == 1
    assert paper is not None
    assert paper.s2_id == "52c3519026633d3db98c375970d2c2e92733841a"
    assert paper.s2_corpus_id == "94932690"
