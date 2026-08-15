from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import FullTextQueueItem, Paper, PaperContentProfile
from research_lab.pdf_pipeline import PdfEvidenceService


class FullTextEnrichmentWorker:
    """Consume a small, rights-safe slice of the prioritized open-access PDF queue."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ai-mot-research-lab/0.1 (open-access evidence enrichment)"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(self, *, max_items: int = 3, max_pdf_bytes: int = 30_000_000) -> dict[str, Any]:
        now = datetime.now(UTC)
        selected = 0
        completed = 0
        failed = 0
        skipped = 0
        try:
            for _ in range(max(max_items, 1)):
                item = self.session.scalar(
                    select(FullTextQueueItem)
                    .where(
                        FullTextQueueItem.status == "pending",
                        FullTextQueueItem.rights_status == "open_access",
                        (
                            FullTextQueueItem.next_attempt_at.is_(None)
                            | (FullTextQueueItem.next_attempt_at <= now)
                        ),
                    )
                    .order_by(FullTextQueueItem.priority.desc(), FullTextQueueItem.created_at)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                if item is None:
                    break
                selected += 1
                paper = self.session.get(Paper, item.paper_id)
                if paper is None or not paper.is_oa or not paper.pdf_url:
                    item.status = "restricted"
                    item.last_error = "No rights-safe open-access PDF URL remains available"
                    item.next_attempt_at = None
                    profile = self.session.get(PaperContentProfile, item.paper_id)
                    if profile is not None:
                        profile.full_text_status = "restricted"
                        profile.full_text_access = "unknown" if paper is None else "restricted"
                        profile.full_text_updated_at = datetime.now(UTC)
                    skipped += 1
                    self.session.commit()
                    continue
                item.status = "processing"
                item.attempts += 1
                self.session.commit()
                try:
                    response = self.client.get(paper.pdf_url)
                    response.raise_for_status()
                    content_length = int(response.headers.get("content-length") or 0)
                    if content_length > max_pdf_bytes or len(response.content) > max_pdf_bytes:
                        raise ValueError(f"PDF exceeds {max_pdf_bytes} byte enrichment limit")
                    if not response.content.startswith(b"%PDF"):
                        raise ValueError("Open-access URL did not return a PDF")
                    result = PdfEvidenceService(self.session, self.settings).ingest(
                        paper.id,
                        f"{paper.openalex_id or paper.id}.pdf",
                        response.content,
                        source="openalex_oa_pdf",
                        source_url=paper.pdf_url,
                        license_label=paper.license or "Open-access source; redistribution not granted",
                        redistributable=False,
                    )
                    if result.chunk_count <= 0 or result.extraction_status != "extracted":
                        raise ValueError(
                            "PDF contained no extractable text; OCR was not run and full text was not marked available"
                        )
                    item.status = "completed"
                    item.last_error = None
                    item.next_attempt_at = None
                    profile = self.session.get(PaperContentProfile, paper.id)
                    if profile is not None:
                        profile.full_text_status = "available"
                        profile.full_text_access = "open_access"
                        profile.full_text_updated_at = datetime.now(UTC)
                        profile.rights_status = "open_access"
                    completed += 1
                    self.session.commit()
                except Exception as exc:
                    self.session.rollback()
                    persisted = self.session.get(FullTextQueueItem, item.id)
                    if persisted is not None:
                        permanent_http_failure = (
                            isinstance(exc, httpx.HTTPStatusError)
                            and exc.response.status_code in {401, 403, 404, 410}
                        )
                        terminal_failure = permanent_http_failure or persisted.attempts >= 3
                        persisted.status = "failed" if terminal_failure else "pending"
                        persisted.next_attempt_at = (
                            None
                            if terminal_failure
                            else datetime.now(UTC) + timedelta(hours=2 ** persisted.attempts)
                        )
                        persisted.last_error = f"{type(exc).__name__}: {exc}"[:1000]
                        profile = self.session.get(PaperContentProfile, persisted.paper_id)
                        if profile is not None:
                            profile.full_text_status = "failed" if terminal_failure else "queued"
                            if terminal_failure:
                                profile.full_text_updated_at = datetime.now(UTC)
                        self.session.commit()
                    failed += 1
        finally:
            self.close()
        return {
            "selected": selected,
            "completed": completed,
            "failed": failed,
            "restricted_or_missing": skipped,
        }
