from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_enrichment import FullTextEnrichmentWorker
from research_lab.full_text_sources import (
    OpenAccessPdfCandidate,
    PaperSearchMcpSourceResolver,
    rank_open_access_candidates,
)
from research_lab.models import FullTextQueueItem, FullTextSourceAttempt, Paper


class PaperSearchMcpFullTextWorker(FullTextEnrichmentWorker):
    """Low-volume auxiliary OA worker backed by paper-search-mcp repositories."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(session, settings, client=client, worker_id=worker_id)
        self.mcp_resolver = PaperSearchMcpSourceResolver(settings)

    def run(
        self,
        *,
        max_items: int = 5,
        max_pdf_bytes: int = 30_000_000,
        lease_minutes: int = 15,
        min_prior_attempts: int = 1,
    ) -> dict[str, Any]:
        if not self.mcp_resolver.enabled:
            self.close()
            return {
                "worker_id": self.worker_id,
                "enabled": False,
                "selected": 0,
                "completed": 0,
                "failed": 0,
                "no_match": 0,
            }

        selected = completed = failed = no_match = 0
        recovered = self._recover_stale_leases()
        try:
            for _ in range(max(max_items, 1)):
                item = self._claim_mcp_item(
                    lease_minutes=max(lease_minutes, 1),
                    min_prior_attempts=max(min_prior_attempts, 0),
                )
                if item is None:
                    break
                selected += 1
                paper = self.session.get(Paper, item.paper_id)
                if paper is None:
                    self._release_mcp_item(item, "paper_search_mcp_missing_paper", "Paper row is missing")
                    failed += 1
                    continue

                try:
                    candidates = rank_open_access_candidates(
                        self.session,
                        self.mcp_resolver.resolve(paper),
                    )
                except Exception as exc:
                    self._record_mcp_search(item, paper, status="failed", error=exc)
                    self._release_mcp_item(
                        item,
                        "paper_search_mcp_provider_error",
                        self._sanitize_error_message(exc),
                    )
                    failed += 1
                    continue

                if not candidates:
                    self._record_mcp_search(item, paper, status="failed", failure_kind="no_match")
                    self._release_mcp_item(item, "paper_search_mcp_no_match", "No exact OA repository match")
                    no_match += 1
                    continue

                succeeded = False
                last_error: Exception | None = None
                last_failure = "paper_search_mcp_exhausted"
                for candidate in candidates[:4]:
                    ok, failure_kind, error = self._attempt_candidate(
                        item,
                        paper,
                        candidate,
                        max_pdf_bytes=max_pdf_bytes,
                    )
                    if ok:
                        if candidate.media_type == "pdf":
                            paper.pdf_url = candidate.url
                        self._clear_mcp_claim_snapshot(item)
                        self._mark_completed(item, paper)
                        completed += 1
                        succeeded = True
                        break
                    last_failure = failure_kind or last_failure
                    last_error = error
                if not succeeded:
                    self._release_mcp_item(
                        item,
                        last_failure,
                        self._sanitize_error_message(last_error or RuntimeError("Repository candidates exhausted")),
                    )
                    failed += 1
        finally:
            self.close()
        return {
            "worker_id": self.worker_id,
            "enabled": True,
            "stale_leases_recovered": recovered,
            "selected": selected,
            "completed": completed,
            "failed": failed,
            "no_match": no_match,
        }

    def _claim_mcp_item(self, *, lease_minutes: int, min_prior_attempts: int) -> FullTextQueueItem | None:
        now = datetime.now(UTC)
        mcp_already_checked = exists(
            select(FullTextSourceAttempt.id).where(
                FullTextSourceAttempt.paper_id == FullTextQueueItem.paper_id,
                FullTextSourceAttempt.source_kind.like("paper_search_mcp_%"),
            )
        )
        item = self.session.scalar(
            select(FullTextQueueItem)
            .join(Paper, Paper.id == FullTextQueueItem.paper_id)
            .where(
                FullTextQueueItem.status == "pending",
                FullTextQueueItem.rights_status.in_(("open_access", "unknown")),
                FullTextQueueItem.attempts >= min_prior_attempts,
                ~mcp_already_checked,
                or_(Paper.doi.is_not(None), Paper.title.is_not(None)),
            )
            .order_by(FullTextQueueItem.priority.desc(), FullTextQueueItem.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            return None
        factors = dict(item.reason_factors or {})
        factors["paper_search_mcp_claim"] = {
            "next_attempt_at": item.next_attempt_at.isoformat() if item.next_attempt_at else None,
            "failure_kind": item.failure_kind,
            "last_error": item.last_error,
        }
        item.reason_factors = factors
        item.status = "processing"
        item.worker_id = self.worker_id
        item.claimed_at = now
        item.lease_expires_at = now + timedelta(minutes=lease_minutes)
        item.failure_kind = None
        self.session.commit()
        return item

    def _record_mcp_search(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        *,
        status: str,
        failure_kind: str | None = "provider_error",
        error: Exception | None = None,
    ) -> None:
        candidate = OpenAccessPdfCandidate(
            url="paper-search-mcp://search",
            license=paper.license,
            source_kind="paper_search_mcp_search",
            source_record_id=paper.doi or str(paper.id),
        )
        self._record_source_attempt(
            item,
            paper,
            candidate,
            started_at=datetime.now(UTC),
            status=status,
            failure_kind=failure_kind,
            http_status=None,
            error=error,
        )

    def _release_mcp_item(self, item: FullTextQueueItem, failure_kind: str, message: str) -> None:
        factors = dict(item.reason_factors or {})
        snapshot_raw = factors.pop("paper_search_mcp_claim", None)
        snapshot = snapshot_raw if isinstance(snapshot_raw, dict) else {}
        item.reason_factors = factors
        item.status = "pending"
        item.failure_kind = snapshot.get("failure_kind") if isinstance(snapshot.get("failure_kind"), str) else None
        item.last_error = snapshot.get("last_error") if isinstance(snapshot.get("last_error"), str) else None
        raw_next = snapshot.get("next_attempt_at")
        item.next_attempt_at = datetime.fromisoformat(raw_next) if isinstance(raw_next, str) and raw_next else None
        self._clear_lease(item)
        self.session.commit()

    @staticmethod
    def _clear_mcp_claim_snapshot(item: FullTextQueueItem) -> None:
        factors = dict(item.reason_factors or {})
        factors.pop("paper_search_mcp_claim", None)
        item.reason_factors = factors


__all__ = ("PaperSearchMcpFullTextWorker",)
