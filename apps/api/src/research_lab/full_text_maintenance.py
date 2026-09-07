from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from research_lab.models import FullTextQueueItem, Paper, PaperChunk, PaperContentProfile


class FullTextQueueMaintenance:
    """Keep the full-text queue aligned with the paper corpus.

    Bulk metadata imports can add tens of thousands of papers without going
    through the normal discovery path. This maintenance pass is intentionally
    independent of the enrichment workers so a hung worker cannot prevent an
    expired lease from being reclaimed or new papers from entering the queue.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self,
        *,
        limit: int = 10_000,
        stale_grace_minutes: int = 5,
        commit_every: int = 500,
    ) -> dict[str, int]:
        recovered = self.recover_expired_leases(stale_grace_minutes=stale_grace_minutes)
        stats = self.backfill_missing(
            limit=max(limit, 1),
            commit_every=max(commit_every, 1),
        )
        return {"expired_leases_recovered": recovered, **stats}

    def recover_expired_leases(self, *, stale_grace_minutes: int = 5) -> int:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=max(stale_grace_minutes, 0))
        rows = list(
            self.session.scalars(
                select(FullTextQueueItem)
                .where(
                    FullTextQueueItem.status == "processing",
                    or_(
                        FullTextQueueItem.lease_expires_at.is_(None),
                        FullTextQueueItem.lease_expires_at <= cutoff,
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
            item.last_error = "Recovered expired full-text worker lease by queue maintenance"
            item.next_attempt_at = now
        if rows:
            self.session.commit()
        return len(rows)

    def backfill_missing(self, *, limit: int, commit_every: int = 500) -> dict[str, int]:
        has_profile = exists(
            select(PaperContentProfile.paper_id).where(PaperContentProfile.paper_id == Paper.id)
        )
        has_queue = exists(select(FullTextQueueItem.id).where(FullTextQueueItem.paper_id == Paper.id))
        has_chunks = exists(select(PaperChunk.id).where(PaperChunk.paper_id == Paper.id))
        profiles_created = 0
        queue_items_created = 0
        available_profiles = 0
        restricted_profiles = 0
        processed = 0
        now = datetime.now(UTC)

        batch_size = min(max(commit_every, 1), max(limit, 1))
        while processed < limit:
            rows = list(
                self.session.execute(
                    select(
                        Paper,
                        has_profile.label("has_profile"),
                        has_queue.label("has_queue"),
                        has_chunks.label("has_chunks"),
                    )
                    .where(or_(~has_profile, ~has_queue))
                    .order_by(Paper.created_at, Paper.id)
                    .limit(min(batch_size, limit - processed))
                )
            )
            if not rows:
                break

            for paper, row_has_profile, row_has_queue, row_has_chunks in rows:
                processed += 1
                profile = self.session.get(PaperContentProfile, paper.id) if row_has_profile else None
                if profile is None:
                    profile = PaperContentProfile(paper_id=paper.id)
                    self.session.add(profile)
                    profiles_created += 1

                abstract_ready = bool(paper.abstract and paper.abstract.strip())
                profile.abstract_status = "available" if abstract_ready else "missing"
                profile.abstract_updated_at = paper.updated_at if abstract_ready else None

                if row_has_chunks:
                    profile.full_text_status = "available"
                    profile.full_text_access = "open_access" if paper.is_oa else "unknown"
                    profile.rights_status = "open_access" if paper.is_oa else "unknown"
                    profile.full_text_updated_at = paper.updated_at or now
                    available_profiles += 1
                    if not row_has_queue:
                        self.session.add(
                            FullTextQueueItem(
                                paper_id=paper.id,
                                status="completed",
                                priority=100,
                                rights_status="open_access" if paper.is_oa else "unknown",
                                reason_factors={"maintenance_backfill": True, "full_text_already_available": True},
                            )
                        )
                        queue_items_created += 1
                else:
                    priority, rights_status, access, reason_factors = _queue_policy(
                        paper,
                        abstract_ready=abstract_ready,
                    )
                    profile.full_text_priority = priority
                    profile.full_text_access = access
                    profile.rights_status = rights_status
                    if priority <= 0:
                        profile.full_text_status = "restricted"
                        profile.full_text_updated_at = now
                        restricted_profiles += 1
                        if not row_has_queue:
                            self.session.add(
                                FullTextQueueItem(
                                    paper_id=paper.id,
                                    status="restricted",
                                    priority=0,
                                    rights_status="unknown",
                                    reason_factors=reason_factors,
                                    failure_kind="missing_resolvable_identity",
                                )
                            )
                            queue_items_created += 1
                    else:
                        profile.full_text_status = "queued"
                        if not row_has_queue:
                            self.session.add(
                                FullTextQueueItem(
                                    paper_id=paper.id,
                                    status="pending",
                                    priority=priority,
                                    rights_status=rights_status,
                                    reason_factors=reason_factors,
                                    next_attempt_at=now,
                                )
                            )
                            queue_items_created += 1

            self.session.commit()
        return {
            "papers_examined": processed,
            "profiles_created": profiles_created,
            "queue_items_created": queue_items_created,
            "profiles_marked_available": available_profiles,
            "profiles_marked_restricted": restricted_profiles,
        }


def _queue_policy(paper: Paper, *, abstract_ready: bool) -> tuple[int, str, str, dict[str, Any]]:
    has_identity = bool(paper.doi or paper.arxiv_id or paper.openalex_id or paper.s2_id or paper.s2_corpus_id)
    if not has_identity and not paper.pdf_url:
        return 0, "unknown", "unknown", {"resolver_discovery": False}

    if paper.is_oa and paper.pdf_url:
        priority = 100
    elif paper.is_oa and paper.arxiv_id:
        priority = 98
    elif paper.is_oa:
        priority = 90
    elif paper.pdf_url:
        priority = 70
    else:
        priority = 50
    if abstract_ready:
        priority = min(100, priority + 2)
    rights_status = "open_access" if paper.is_oa else "unknown"
    access = "open_access" if paper.is_oa else "unknown"
    return (
        priority,
        rights_status,
        access,
        {
            "maintenance_backfill": True,
            "open_access": bool(paper.is_oa),
            "pdf_available": bool(paper.pdf_url),
            "resolver_discovery": bool(has_identity),
            "abstract_ready": abstract_ready,
        },
    )


__all__ = ("FullTextQueueMaintenance",)
