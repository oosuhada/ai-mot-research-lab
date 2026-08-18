from __future__ import annotations

import gzip
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.ingestion.openalex import OpenAlexClient, OpenAlexRecord
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import IngestionRun, Paper
from research_lab.taxonomy import AXIS_BY_SLUG, RESEARCH_AXES, TAXONOMY_VERSION, text_matches_axis


@dataclass(slots=True)
class BulkBootstrapState:
    target_total: int
    from_year: int
    to_year: int
    slice_index: int = 0
    basic_pages: dict[str, int] = field(default_factory=dict)
    cursors: dict[str, str] = field(default_factory=dict)
    slice_requests: dict[str, int] = field(default_factory=dict)
    completed_slice_keys: list[str] = field(default_factory=list)
    fetched_total: int = 0
    accepted_total: int = 0
    inserted_total: int = 0
    updated_total: int = 0
    skipped_total: int = 0
    error_total: int = 0
    requests_total: int = 0
    request_day: str = ""
    requests_today: int = 0
    started_at: str = ""
    updated_at: str = ""
    last_error: str | None = None


def bulk_bootstrap_slices(from_year: int, to_year: int) -> list[tuple[str, int]]:
    years = range(to_year, from_year - 1, -1)
    return [(axis.slug, year) for year in years for axis in RESEARCH_AXES]


