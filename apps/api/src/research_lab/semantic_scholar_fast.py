from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.ingestion.normalization import normalize_arxiv_id, normalize_doi
from research_lab.models import FullTextQueueItem, IngestionRun, Paper, PaperContentProfile
from research_lab.taxonomy import TAXONOMY_VERSION

SOURCE = "semantic_scholar_batch_api"
FIELDS = (
    "paperId,corpusId,externalIds,isOpenAccess,openAccessPdf,"
    "citationCount,referenceCount"
)


@dataclass(slots=True)
class SemanticScholarBatchMappingResult:
    run_id: str
    status: str
    selected: int
    requests: int
    found: int
    updated: int
    already_mapped: int
    not_found: int
    conflicts: int
    oa_pdf_discovered: int
    queue_reactivated: int


class SemanticScholarBatchMapper:
    """Fast exact-ID mapper using Semantic Scholar's 500-paper batch endpoint."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        min_interval_seconds: float = 1.50,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        api_key = (settings.semantic_scholar_api_key or "").strip()
        if not api_key:
            raise RuntimeError("SEMANTIC_SCHOLAR_API_KEY is required")
        self.session = session
        self.settings = settings
        self.min_interval_seconds = max(min_interval_seconds, 0.0)
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request_at = 0.0
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={
                "x-api-key": api_key,
                "User-Agent": "ai-mot-research-lab/0.1 Semantic Scholar batch mapper",
                "Accept": "application/json",
            },
        )
        self.base_url = settings.semantic_scholar_base_url.rstrip("/")
        existing = self.session.execute(
            select(Paper.id, Paper.s2_id, Paper.s2_corpus_id).where(
                or_(Paper.s2_id.is_not(None), Paper.s2_corpus_id.is_not(None))
            )
        )
        self._s2_owners: dict[str, object] = {}
        self._corpus_owners: dict[str, object] = {}
        for paper_id, s2_id, corpus_id in existing:
            if s2_id:
                self._s2_owners[s2_id] = paper_id
            if corpus_id:
                self._corpus_owners[corpus_id] = paper_id

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(self, *, max_items: int = 200_000, batch_size: int = 500) -> SemanticScholarBatchMappingResult:
        batch_size = min(max(batch_size, 1), 500)
        candidates = list(
            self.session.scalars(
                select(Paper)
                .where(
                    or_(Paper.s2_id.is_(None), Paper.s2_corpus_id.is_(None)),
                    or_(Paper.doi.is_not(None), Paper.arxiv_id.is_not(None)),
                )
                .order_by(Paper.id)
                .limit(max(max_items, 1))
            )
        )
        run = IngestionRun(
            source=SOURCE,
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={"selected": len(candidates), "batch_size": batch_size},
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        stats = {
            "requests": 0,
            "found": 0,
            "updated": 0,
            "already_mapped": 0,
            "not_found": 0,
            "conflicts": 0,
            "oa_pdf_discovered": 0,
            "queue_reactivated": 0,
        }
        try:
            for offset in range(0, len(candidates), batch_size):
                batch = candidates[offset : offset + batch_size]
                ids = [self._lookup_id(paper) for paper in batch]
                records = self._request_batch(ids)
                stats["requests"] += 1
                batch_paper_ids = [paper.id for paper in batch]
                profiles = {
                    profile.paper_id: profile
                    for profile in self.session.scalars(
                        select(PaperContentProfile).where(
                            PaperContentProfile.paper_id.in_(batch_paper_ids)
                        )
                    )
                }
                queues = {
                    item.paper_id: item
                    for item in self.session.scalars(
                        select(FullTextQueueItem).where(
                            FullTextQueueItem.paper_id.in_(batch_paper_ids)
                        )
                    )
                }
                for paper, requested_id, record in zip(batch, ids, records, strict=True):
                    run.fetched_count += 1
                    if record is None:
                        stats["not_found"] += 1
                        run.skipped_count += 1
                        continue
                    if not isinstance(record, dict) or not self._response_matches(paper, requested_id, record):
                        stats["conflicts"] += 1
                        run.error_count += 1
                        continue
                    stats["found"] += 1
                    run.accepted_count += 1
                    changed, oa_pdf, reactivated = self._apply(
                        paper,
                        record,
                        profile=profiles.get(paper.id),
                        queue=queues.get(paper.id),
                    )
                    if changed:
                        stats["updated"] += 1
                        run.updated_count += 1
                    else:
                        stats["already_mapped"] += 1
                        run.skipped_count += 1
                    stats["oa_pdf_discovered"] += int(oa_pdf)
                    stats["queue_reactivated"] += int(reactivated)

                run.checkpoint = {
                    "updated_at": datetime.now(UTC).isoformat(),
                    "processed": min(offset + len(batch), len(candidates)),
                    "selected": len(candidates),
                    **stats,
                }
                self.session.commit()

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            persisted = self.session.get(IngestionRun, run.id)
            if persisted is not None:
                persisted.status = "failed"
                persisted.error_count += 1
                persisted.error_message = f"{type(exc).__name__}: {exc}"[:2000]
                persisted.finished_at = datetime.now(UTC)
                self.session.commit()
            raise
        finally:
            self.close()

        return SemanticScholarBatchMappingResult(
            run_id=str(run.id),
            status=run.status,
            selected=len(candidates),
            **stats,
        )

    @staticmethod
    def _lookup_id(paper: Paper) -> str:
        doi = normalize_doi(paper.doi)
        if doi:
            return f"DOI:{doi}"
        arxiv = normalize_arxiv_id(paper.arxiv_id)
        if arxiv:
            return f"ARXIV:{arxiv}"
        raise ValueError(f"Paper {paper.id} has no supported Semantic Scholar lookup ID")

    def _wait_for_slot(self) -> None:
        if self._last_request_at <= 0:
            return
        remaining = self.min_interval_seconds - (self.monotonic() - self._last_request_at)
        if remaining > 0:
            self.sleep(remaining)

    def _request_batch(self, ids: list[str]) -> list[dict[str, object] | None]:
        url = f"{self.base_url}/paper/batch"
        attempt = 0
        while True:
            self._wait_for_slot()
            self._last_request_at = self.monotonic()
            try:
                response = self.client.post(url, params={"fields": FIELDS}, json={"ids": ids})
            except httpx.TransportError as exc:
                attempt += 1
                delay = min(max(5.0 * (2 ** min(attempt - 1, 4)), 5.0), 60.0)
                self._log_retry("transport_error", attempt, delay, detail=type(exc).__name__)
                self.sleep(delay)
                continue

            if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
                attempt += 1
                retry_after = response.headers.get("Retry-After")
                try:
                    retry_after_seconds = float(retry_after) if retry_after else 0.0
                except ValueError:
                    retry_after_seconds = 0.0
                exponential = min(5.0 * (2 ** min(attempt - 1, 4)), 60.0)
                delay = max(retry_after_seconds, exponential, self.min_interval_seconds)
                self._log_retry(
                    "http_retry",
                    attempt,
                    delay,
                    detail=str(response.status_code),
                )
                self.sleep(delay)
                continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) != len(ids):
                raise RuntimeError("Semantic Scholar batch response length did not match request")
            return payload

    @staticmethod
    def _log_retry(kind: str, attempt: int, delay: float, *, detail: str) -> None:
        # CLI stdout is machine-readable JSON, so retry diagnostics belong on stderr.
        print(
            json.dumps(
                {
                    "event": "semantic_scholar_retry",
                    "kind": kind,
                    "attempt": attempt,
                    "retry_seconds": round(delay, 2),
                    "detail": detail,
                }
            ),
            file=sys.stderr,
            flush=True,
        )

    @staticmethod
    def _response_matches(paper: Paper, requested_id: str, record: dict[str, object]) -> bool:
        external = record.get("externalIds") or record.get("externalids") or {}
        external = external if isinstance(external, dict) else {}
        if requested_id.startswith("DOI:"):
            expected = normalize_doi(paper.doi)
            actual = normalize_doi(external.get("DOI") or external.get("doi"))
            return bool(expected and actual and expected == actual)
        if requested_id.startswith("ARXIV:"):
            expected = normalize_arxiv_id(paper.arxiv_id)
            actual = normalize_arxiv_id(external.get("ArXiv") or external.get("arxiv"))
            return bool(expected and actual and expected == actual)
        return False

    def _apply(
        self,
        paper: Paper,
        record: dict[str, object],
        *,
        profile: PaperContentProfile | None,
        queue: FullTextQueueItem | None,
    ) -> tuple[bool, bool, bool]:
        paper_id = str(record.get("paperId") or "").strip() or None
        corpus_raw = record.get("corpusId") or record.get("corpusid")
        corpus_id = str(corpus_raw) if corpus_raw is not None else None
        if paper_id and paper.s2_id and paper.s2_id != paper_id:
            return False, False, False
        if corpus_id and paper.s2_corpus_id and paper.s2_corpus_id != corpus_id:
            return False, False, False
        if paper_id and paper_id in self._s2_owners and self._s2_owners[paper_id] != paper.id:
            return False, False, False
        if corpus_id and corpus_id in self._corpus_owners and self._corpus_owners[corpus_id] != paper.id:
            return False, False, False

        changed = False
        if paper_id and not paper.s2_id:
            paper.s2_id = paper_id
            self._s2_owners[paper_id] = paper.id
            changed = True
        if corpus_id and not paper.s2_corpus_id:
            paper.s2_corpus_id = corpus_id
            self._corpus_owners[corpus_id] = paper.id
            changed = True

        pdf = record.get("openAccessPdf") or record.get("openaccesspdf") or {}
        pdf = pdf if isinstance(pdf, dict) else {}
        pdf_url = str(pdf.get("url") or "").strip()
        is_open = record.get("isOpenAccess") is True or bool(pdf_url)
        oa_pdf_discovered = bool(pdf_url and not paper.pdf_url)
        if oa_pdf_discovered:
            paper.pdf_url = pdf_url
            changed = True
        if is_open and not paper.is_oa:
            paper.is_oa = True
            changed = True
        status = str(pdf.get("status") or "").strip().lower()
        if status and status != "closed" and not paper.oa_status:
            paper.oa_status = status
            changed = True
        license_label = str(pdf.get("license") or "").strip()
        if license_label and not paper.license:
            paper.license = license_label
            changed = True

        provenance = dict(paper.provenance or {})
        snapshot = {
            "paper_id": paper_id,
            "corpus_id": corpus_id,
            "citation_count": record.get("citationCount"),
            "reference_count": record.get("referenceCount"),
            "is_open_access": record.get("isOpenAccess"),
            "open_access_pdf": pdf_url or None,
            "source": "Semantic Scholar Graph batch API",
        }
        if provenance.get("semantic_scholar_api") != snapshot:
            provenance["semantic_scholar_api"] = snapshot
            paper.provenance = provenance
            changed = True

        queue_reactivated = False
        if is_open:
            if profile is not None:
                profile.rights_status = "open_access"
                if profile.full_text_status != "available":
                    profile.full_text_access = "open_access"
                    profile.full_text_priority = max(profile.full_text_priority, 95)
                    if profile.full_text_status in {"not_requested", "failed", "restricted"}:
                        profile.full_text_status = "queued"
            if queue is not None and queue.status != "completed":
                queue.rights_status = "open_access"
                queue.priority = max(queue.priority, 95)
                if pdf_url and queue.status in {"failed", "restricted"}:
                    queue.status = "pending"
                    queue.failure_kind = None
                    queue.last_error = None
                    queue.next_attempt_at = datetime.now(UTC)
                    queue.worker_id = None
                    queue.claimed_at = None
                    queue.lease_expires_at = None
                    queue_reactivated = True
        if changed:
            paper.retrieved_at = datetime.now(UTC)
        return changed, oa_pdf_discovered, queue_reactivated
