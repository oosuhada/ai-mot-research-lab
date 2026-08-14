from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.corpus_intelligence import refresh_corpus_intelligence
from research_lab.ingestion.openalex import OpenAlexClient
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import DailyDiscoveryEvent, IngestionRun
from research_lab.taxonomy import RESEARCH_AXES, TAXONOMY_VERSION, text_matches_axis


class DailyDiscoveryWorker:
    """Incrementally discover recent publications without touching corpus state.json."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: OpenAlexClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.client = client or OpenAlexClient(settings)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(
        self,
        *,
        lookback_days: int = 3,
        max_pages_per_axis: int = 2,
        through_date: date | None = None,
    ) -> dict[str, Any]:
        end_date = through_date or datetime.now(UTC).date()
        start_date = end_date - timedelta(days=max(lookback_days, 1) - 1)
        page_limit = min(max(max_pages_per_axis, 1), 100)
        run = IngestionRun(
            source="openalex_daily_discovery",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={
                "from_publication_date": start_date.isoformat(),
                "to_publication_date": end_date.isoformat(),
                "max_pages_per_axis": page_limit,
                "paging": "independent daily publication-date window",
            },
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        service = OpenAlexIngestionService(
            self.session,
            self.settings,
            client=self.client,
            preload_caches=False,
        )
        service.prepare_for_batch()
        retrieved_at = datetime.now(UTC)
        discovered_ids: set[str] = set()
        try:
            for axis in RESEARCH_AXES:
                for page in range(1, page_limit + 1):
                    records, result_count = self.client.fetch_axis_date_page(
                        axis,
                        from_date=start_date,
                        to_date=end_date,
                        page=page,
                        per_page=100,
                    )
                    run.fetched_count += len(records)
                    for record in records:
                        text = f"{record.title}\n{record.abstract or ''}"
                        if not text_matches_axis(text, axis):
                            run.skipped_count += 1
                            continue
                        paper, inserted = service.upsert_axis_record(
                            record,
                            axis,
                            retrieved_at=retrieved_at,
                        )
                        run.accepted_count += 1
                        if inserted:
                            run.inserted_count += 1
                            discovered_ids.add(str(paper.id))
                            self._record_discovery(paper.id, retrieved_at)
                        else:
                            run.updated_count += 1
                    run.checkpoint = {
                        "axis": axis.slug,
                        "page": page,
                        "new_papers": len(discovered_ids),
                    }
                    self.session.commit()
                    if not records or len(records) < 100 or result_count <= page * 100:
                        break

            intelligence = refresh_corpus_intelligence(
                self.session,
                discovery_days=lookback_days,
                create_discovery_events=False,
            )
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
            return {
                "run_id": str(run.id),
                "status": run.status,
                "from_date": start_date.isoformat(),
                "to_date": end_date.isoformat(),
                "fetched": run.fetched_count,
                "accepted": run.accepted_count,
                "inserted": run.inserted_count,
                "updated": run.updated_count,
                "skipped": run.skipped_count,
                "new_papers": len(discovered_ids),
                "intelligence": intelligence,
            }
        except Exception as exc:
            self.session.rollback()
            persisted = self.session.get(IngestionRun, run.id)
            if persisted is not None:
                persisted.status = "failed"
                persisted.error_count += 1
                persisted.error_message = str(exc)[:1000]
                persisted.finished_at = datetime.now(UTC)
                self.session.commit()
            raise
        finally:
            self.close()

    def _record_discovery(self, paper_id: uuid.UUID, detected_at: datetime) -> None:
        existing = self.session.scalar(
            select(DailyDiscoveryEvent).where(
                DailyDiscoveryEvent.paper_id == paper_id,
                DailyDiscoveryEvent.event_kind == "newly_discovered",
                DailyDiscoveryEvent.event_date == detected_at.date(),
            )
        )
        if existing is None:
            self.session.add(
                DailyDiscoveryEvent(
                    paper_id=paper_id,
                    event_kind="newly_discovered",
                    event_date=detected_at.date(),
                    relevance_score=0.6,
                    novelty_score=0.7,
                    summary=(
                        "Newly discovered in the daily AI × MOT publication window. "
                        "Relevance is system inference and should be verified from the record."
                    ),
                    signals={"source": "openalex_daily_discovery", "new_record": True},
                )
            )
