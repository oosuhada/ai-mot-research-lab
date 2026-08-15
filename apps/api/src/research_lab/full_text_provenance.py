from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import Paper, PaperChunk, PaperVersion


def backfill_full_text_provenance(
    session: Session,
    settings: Settings,
    *,
    limit: int = 100,
) -> dict[str, object]:
    versions = session.scalars(
        select(PaperVersion)
        .where(PaperVersion.source == "openalex_oa_pdf")
        .order_by(PaperVersion.retrieved_at)
    )
    visited = 0
    scanned = 0
    updated = 0
    skipped_complete = 0
    missing_blob = 0
    hash_mismatch = 0
    extraction_failed = 0

    for version in versions:
        visited += 1
        metadata = dict(version.source_metadata or {})
        if isinstance(metadata.get("extraction"), dict) and "source_url" in metadata:
            skipped_complete += 1
            continue
        if scanned >= max(limit, 1):
            break
        scanned += 1
        paper = session.get(Paper, version.paper_id)
        if paper is None:
            continue
        blob_id = metadata.get("private_blob_id")
        blob_path = _resolve_blob_path(settings.private_data_root, version, blob_id)
        if blob_path is None or not blob_path.exists():
            missing_blob += 1
            continue
        data = blob_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != version.payload_hash:
            hash_mismatch += 1
            continue

        try:
            reader = PdfReader(io.BytesIO(data))
            page_texts = [page.extract_text() or "" for page in reader.pages]
            extracted_characters = sum(
                len("\n".join(line.strip() for line in text.splitlines() if line.strip()).strip())
                for text in page_texts
            )
        except Exception:
            extraction_failed += 1
            continue

        chunk_count = int(
            session.scalar(
                select(func.count(PaperChunk.id)).where(PaperChunk.paper_version_id == version.id)
            )
            or 0
        )
        backfilled_at = datetime.now(UTC).isoformat()
        extraction = {
            "method": "pypdf",
            "ocr_run": False,
            "status": "extracted" if extracted_characters else "text_extraction_failed_ocr_not_run",
            "page_count": len(page_texts),
            "chunk_count": chunk_count,
            "extracted_characters": extracted_characters,
            "reconstructed_from_stored_blob": True,
        }
        metadata.update(
            {
                "private_blob_id": str(blob_id or f"{version.paper_id}/{version.payload_hash}.pdf"),
                "source_url": metadata.get("source_url"),
                "extraction": extraction,
                "provenance_backfill": {
                    "backfilled_at": backfilled_at,
                    "backfilled_from_current_paper_record": False,
                    "source_url_reconstructed": False,
                },
            }
        )
        version.source_metadata = metadata
        _upsert_paper_provenance(paper, version, extraction, backfilled_at)
        updated += 1
        session.commit()

    return {
        "versions_considered": visited,
        "legacy_scanned": scanned,
        "updated": updated,
        "skipped_complete": skipped_complete,
        "missing_blob": missing_blob,
        "hash_mismatch": hash_mismatch,
        "extraction_failed": extraction_failed,
    }


def _resolve_blob_path(root: Path, version: PaperVersion, blob_id: Any) -> Path | None:
    if isinstance(blob_id, str) and blob_id:
        return root / blob_id
    if version.payload_hash:
        return root / str(version.paper_id) / f"{version.payload_hash}.pdf"
    return None


def _upsert_paper_provenance(
    paper: Paper,
    version: PaperVersion,
    extraction: dict[str, object],
    backfilled_at: str,
) -> None:
    provenance = dict(paper.provenance or {})
    pdfs = list(provenance.get("open_access_pdfs") or [])
    entry = {
        "sha256": version.payload_hash,
        "private_blob_id": (version.source_metadata or {}).get("private_blob_id"),
        "source_url": (version.source_metadata or {}).get("source_url"),
        "license": version.license,
        "retrieved_at": version.retrieved_at.isoformat(),
        "redistributable": bool((version.source_metadata or {}).get("redistributable", False)),
        "extraction": extraction,
        "provenance_backfill": {
            "backfilled_at": backfilled_at,
            "backfilled_from_current_paper_record": False,
            "source_url_reconstructed": False,
        },
    }
    replaced = False
    merged: list[object] = []
    for item in pdfs:
        if isinstance(item, dict) and item.get("sha256") == version.payload_hash:
            merged.append({**item, **entry})
            replaced = True
        else:
            merged.append(item)
    if not replaced:
        merged.append(entry)
    provenance["open_access_pdfs"] = merged
    paper.provenance = provenance
