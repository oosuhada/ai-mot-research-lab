from __future__ import annotations

import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embeddings import build_embedding_provider
from research_lab.models import IngestionRun, Paper, PaperChunk, PaperVersion
from research_lab.taxonomy import TAXONOMY_VERSION


@dataclass(slots=True)
class PdfIngestResult:
    run_id: uuid.UUID
    paper_id: uuid.UUID
    version_id: uuid.UUID
    chunk_count: int
    page_count: int
    extraction_status: str
    private_blob_id: str


class PdfEvidenceService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.embedding_provider = build_embedding_provider(settings)

    def ingest(self, paper_id: uuid.UUID, filename: str, data: bytes) -> PdfIngestResult:
        paper = self.session.get(Paper, paper_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        if not filename.lower().endswith(".pdf") or not data.startswith(b"%PDF"):
            raise HTTPException(status_code=422, detail="Only valid PDF uploads are supported")

        digest = hashlib.sha256(data).hexdigest()
        run = IngestionRun(
            source="user_pdf",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={"paper_id": str(paper_id), "filename": Path(filename).name, "sha256": digest},
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        blob_id = f"{paper_id}/{digest}.pdf"
        target = self.settings.private_data_root / str(paper_id) / f"{digest}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        version = self.session.scalar(
            select(PaperVersion).where(
                PaperVersion.paper_id == paper_id,
                PaperVersion.source == "user_pdf",
                PaperVersion.payload_hash == digest,
            )
        )
        if version is None:
            version = PaperVersion(
                paper_id=paper_id,
                source="user_pdf",
                source_record_id=digest,
                version_label="private-full-text",
                retrieved_at=datetime.now(UTC),
                license="user-supplied private file; redistribution not granted",
                payload_hash=digest,
                source_metadata={
                    "private_blob_id": blob_id,
                    "original_filename": Path(filename).name,
                    "redistributable": False,
                },
            )
            self.session.add(version)
            self.session.flush()

        try:
            reader = PdfReader(io.BytesIO(data))
            page_texts = [(index + 1, page.extract_text() or "") for index, page in enumerate(reader.pages)]
        except Exception as exc:
            run.status = "failed"
            run.error_count = 1
            run.error_message = f"PDF extraction failed; OCR was not run: {type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
            raise HTTPException(status_code=422, detail="PDF text extraction failed; OCR was not run") from exc

        chunks = 0
        extracted_chars = 0
        for page_number, page_text in page_texts:
            cleaned = "\n".join(line.strip() for line in page_text.splitlines() if line.strip()).strip()
            if not cleaned:
                continue
            extracted_chars += len(cleaned)
            for offset, text in _chunk_text(cleaned):
                text_hash = hashlib.sha256(text.encode()).hexdigest()
                existing = self.session.scalar(
                    select(PaperChunk).where(PaperChunk.paper_id == paper_id, PaperChunk.text_hash == text_hash)
                )
                if existing is not None:
                    continue
                section = _infer_section(text, page_number)
                locator = f"p. {page_number} · {section}"
                self.session.add(
                    PaperChunk(
                        paper_id=paper_id,
                        paper_version_id=version.id,
                        section=section,
                        page_start=page_number,
                        page_end=page_number,
                        char_start=offset,
                        char_end=offset + len(text),
                        source_locator=locator,
                        text=text,
                        text_hash=text_hash,
                        language=paper.language,
                        embedding=self.embedding_provider.embed(text),
                    )
                )
                chunks += 1

        status = "extracted" if extracted_chars else "text_extraction_failed_ocr_not_run"
        run.status = "completed" if extracted_chars else "completed_with_errors"
        run.fetched_count = len(page_texts)
        run.accepted_count = chunks
        run.inserted_count = chunks
        run.error_count = 0 if extracted_chars else 1
        run.error_message = None if extracted_chars else "No extractable text found; OCR was not run"
        run.checkpoint = {"page_count": len(page_texts), "chunk_count": chunks, "status": status}
        run.finished_at = datetime.now(UTC)
        provenance = dict(paper.provenance or {})
        pdfs = list(provenance.get("private_pdfs") or [])
        if not any(item.get("sha256") == digest for item in pdfs if isinstance(item, dict)):
            pdfs.append({"sha256": digest, "private_blob_id": blob_id, "ingested_at": datetime.now(UTC).isoformat()})
        provenance["private_pdfs"] = pdfs
        paper.provenance = provenance
        self.session.commit()

        return PdfIngestResult(
            run_id=run.id,
            paper_id=paper_id,
            version_id=version.id,
            chunk_count=chunks,
            page_count=len(page_texts),
            extraction_status=status,
            private_blob_id=blob_id,
        )


def _chunk_text(text: str, size: int = 1800, overlap: int = 200) -> list[tuple[int, str]]:
    if len(text) <= size:
        return [(0, text)]
    chunks: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        chunks.append((start, text[start:end].strip()))
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [(offset, chunk) for offset, chunk in chunks if chunk]


def _infer_section(text: str, page_number: int) -> str:
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if first and len(first) <= 100 and len(first.split()) <= 12:
        return first
    return f"Page {page_number}"
