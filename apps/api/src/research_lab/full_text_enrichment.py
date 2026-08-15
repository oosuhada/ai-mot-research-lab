from __future__ import annotations

import hashlib
import os
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_sources import (
    OpenAccessPdfCandidate,
    OpenAccessSourceResolver,
    rank_open_access_candidates,
    should_refresh_before_direct_attempt,
)
from research_lab.models import (
    FullTextQueueItem,
    FullTextSourceAttempt,
    Paper,
    PaperContentProfile,
)
from research_lab.pdf_pipeline import PdfEvidenceService

SOURCE_TERMINAL_FAILURES = {
    "http_401",
    "http_403",
    "http_404",
    "http_410",
    "non_pdf_response",
    "pdf_too_large",
    "extraction_failure",
}


class FullTextEnrichmentWorker:
    """Consume a bounded, leased, rights-safe slice of the open-access PDF queue."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ai-mot-research-lab/0.1 (open-access evidence enrichment)"},
        )
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self.source_resolver = OpenAccessSourceResolver(settings, self.client)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(
        self,
        *,
        max_items: int = 3,
        max_pdf_bytes: int = 30_000_000,
        lease_minutes: int = 20,
    ) -> dict[str, Any]:
        selected = 0
        completed = 0
        failed = 0
        deferred = 0
        skipped = 0
        recovered = self._recover_stale_leases()
        legacy_requeued = self._requeue_legacy_failed_items()
        try:
            for _ in range(max(max_items, 1)):
                item = self._claim_next_item(lease_minutes=max(lease_minutes, 1))
                if item is None:
                    break
                selected += 1
                paper = self.session.get(Paper, item.paper_id)
                if paper is None or not paper.is_oa:
                    self._mark_restricted(item, paper)
                    skipped += 1
                    continue
                outcome = self._process_item(item, paper, max_pdf_bytes=max_pdf_bytes)
                if outcome == "completed":
                    completed += 1
                elif outcome == "failed":
                    failed += 1
                else:
                    failed += 1
                    deferred += 1
        finally:
            self.close()
        return {
            "worker_id": self.worker_id,
            "stale_leases_recovered": recovered,
            "legacy_failures_requeued": legacy_requeued,
            "selected": selected,
            "completed": completed,
            "failed": failed,
            "deferred": deferred,
            "restricted_or_missing": skipped,
        }

    def _recover_stale_leases(self) -> int:
        now = datetime.now(UTC)
        rows = list(
            self.session.scalars(
                select(FullTextQueueItem)
                .where(
                    FullTextQueueItem.status == "processing",
                    or_(
                        FullTextQueueItem.lease_expires_at.is_(None),
                        FullTextQueueItem.lease_expires_at <= now,
                    ),
                )
                .with_for_update(skip_locked=True)
            )
        )
        for item in rows:
            item.status = "pending"
            item.worker_id = None
            item.claimed_at = None
            item.lease_expires_at = None
            item.failure_kind = "stale_lease_recovered"
            item.last_error = "Recovered an expired or legacy processing lease"
            item.next_attempt_at = now
        if rows:
            self.session.commit()
        return len(rows)

    def _requeue_legacy_failed_items(self) -> int:
        """Give pre-attempt-ledger OA failures one resolver-aware retry path.

        Rows failed by the older worker have no per-source attempt history, so they
        cannot benefit from alternate OpenAlex OA locations unless they are moved
        back into the claimable queue. Once a row has any attempt ledger entry this
        recovery never touches it again.
        """
        now = datetime.now(UTC)
        has_attempt = exists(
            select(FullTextSourceAttempt.id).where(
                FullTextSourceAttempt.queue_item_id == FullTextQueueItem.id
            )
        )
        rows = list(
            self.session.scalars(
                select(FullTextQueueItem)
                .where(
                    FullTextQueueItem.status == "failed",
                    FullTextQueueItem.rights_status == "open_access",
                    ~has_attempt,
                )
                .with_for_update(skip_locked=True)
            )
        )
        for item in rows:
            item.status = "pending"
            item.next_attempt_at = now
            item.failure_kind = "legacy_failure_requeued"
            self._clear_lease(item)
            profile = self.session.get(PaperContentProfile, item.paper_id)
            if profile is not None:
                profile.full_text_status = "queued"
        if rows:
            self.session.commit()
        return len(rows)

    def _claim_next_item(self, *, lease_minutes: int) -> FullTextQueueItem | None:
        now = datetime.now(UTC)
        item = self.session.scalar(
            select(FullTextQueueItem)
            .where(
                FullTextQueueItem.status == "pending",
                FullTextQueueItem.rights_status == "open_access",
                or_(
                    FullTextQueueItem.next_attempt_at.is_(None),
                    FullTextQueueItem.next_attempt_at <= now,
                ),
            )
            .order_by(FullTextQueueItem.priority.desc(), FullTextQueueItem.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            return None
        item.status = "processing"
        item.attempts += 1
        item.worker_id = self.worker_id
        item.claimed_at = now
        item.lease_expires_at = now + timedelta(minutes=lease_minutes)
        item.failure_kind = None
        self.session.commit()
        return item

    def _process_item(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        *,
        max_pdf_bytes: int,
    ) -> str:
        known_terminal_urls = set(
            self.session.scalars(
                select(FullTextSourceAttempt.source_url).where(
                    FullTextSourceAttempt.queue_item_id == item.id,
                    FullTextSourceAttempt.failure_kind.in_(SOURCE_TERMINAL_FAILURES),
                )
            )
        )
        attempted_this_run: set[str] = set()
        candidates: list[OpenAccessPdfCandidate] = []
        current_url = paper.pdf_url
        current_candidate: OpenAccessPdfCandidate | None = None
        if current_url is not None and current_url not in known_terminal_urls:
            current_candidate = OpenAccessPdfCandidate(
                url=current_url,
                license=paper.license,
                source_kind="paper_pdf_url",
            )
            candidates.append(current_candidate)

        resolution_error: Exception | None = None
        resolver_used = False
        resolution_unchanged_count = 0
        last_error: Exception | None = None
        last_failure_kind: str | None = None

        if (
            current_candidate is not None
            and should_refresh_before_direct_attempt(self.session, current_candidate)
        ):
            resolver_used = True
            try:
                resolved = self.source_resolver.resolve(paper)
                resolution_unchanged_count = self._record_resolution_snapshot(item, resolved)
                candidates = self._dedupe_candidates([*resolved, current_candidate])
                candidates = rank_open_access_candidates(self.session, candidates)
            except Exception as exc:
                resolution_error = exc
                candidates = [current_candidate]

        while True:
            while candidates:
                candidate = candidates.pop(0)
                if candidate.url in attempted_this_run or candidate.url in known_terminal_urls:
                    continue
                attempted_this_run.add(candidate.url)
                success, failure_kind, error = self._attempt_candidate(
                    item,
                    paper,
                    candidate,
                    max_pdf_bytes=max_pdf_bytes,
                )
                if success:
                    paper.pdf_url = candidate.url
                    if candidate.license:
                        paper.license = candidate.license
                    self._mark_completed(item, paper)
                    return "completed"
                last_failure_kind = failure_kind
                last_error = error
                if failure_kind in SOURCE_TERMINAL_FAILURES:
                    known_terminal_urls.add(candidate.url)

            if resolver_used:
                break
            resolver_used = True
            try:
                resolved = self.source_resolver.resolve(paper)
                resolution_unchanged_count = self._record_resolution_snapshot(item, resolved)
                candidates = [
                    candidate
                    for candidate in rank_open_access_candidates(self.session, resolved)
                    if candidate.url not in known_terminal_urls | attempted_this_run
                ][:4]
            except Exception as exc:
                resolution_error = exc
                candidates = []
            if not candidates:
                break

        if resolution_error is not None:
            failure_kind = "source_resolution_failure"
            error = resolution_error
        elif last_failure_kind in SOURCE_TERMINAL_FAILURES:
            failure_kind = "source_exhausted"
            error = last_error or RuntimeError("No untried rights-safe OpenAlex PDF location remains")
        else:
            failure_kind = last_failure_kind or "source_exhausted"
            error = last_error or RuntimeError("No rights-safe OpenAlex PDF location remains")

        has_openalex_identity = bool(paper.openalex_id) or (
            paper.primary_source == "openalex" and paper.source_record_id.startswith("W")
        )
        retryable = has_openalex_identity and (
            failure_kind == "source_exhausted" or item.attempts < 6
        )
        self._mark_unsuccessful(
            item,
            paper,
            failure_kind=failure_kind,
            error=error,
            retryable=retryable,
            resolution_unchanged_count=resolution_unchanged_count,
        )
        return "deferred" if retryable else "failed"

    @staticmethod
    def _dedupe_candidates(candidates: list[OpenAccessPdfCandidate]) -> list[OpenAccessPdfCandidate]:
        seen: set[str] = set()
        result: list[OpenAccessPdfCandidate] = []
        for candidate in candidates:
            if candidate.url in seen:
                continue
            seen.add(candidate.url)
            result.append(candidate)
        return result

    def _record_resolution_snapshot(
        self,
        item: FullTextQueueItem,
        candidates: list[OpenAccessPdfCandidate],
    ) -> int:
        fingerprint_input = "\n".join(sorted(candidate.url for candidate in candidates))
        fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()
        factors = dict(item.reason_factors or {})
        previous_raw = factors.get("source_resolution")
        previous = previous_raw if isinstance(previous_raw, dict) else {}
        unchanged_count = (
            int(previous.get("unchanged_count") or 0) + 1
            if previous.get("fingerprint") == fingerprint
            else 0
        )
        factors["source_resolution"] = {
            "fingerprint": fingerprint,
            "resolved_at": datetime.now(UTC).isoformat(),
            "candidate_count": len(candidates),
            "unchanged_count": unchanged_count,
        }
        item.reason_factors = factors
        return unchanged_count

    def _attempt_candidate(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        candidate: OpenAccessPdfCandidate,
        *,
        max_pdf_bytes: int,
    ) -> tuple[bool, str | None, Exception | None]:
        started_at = datetime.now(UTC)
        http_status: int | None = None
        try:
            response = self.client.get(candidate.url)
            http_status = response.status_code
            response.raise_for_status()
            content_length = int(response.headers.get("content-length") or 0)
            if content_length > max_pdf_bytes or len(response.content) > max_pdf_bytes:
                raise ValueError(f"PDF exceeds {max_pdf_bytes} byte enrichment limit")
            if not response.content.startswith(b"%PDF"):
                raise TypeError("Open-access URL did not return a PDF")
            result = PdfEvidenceService(self.session, self.settings).ingest(
                paper.id,
                f"{paper.openalex_id or paper.id}.pdf",
                response.content,
                source="openalex_oa_pdf",
                source_url=candidate.url,
                license_label=candidate.license or paper.license or "Open-access source; redistribution not granted",
                redistributable=False,
            )
            if result.chunk_count <= 0 or result.extraction_status != "extracted":
                raise HTTPException(
                    status_code=422,
                    detail="PDF contained no extractable text; OCR was not run",
                )
            self._record_source_attempt(
                item,
                paper,
                candidate,
                started_at=started_at,
                status="completed",
                failure_kind=None,
                http_status=http_status,
                error=None,
            )
            return True, None, None
        except Exception as exc:
            failure_kind = _classify_failure(exc, http_status=http_status)
            self._record_source_attempt(
                item,
                paper,
                candidate,
                started_at=started_at,
                status="failed",
                failure_kind=failure_kind,
                http_status=http_status,
                error=exc,
            )
            return False, failure_kind, exc

    def _record_source_attempt(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        candidate: OpenAccessPdfCandidate,
        *,
        started_at: datetime,
        status: str,
        failure_kind: str | None,
        http_status: int | None,
        error: Exception | None,
    ) -> None:
        self.session.add(
            FullTextSourceAttempt(
                queue_item_id=item.id,
                paper_id=paper.id,
                source_url=candidate.url,
                domain=candidate.domain,
                publisher=paper.publisher,
                source_kind=candidate.source_kind,
                status=status,
                failure_kind=failure_kind,
                http_status=http_status,
                error_message=(f"{type(error).__name__}: {error}"[:1000] if error else None),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        )
        self.session.commit()

    def _mark_completed(self, item: FullTextQueueItem, paper: Paper) -> None:
        item.status = "completed"
        item.last_error = None
        item.failure_kind = None
        item.next_attempt_at = None
        self._clear_lease(item)
        profile = self.session.get(PaperContentProfile, paper.id)
        if profile is not None:
            profile.full_text_status = "available"
            profile.full_text_access = "open_access"
            profile.full_text_updated_at = datetime.now(UTC)
            profile.rights_status = "open_access"
        self.session.commit()

    def _mark_unsuccessful(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        *,
        failure_kind: str,
        error: Exception,
        retryable: bool,
        resolution_unchanged_count: int = 0,
    ) -> None:
        item.status = "pending" if retryable else "failed"
        item.failure_kind = failure_kind
        item.last_error = f"{type(error).__name__}: {error}"[:1000]
        if retryable:
            if failure_kind == "source_exhausted":
                if resolution_unchanged_count >= 2:
                    delay = timedelta(days=7)
                elif resolution_unchanged_count == 1:
                    delay = timedelta(days=3)
                else:
                    delay = timedelta(hours=24)
            else:
                delay = timedelta(hours=min(2 ** item.attempts, 24))
            item.next_attempt_at = datetime.now(UTC) + delay
        else:
            item.next_attempt_at = None
        self._clear_lease(item)
        profile = self.session.get(PaperContentProfile, paper.id)
        if profile is not None:
            profile.full_text_status = "queued" if retryable else "failed"
            if not retryable:
                profile.full_text_updated_at = datetime.now(UTC)
        self.session.commit()

    def _mark_restricted(self, item: FullTextQueueItem, paper: Paper | None) -> None:
        item.status = "restricted"
        item.failure_kind = "rights_unavailable"
        item.last_error = "No rights-safe open-access PDF URL remains available"
        item.next_attempt_at = None
        self._clear_lease(item)
        profile = self.session.get(PaperContentProfile, item.paper_id)
        if profile is not None:
            profile.full_text_status = "restricted"
            profile.full_text_access = "unknown" if paper is None else "restricted"
            profile.full_text_updated_at = datetime.now(UTC)
        self.session.commit()

    @staticmethod
    def _clear_lease(item: FullTextQueueItem) -> None:
        item.worker_id = None
        item.claimed_at = None
        item.lease_expires_at = None


def _classify_failure(exc: Exception, *, http_status: int | None) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return f"http_{status}"
    if http_status in {401, 403, 404, 410}:
        return f"http_{http_status}"
    if isinstance(exc, TypeError) and "did not return a PDF" in str(exc):
        return "non_pdf_response"
    if isinstance(exc, ValueError) and "exceeds" in str(exc):
        return "pdf_too_large"
    if isinstance(exc, HTTPException) and exc.status_code == 422:
        return "extraction_failure"
    if isinstance(exc, httpx.RequestError):
        return "network_error"
    return "extraction_failure"