class OpenAlexBulkBootstrapWorker:
    """Build the initial corpus from bounded cursor-paged OpenAlex metadata."""

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
        self.state_path = settings.artifact_root / "corpus-bulk-bootstrap" / "state.json"
        self.page_root = settings.artifact_root / "corpus-bulk-bootstrap" / "pages"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run_batch(
        self,
        *,
        target_total: int = 100_000,
        from_year: int = 2017,
        to_year: int = 2026,
        max_requests: int = 50,
        daily_request_cap: int = 480,
    ) -> dict[str, Any]:
        state = self._load_state(target_total=target_total, from_year=from_year, to_year=to_year)
        self._refresh_daily_counter(state)
        slices = bulk_bootstrap_slices(state.from_year, state.to_year)
        if self._corpus_count() >= state.target_total or len(state.completed_slice_keys) >= len(slices):
            return self.status(state=state, status="completed")
        if not self.settings.openalex_api_key:
            return self.status(state=state, status="blocked_no_api_key")
        requests_available = max(daily_request_cap - state.requests_today, 0)
        requests_allowed = min(max(max_requests, 1), requests_available)
        if requests_allowed <= 0:
            self._save_state(state)
            return self.status(state=state, status="paused_daily_budget")

        run = IngestionRun(
            source="openalex_bulk_bootstrap",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={
                "target_total": state.target_total,
                "from_year": state.from_year,
                "to_year": state.to_year,
                "max_requests": max_requests,
                "daily_request_cap": daily_request_cap,
                "paging": "cursor",
                "search_scope": "title_and_abstract",
                "has_abstract": True,
                "language": "en",
                "axes": [
                    {"slug": axis.slug, "query": axis.openalex_query}
                    for axis in RESEARCH_AXES
                ],
            },
            checkpoint={"slice_index": state.slice_index},
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
        requests_processed = 0
        try:
            while requests_processed < requests_allowed:
                if self._corpus_count() >= state.target_total:
                    break
                if len(state.completed_slice_keys) >= len(slices):
                    break

                state.slice_index = _next_bulk_slice_index(
                    slices,
                    state.slice_index,
                    set(state.completed_slice_keys),
                )
                if state.slice_index >= len(slices):
                    break

                axis_slug, year = slices[state.slice_index]
                slice_key = _slice_key(axis_slug, year)
                axis = AXIS_BY_SLUG[axis_slug]
                basic_page = state.basic_pages.get(slice_key, 1)
                pagination_mode = "basic_page"
                cursor: str | None = None
                next_cursor: str | None = None
                if basic_page <= 100:
                    records, result_count = self.client.fetch_axis_year_page(
                        axis,
                        year=year,
                        page=basic_page,
                        per_page=100,
                    )
                else:
                    pagination_mode = "cursor"
                    cursor = state.cursors.get(slice_key, "*")
                    records, next_cursor, result_count = self.client.fetch_axis_year_cursor_page(
                        axis,
                        year=year,
                        cursor=cursor,
                        per_page=100,
                    )
                request_number = state.slice_requests.get(slice_key, 0) + 1
                self._write_raw_page(
                    slice_key=slice_key,
                    request_number=request_number,
                    pagination_mode=pagination_mode,
                    basic_page=basic_page if pagination_mode == "basic_page" else None,
                    cursor=cursor,
                    next_cursor=next_cursor,
                    result_count=result_count,
                    records=records,
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
                        run.error_count += 1
                        run.skipped_count += 1
                        state.error_total += 1
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

                requests_processed += 1
                state.requests_total += 1
                state.requests_today += 1
                state.slice_requests[slice_key] = request_number
                if pagination_mode == "basic_page":
                    last_basic_page = not records or len(records) < 100 or result_count <= basic_page * 100
                    if last_basic_page:
                        if slice_key not in state.completed_slice_keys:
                            state.completed_slice_keys.append(slice_key)
                        state.basic_pages.pop(slice_key, None)
                        state.cursors.pop(slice_key, None)
                    else:
                        state.basic_pages[slice_key] = basic_page + 1
                else:
                    if not records or not next_cursor or next_cursor == cursor:
                        if slice_key not in state.completed_slice_keys:
                            state.completed_slice_keys.append(slice_key)
                        state.cursors.pop(slice_key, None)
                    else:
                        state.cursors[slice_key] = next_cursor

                state.slice_index = _next_bulk_slice_index(
                    slices,
                    state.slice_index,
                    set(state.completed_slice_keys),
                    advance=True,
                )
                state.last_error = None
                state.updated_at = datetime.now(UTC).isoformat()
                run.checkpoint = {
                    "slice_index": state.slice_index,
                    "requests_processed": requests_processed,
                    "requests_total": state.requests_total,
                    "corpus_count": self._corpus_count(),
                }
                self.session.commit()
                self._save_state(state)

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
            final_status = "completed" if self._corpus_count() >= state.target_total else "running"
            return self.status(state=state, status=final_status) | {"run_id": str(run.id)}
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
        except Exception as exc:
            self.session.rollback()
            state.last_error = f"{type(exc).__name__}: {exc}"[:1000]
            state.updated_at = datetime.now(UTC).isoformat()
            self._save_state(state)
            persisted = self.session.get(IngestionRun, run.id)
            if persisted is not None:
                persisted.status = "failed"
                persisted.error_count += 1
                persisted.error_message = state.last_error
                persisted.finished_at = datetime.now(UTC)
                self.session.commit()
            raise
        finally:
            self.close()

    def status(
        self,
        *,
        state: BulkBootstrapState | None = None,
        status: str = "idle",
    ) -> dict[str, Any]:
        current = state or self._load_state(target_total=100_000, from_year=2017, to_year=2026)
        slices = bulk_bootstrap_slices(current.from_year, current.to_year)
        active_slice = None
        if current.slice_index < len(slices):
            axis_slug, year = slices[current.slice_index]
            key = _slice_key(axis_slug, year)
            basic_page = current.basic_pages.get(key, 1)
            active_slice = {
                "axis": axis_slug,
                "year": year,
                "pagination_mode": "basic_page" if basic_page <= 100 else "cursor",
                "page": basic_page if basic_page <= 100 else None,
                "cursor_started": key in current.cursors if basic_page > 100 else False,
                "requests": current.slice_requests.get(key, 0),
            }
        corpus_count = self._corpus_count()
        return {
            "status": status,
            "corpus_count": corpus_count,
            "target_total": current.target_total,
            "progress_pct": round(min(corpus_count / current.target_total, 1.0) * 100, 3),
            "active_slice": active_slice,
            "completed_slices": len(current.completed_slice_keys),
            "total_slices": len(slices),
            "requests_total": current.requests_total,
            "request_day": current.request_day,
            "requests_today": current.requests_today,
            "fetched_total": current.fetched_total,
            "accepted_total": current.accepted_total,
            "inserted_total": current.inserted_total,
            "updated_total": current.updated_total,
            "skipped_total": current.skipped_total,
            "error_total": current.error_total,
            "last_error": current.last_error,
            "updated_at": current.updated_at,
            "state_path": str(self.state_path),
            "raw_page_root": str(self.page_root),
        }

    def _corpus_count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Paper)) or 0)

    @staticmethod
    def _refresh_daily_counter(state: BulkBootstrapState) -> None:
        today = datetime.now(UTC).date().isoformat()
        if state.request_day != today:
            state.request_day = today
            state.requests_today = 0

    def _load_state(self, *, target_total: int, from_year: int, to_year: int) -> BulkBootstrapState:
        if self.state_path.exists():
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            state = BulkBootstrapState(**payload)
            if (state.from_year, state.to_year) != (from_year, to_year):
                raise ValueError("Existing corpus bulk-bootstrap year range differs from requested range")
            state.target_total = max(state.target_total, target_total)
            if self._hydrate_legacy_checkpoint(state):
                self._save_state(state)
            return state
        now = datetime.now(UTC).isoformat()
        state = BulkBootstrapState(
            target_total=target_total,
            from_year=from_year,
            to_year=to_year,
            started_at=now,
            updated_at=now,
        )
        self._hydrate_legacy_checkpoint(state)
        self._save_state(state)
        return state

    def _hydrate_legacy_checkpoint(self, state: BulkBootstrapState) -> bool:
        legacy_path = self.settings.artifact_root / "corpus-expansion" / "state.json"
        if not legacy_path.exists():
            return False
        payload = json.loads(legacy_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False
        return _merge_legacy_expansion_state(state, payload)

    def _save_state(self, state: BulkBootstrapState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(asdict(state), indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.state_path)

    def _write_raw_page(
        self,
        *,
        slice_key: str,
        request_number: int,
        pagination_mode: str,
        basic_page: int | None,
        cursor: str | None,
        next_cursor: str | None,
        result_count: int,
        records: list[OpenAlexRecord],
    ) -> Path:
        axis_slug, year = slice_key.rsplit(":", 1)
        directory = self.page_root / year / axis_slug
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"page-{request_number:05d}.json.gz"
        temp_path = path.with_suffix(".tmp.gz")
        payload = {
            "slice_key": slice_key,
            "pagination_mode": pagination_mode,
            "basic_page": basic_page,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "result_count": result_count,
            "downloaded_at": datetime.now(UTC).isoformat(),
            "records": [record.raw for record in records],
        }
        with gzip.open(temp_path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        temp_path.replace(path)
        return path


def _slice_key(axis_slug: str, year: int) -> str:
    return f"{axis_slug}:{year}"


def _next_bulk_slice_index(
    slices: list[tuple[str, int]],
    current_index: int,
    completed_keys: set[str],
    *,
    advance: bool = False,
) -> int:
    if len(completed_keys) >= len(slices):
        return len(slices)
    start_offset = 1 if advance else 0
    for offset in range(start_offset, len(slices) + start_offset):
        candidate = (current_index + offset) % len(slices)
        axis_slug, year = slices[candidate]
        if _slice_key(axis_slug, year) not in completed_keys:
            return candidate
    return len(slices)


def _merge_legacy_expansion_state(
    state: BulkBootstrapState,
    payload: dict[str, object],
) -> bool:
    changed = False
    raw_pages = payload.get("slice_pages")
    if isinstance(raw_pages, dict):
        for raw_key, raw_page in raw_pages.items():
            if not isinstance(raw_key, str):
                continue
            try:
                page = max(int(raw_page), 1)
            except (TypeError, ValueError):
                continue
            if page > state.basic_pages.get(raw_key, 1):
                state.basic_pages[raw_key] = page
                changed = True

    raw_completed = payload.get("completed_slice_keys")
    if isinstance(raw_completed, list):
        for raw_key in raw_completed:
            if isinstance(raw_key, str) and raw_key not in state.completed_slice_keys:
                state.completed_slice_keys.append(raw_key)
                changed = True
    return changed
