from __future__ import annotations

import hashlib
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embeddings import build_embedding_provider
from research_lab.models import IngestionRun, Paper, PaperChunk, PaperVersion
from research_lab.pdf_pipeline import _chunk_text
from research_lab.taxonomy import TAXONOMY_VERSION


@dataclass
class XmlIngestResult:
    run_id: uuid.UUID
    paper_id: uuid.UUID
    version_id: uuid.UUID
    chunk_count: int
    extraction_status: str
    private_blob_id: str


class XmlEvidenceService:
    """Store and chunk rights-safe structured full text such as Europe PMC JATS XML."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.embedding_provider = build_embedding_provider(settings)

    def ingest(
        self,
        paper_id: uuid.UUID,
        data: bytes,
        *,
        source: str,
        source_record_id: str,
        source_url: str,
        license_label: str,
        redistributable: bool = False,
        section_label: str = "Europe PMC full text",
    ) -> XmlIngestResult:
        paper = self.session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")

        digest = hashlib.sha256(data).hexdigest()
        run = IngestionRun(
            source=source,
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={
                "paper_id": str(paper_id),
                "source_record_id": source_record_id,
                "sha256": digest,
            },
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        blob_id = f"{paper_id}/{digest}.xml"
        target = self.settings.private_data_root / str(paper_id) / f"{digest}.xml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        retrieved_at = datetime.now(timezone.utc)
        version = self.session.scalar(
            select(PaperVersion).where(
                PaperVersion.paper_id == paper_id,
                PaperVersion.source == source,
                PaperVersion.source_record_id == source_record_id,
                PaperVersion.payload_hash == digest,
            )
        )
        if version is None:
            version = PaperVersion(
                paper_id=paper_id,
                source=source,
                source_record_id=source_record_id,
                version_label="structured-full-text",
                retrieved_at=retrieved_at,
                license=license_label,
                payload_hash=digest,
                source_metadata={},
            )
            self.session.add(version)
            self.session.flush()

        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            self._mark_run_failed(run.id, f"XML parse failed: {exc}")
            raise HTTPException(status_code=422, detail="Structured full-text XML could not be parsed") from exc

        blocks: list[str] = []
        nul_characters_removed = 0
        for element in root.iter():
            if _local_name(element.tag) not in {"title", "p"}:
                continue
            raw = " ".join("".join(element.itertext()).split())
            nul_characters_removed += raw.count("\x00")
            cleaned = raw.replace("\x00", "").strip()
            if cleaned:
                blocks.append(cleaned)
        full_text = "\n\n".join(blocks)
        if not full_text:
            self._mark_run_failed(run.id, "Structured full text contained no extractable text")
            raise HTTPException(status_code=422, detail="Structured full text contained no extractable text")

        chunks = 0
        for offset, text in _chunk_text(full_text):
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            existing = self.session.scalar(
                select(PaperChunk).where(
                    PaperChunk.paper_id == paper_id,
                    PaperChunk.text_hash == text_hash,
                )
            )
            if existing is not None:
                continue
            self.session.add(
                PaperChunk(
                    paper_id=paper_id,
                    paper_version_id=version.id,
                    section=section_label,
                    page_start=None,
                    page_end=None,
                    char_start=offset,
                    char_end=offset + len(text),
                    source_locator=f"{source_record_id} · chars {offset}-{offset + len(text)}",
                    text=text,
                    text_hash=text_hash,
                    language=paper.language,
                    embedding=self.embedding_provider.embed_document(text),
                    embedding_provider=self.embedding_provider.name,
                    embedding_model=self.embedding_provider.model,
                )
            )
            chunks += 1

        extraction = {
            "method": "jats_xml",
            "ocr_run": False,
            "status": "extracted",
            "block_count": len(blocks),
            "chunk_count": chunks,
            "extracted_characters": len(full_text),
            "nul_characters_removed": nul_characters_removed,
        }
        version.source_metadata = {
            **dict(version.source_metadata or {}),
            "private_blob_id": blob_id,
            "media_type": "application/xml",
            "redistributable": redistributable,
            "source_url": source_url,
            "retrieved_at": version.retrieved_at.isoformat(),
            "last_retrieved_at": retrieved_at.isoformat(),
            "extraction": extraction,
        }
        provenance = dict(paper.provenance or {})
        documents = list(provenance.get("open_access_documents") or [])
        entry = {
            "sha256": digest,
            "private_blob_id": blob_id,
            "source": source,
            "source_record_id": source_record_id,
            "source_url": source_url,
            "media_type": "application/xml",
            "license": license_label,
            "retrieved_at": version.retrieved_at.isoformat(),
            "last_retrieved_at": retrieved_at.isoformat(),
            "redistributable": redistributable,
            "extraction": extraction,
        }
        replaced = False
        updated_documents: list[object] = []
        for item in documents:
            if isinstance(item, dict) and item.get("sha256") == digest:
                updated_documents.append(entry)
                replaced = True
            else:
                updated_documents.append(item)
        if not replaced:
            updated_documents.append(entry)
        provenance["open_access_documents"] = updated_documents
        paper.provenance = provenance

        run.status = "completed"
        run.fetched_count = 1
        run.accepted_count = chunks
        run.inserted_count = chunks
        run.checkpoint = {"chunk_count": chunks, "status": "extracted"}
        run.finished_at = datetime.now(timezone.utc)
        try:
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            self._mark_run_failed(run.id, f"Structured full-text persistence failed: {type(exc).__name__}: {exc}")
            raise

        return XmlIngestResult(
            run_id=run.id,
            paper_id=paper_id,
            version_id=version.id,
            chunk_count=chunks,
            extraction_status="extracted",
            private_blob_id=blob_id,
        )

    def _mark_run_failed(self, run_id: uuid.UUID, message: str) -> None:
        self.session.rollback()
        run = self.session.get(IngestionRun, run_id)
        if run is not None:
            run.status = "failed"
            run.error_count = 1
            run.error_message = message[:1000]
            run.finished_at = datetime.now(timezone.utc)
            self.session.commit()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
