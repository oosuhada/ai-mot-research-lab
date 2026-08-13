from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.ingestion.openalex import OpenAlexClient
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import IngestionRun, Paper
from research_lab.taxonomy import AXIS_BY_SLUG, RESEARCH_AXES, TAXONOMY_VERSION, text_matches_axis


@dataclass(slots=True)
class ExpansionState:
    target_total: int
    from_year: int
    to_year: int
    slice_index: int = 0
    page: int = 1
    fetched_total: int = 0
    accepted_total: int = 0
    inserted_total: int = 0
    updated_total: int = 0
    skipped_total: int = 0
    completed_slices: int = 0
    started_at: str = ""
    updated_at: str = ""
    last_error: str | None = None


def expansion_slices(from_year: int, to_year: int) -> list[tuple[str, int]]:
    years = range(to_year, from_year - 1, -1)
    return [(axis.slug, year) for year in years for axis in RESEARCH_AXES]


class CorpusExpansionWorker:
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
        self.state_path = settings.artifact_root / "corpus-expansion" / "state.json"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run_batch(
        self,
        *,
        target_total: int = 100_000,
        from_year: int = 2017,
        to_year: int = 2026,
        max_pages: int = 5,
    ) -> dict[str, Any]:
        state = self._load_state(target_total=target_total, from_year=from_year, to_year=to_year)
        slices = expansion_slices(state.from_year, state.to_year)
        corpus_count = self._corpus_count()
        if corpus_count >= state.target_total or state.slice_index >= len(slices):
            return self.status(state=state, status="completed")

        run = IngestionRun(
            source="openalex_expansion",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={
                "target_total": state.target_total,
                "from_year": state.from_year,
                "to_year": state.to_year,
                "max_pages": max_pages,
                "paging": "year-sliced basic paging",
            },
            checkpoint={"slice_index": state.slice_index, "page": state.page},
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
        pages_processed = 0
        try:
            while pages_processed < max_pages and state.slice_index < len(slices):
                if self._corpus_count() >= state.target_total:
                    break
                axis_slug, year = slices[state.slice_index]
                axis = AXIS_BY_SLUG[axis_slug]
                records, result_count = self.client.fetch_axis_year_page(
                    axis,
                    year=year,
                    page=state.page,
                    per_page=100,
                )
                run.fetched_count += len(records)
                state.fetched_total += len(records)
                retrieved_at = datetime.now(UTC)
                for record in records:
                    text = f"{record.title}\n{record.abstract or ''}"
                    if not text_matches_axis(text, axis):
                        run.skipped_count += 1
                        state.skipped_total += 1
                        continue
                    _, inserted = service.upsert_axis_record(
                        record,
                        axis,
                        retrieved_at=retrieved_at,
                    )
                    run.accepted_count += 1
                    state.accepted_total += 1
                    if inserted:
                        run.inserted_count += 1
                        state.inserted_total += 1
                    else:
                        run.updated_count += 1
                        state.updated_total += 1

                pages_processed += 1
                last_page = not records or len(records) < 100 or state.page >= 100
                if result_count <= state.page * 100:
                    last_page = True
                if last_page:
                    state.slice_index += 1
                    state.completed_slices += 1
                    state.page = 1
                else:
                    state.page += 1
                state.last_error = None
                state.updated_at = datetime.now(UTC).isoformat()
                run.checkpoint = {
                    "slice_index": state.slice_index,
                    "page": state.page,
                    "pages_processed": pages_processed,
                    "corpus_count": self._corpus_count(),
                }
                self.session.commit()
                self._save_state(state)

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
            return self.status(state=state, status="running") | {"run_id": str(run.id)}
        except httpx.HTTPStatusError as exc:
            self.session.rollback()
            state.last_error = f"HTTP {exc.response.status_code}: {exc.response.text[:300]}"
            state.updated_at = datetime.now(UTC).isoformat()
            self._save_state(state)
            persisted = self.session.get(IngestionRun, run.id)
            if persisted is not None:
                persisted.status = "paused_rate_limit" if exc.response.status_code in {403, 429} else "failed"
                persisted.error_count += 1
                persisted.error_message = state.last_error
                persisted.finished_at = datetime.now(UTC)
                self.session.commit()
            return self.status(state=state, status="paused") | {"run_id": str(run.id)}
        finally:
            self.close()

    def status(self, *, state: ExpansionState | None = None, status: str = "idle") -> dict[str, Any]:
        current = state or self._load_state(target_total=100_000, from_year=2017, to_year=2026)
        slices = expansion_slices(current.from_year, current.to_year)
        active_slice = None
        if current.slice_index < len(slices):
            axis_slug, year = slices[current.slice_index]
            active_slice = {"axis": axis_slug, "year": year, "page": current.page}
        corpus_count = self._corpus_count()
        return {
            "status": status,
            "corpus_count": corpus_count,
            "target_total": current.target_total,
            "progress_pct": round(min(corpus_count / current.target_total, 1.0) * 100, 3),
            "active_slice": active_slice,
            "completed_slices": current.completed_slices,
            "total_slices": len(slices),
            "fetched_total": current.fetched_total,
            "accepted_total": current.accepted_total,
            "inserted_total": current.inserted_total,
            "updated_total": current.updated_total,
            "skipped_total": current.skipped_total,
            "last_error": current.last_error,
            "updated_at": current.updated_at,
            "state_path": str(self.state_path),
        }

    def _corpus_count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Paper)) or 0)

    def _load_state(self, *, target_total: int, from_year: int, to_year: int) -> ExpansionState:
        if self.state_path.exists():
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            state = ExpansionState(**payload)
            if (state.from_year, state.to_year) != (from_year, to_year):
                raise ValueError("Existing corpus-expansion year range differs from requested range")
            state.target_total = max(state.target_total, target_total)
            return state
        now = datetime.now(UTC).isoformat()
        state = ExpansionState(
            target_total=target_total,
            from_year=from_year,
            to_year=to_year,
            started_at=now,
            updated_at=now,
        )
        self._save_state(state)
        return state

    def _save_state(self, state: ExpansionState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(asdict(state), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
