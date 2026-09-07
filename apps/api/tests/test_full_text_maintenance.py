from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.full_text_maintenance import FullTextQueueMaintenance
from research_lab.models import FullTextQueueItem, Paper, PaperChunk, PaperContentProfile
from research_lab.private_blob_storage import (
    prepare_private_blob_shards,
    require_private_blob_shard,
    sharded_private_blob,
    verify_private_blob_shards,
)


def _create_tables(engine: object) -> None:
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        PaperChunk.__table__,
    ):
        table.create(engine)  # type: ignore[arg-type]


def test_full_text_maintenance_backfills_bulk_imports_and_recovers_expired_lease(tmp_path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_tables(engine)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        oa_pdf = Paper(
            title="Bulk OA with PDF",
            doi="10.1000/oa-pdf",
            is_oa=True,
            pdf_url="https://example.test/paper.pdf",
            primary_source="opencitations",
            source_record_id="omid:1",
            retrieved_at=now,
            provenance={},
        )
        unknown = Paper(
            title="Bulk DOI resolver candidate",
            doi="10.1000/unknown",
            is_oa=False,
            primary_source="opencitations",
            source_record_id="omid:2",
            retrieved_at=now,
            provenance={},
        )
        no_identity = Paper(
            title="Metadata only",
            is_oa=False,
            primary_source="opencitations",
            source_record_id="omid:3",
            retrieved_at=now,
            provenance={},
        )
        stale = Paper(
            title="Expired lease",
            doi="10.1000/stale",
            is_oa=True,
            primary_source="openalex",
            source_record_id="W-STALE-MAINT",
            retrieved_at=now,
            provenance={},
        )
        session.add_all([oa_pdf, unknown, no_identity, stale])
        session.flush()
        oa_pdf_id = oa_pdf.id
        session.add(PaperContentProfile(paper_id=stale.id, full_text_status="queued"))
        session.add(
            FullTextQueueItem(
                paper_id=stale.id,
                status="processing",
                priority=90,
                rights_status="open_access",
                worker_id="dead-worker",
                claimed_at=now - timedelta(hours=1),
                lease_expires_at=now - timedelta(minutes=30),
            )
        )
        session.commit()

        result = FullTextQueueMaintenance(session).run(limit=100, stale_grace_minutes=0, commit_every=2)

        assert result["expired_leases_recovered"] == 1
        assert result["profiles_created"] == 3
        assert result["queue_items_created"] == 3
        assert session.query(PaperContentProfile).count() == 4
        assert session.query(FullTextQueueItem).count() == 4

        oa_queue = session.query(FullTextQueueItem).filter_by(paper_id=oa_pdf.id).one()
        unknown_queue = session.query(FullTextQueueItem).filter_by(paper_id=unknown.id).one()
        restricted_queue = session.query(FullTextQueueItem).filter_by(paper_id=no_identity.id).one()
        stale_queue = session.query(FullTextQueueItem).filter_by(paper_id=stale.id).one()
        assert oa_queue.status == "pending" and oa_queue.priority == 100 and oa_queue.rights_status == "open_access"
        assert unknown_queue.status == "pending" and unknown_queue.priority == 50 and unknown_queue.rights_status == "unknown"
        assert restricted_queue.status == "restricted"
        assert stale_queue.status == "pending"
        assert stale_queue.worker_id is None

        second = FullTextQueueMaintenance(session).run(limit=100, stale_grace_minutes=0, commit_every=2)
        assert second["profiles_created"] == 0
        assert second["queue_items_created"] == 0
        assert second["papers_examined"] == 0

    prepared = prepare_private_blob_shards(tmp_path)
    assert len(prepared) == 256
    assert verify_private_blob_shards(tmp_path) is True
    blob_id, path = sharded_private_blob(tmp_path, oa_pdf_id, "a" * 64, "pdf")
    compact = str(oa_pdf_id).replace("-", "")
    assert blob_id == f"blobs/{compact[:2]}/{oa_pdf_id}_{'a' * 64}.pdf"
    assert path == tmp_path / blob_id
    require_private_blob_shard(path.parent)
