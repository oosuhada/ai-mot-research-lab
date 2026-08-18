from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    slice_pages: dict[str, int] = field(default_factory=dict)
    completed_slice_keys: list[str] = field(default_factory=list)


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
        _hydrate_round_robin_state(state, slices)
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
                slice_key = _slice_key(axis_slug, year)
                current_page = state.slice_pages.get(slice_key, state.page)
                axis = AXIS_BY_SLUG[axis_slug]
                records, result_count = self.client.fetch_axis_year_page(
                    axis,
                    year=year,
                    page=current_page,
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
                    try:
                        with self.session.begin_nested():
                            _, inserted = service.upsert_axis_record(
                                record,
                                axis,
                                retrieved_at=retrieved_at,
                            )
                    except ValueError as exc:
                        # A single malformed/conflicting provider identity must not
                        # terminate the whole page. The savepoint discards partial
                        # writes for this record while preserving the batch/checkpoint.
                        run.error_count += 1
                        run.skipped_count += 1
                        state.skipped_total += 1
                        run.error_message = f"identity conflict: {exc}"[:1000]
                        continue
                    run.accepted_count += 1
                    state.accepted_total += 1
                    if inserted:
                        run.inserted_count += 1
                        state.inserted_total += 1
                    else:
                        run.updated_count += 1
                        state.updated_total += 1

                pages_processed += 1
                last_page = not records or len(records) < 100 or current_page >= 100
                if result_count <= current_page * 100:
                    last_page = True
                if last_page:
                    if slice_key not in state.completed_slice_keys:
                        state.completed_slice_keys.append(slice_key)
                    state.slice_pages.pop(slice_key, None)
                else:
                    state.slice_pages[slice_key] = current_page + 1
                state.completed_slices = len(state.completed_slice_keys)
                state.slice_index = _next_slice_index(
                    slices,
                    state.slice_index,
                    set(state.completed_slice_keys),
                )
                if state.slice_index < len(slices):
                    next_axis, next_year = slices[state.slice_index]
                    state.page = state.slice_pages.get(_slice_key(next_axis, next_year), 1)
                else:
                    state.page = 1
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
        self._reconcile_totals_from_run_ledger(current)
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

    def _reconcile_totals_from_run_ledger(self, state: ExpansionState) -> None:
        """Recover monotonic expansion counters from persisted ingestion-run rows.

        Runtime state can be replaced during operational recovery. The ingestion-run
        ledger is database-backed, so status should never regress to zero simply
        because state.json was recreated.
        """
        totals = self.session.execute(
            select(
                func.coalesce(func.sum(IngestionRun.fetched_count), 0),
                func.coalesce(func.sum(IngestionRun.accepted_count), 0),
                func.coalesce(func.sum(IngestionRun.inserted_count), 0),
                func.coalesce(func.sum(IngestionRun.updated_count), 0),
                func.coalesce(func.sum(IngestionRun.skipped_count), 0),
            ).where(IngestionRun.source == "openalex_expansion")
        ).one()
        state.fetched_total = max(state.fetched_total, int(totals[0] or 0))
        state.accepted_total = max(state.accepted_total, int(totals[1] or 0))
        state.inserted_total = max(state.inserted_total, int(totals[2] or 0))
        state.updated_total = max(state.updated_total, int(totals[3] or 0))
        state.skipped_total = max(state.skipped_total, int(totals[4] or 0))

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


def _slice_key(axis_slug: str, year: int) -> str:
    return f"{axis_slug}:{year}"


def _hydrate_round_robin_state(state: ExpansionState, slices: list[tuple[str, int]]) -> None:
    if not state.completed_slice_keys and state.completed_slices:
        state.completed_slice_keys = [_slice_key(axis, year) for axis, year in slices[: state.completed_slices]]
    if state.slice_index < len(slices):
        axis_slug, year = slices[state.slice_index]
        key = _slice_key(axis_slug, year)
        if key not in state.completed_slice_keys:
            state.slice_pages.setdefault(key, state.page)


def _next_slice_index(
    slices: list[tuple[str, int]],
    current_index: int,
    completed_keys: set[str],
) -> int:
    if len(completed_keys) >= len(slices):
        return len(slices)
    for offset in range(1, len(slices) + 1):
        candidate = (current_index + offset) % len(slices)
        axis_slug, year = slices[candidate]
        if _slice_key(axis_slug, year) not in completed_keys:
            return candidate
    return len(slices)
