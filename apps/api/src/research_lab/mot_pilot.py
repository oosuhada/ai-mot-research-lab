from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.ingestion.openalex import OpenAlexClient
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import IngestionRun, Paper, PaperTopic, Topic
from research_lab.mot_classification import classify_paper_mot, ensure_mot_topics
from research_lab.mot_taxonomy import (
    MOT_PROBLEMS,
    MOT_TAXONOMY_VERSION,
    MotConcept,
    text_matches_mot_problem,
)

MOT_PILOT_SOURCE = "openalex_mot_pilot"


@dataclass(slots=True)
class MotPilotSliceState:
    page: int = 1
    fetched: int = 0
    accepted: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    completed: bool = False


@dataclass(slots=True)
class MotPilotState:
    recent_from_year: int
    recent_to_year: int
    foundation_from_year: int
    foundation_to_year: int
    recent_budget_per_problem: int
    foundation_budget_per_problem: int
    max_pages_per_slice: int
    started_at: str
    updated_at: str
    slices: dict[str, MotPilotSliceState] = field(default_factory=dict)
    last_error: str | None = None


def mot_pilot_slices(
    *,
    recent_from_year: int,
    recent_to_year: int,
    foundation_from_year: int,
    foundation_to_year: int,
) -> list[tuple[MotConcept, str, date, date]]:
    result: list[tuple[MotConcept, str, date, date]] = []
    for problem in MOT_PROBLEMS:
        result.append(
            (
                problem,
                "recent",
                date(recent_from_year, 1, 1),
                date(recent_to_year, 12, 31),
            )
        )
        result.append(
            (
                problem,
                "foundation",
                date(foundation_from_year, 1, 1),
                date(foundation_to_year, 12, 31),
            )
        )
    return result


class MotPilotCollector:
    """Small, resumable MOT collection pilot independent of legacy AI expansion state."""

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
        self.state_path = settings.artifact_root / "mot-pilot" / "state.json"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(
        self,
        *,
        recent_from_year: int = 2017,
        recent_to_year: int = 2026,
        foundation_from_year: int = 1950,
        foundation_to_year: int = 2016,
        recent_budget_per_problem: int = 12,
        foundation_budget_per_problem: int = 4,
        max_pages_per_slice: int = 2,
        max_slices: int = 24,
    ) -> dict[str, Any]:
        if recent_from_year > recent_to_year:
            raise ValueError("recent_from_year must be <= recent_to_year")
        if foundation_from_year > foundation_to_year:
            raise ValueError("foundation_from_year must be <= foundation_to_year")
        if foundation_to_year >= recent_from_year:
            raise ValueError("foundation lane must end before the recent lane begins")

        state = self._load_state(
            recent_from_year=recent_from_year,
            recent_to_year=recent_to_year,
            foundation_from_year=foundation_from_year,
            foundation_to_year=foundation_to_year,
            recent_budget_per_problem=max(recent_budget_per_problem, 1),
            foundation_budget_per_problem=max(foundation_budget_per_problem, 1),
            max_pages_per_slice=max(max_pages_per_slice, 1),
        )
        slices = mot_pilot_slices(
            recent_from_year=state.recent_from_year,
            recent_to_year=state.recent_to_year,
            foundation_from_year=state.foundation_from_year,
            foundation_to_year=state.foundation_to_year,
        )

        run = IngestionRun(
            source=MOT_PILOT_SOURCE,
            status="running",
            taxonomy_version=MOT_TAXONOMY_VERSION,
            query_spec={
                "profile": "mot_broad_pilot_v1",
                "recent_range": [state.recent_from_year, state.recent_to_year],
                "foundation_range": [state.foundation_from_year, state.foundation_to_year],
                "recent_budget_per_problem": state.recent_budget_per_problem,
                "foundation_budget_per_problem": state.foundation_budget_per_problem,
                "max_pages_per_slice": state.max_pages_per_slice,
                "problems": [problem.slug for problem in MOT_PROBLEMS],
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
        topics = ensure_mot_topics(self.session)
        slices_processed = 0
        try:
            for problem, lane, from_date, to_date in slices:
                if slices_processed >= max(max_slices, 1):
                    break
                key = _slice_key(problem.slug, lane)
                slice_state = state.slices.setdefault(key, MotPilotSliceState())
                if slice_state.completed:
                    continue
                budget = (
                    state.recent_budget_per_problem
                    if lane == "recent"
                    else state.foundation_budget_per_problem
                )
                pages_this_run = 0
                while (
                    not slice_state.completed
                    and slice_state.accepted < budget
                    and pages_this_run < state.max_pages_per_slice
                ):
                    records, result_count = self.client.fetch_query_date_range_page(
                        problem.openalex_query or "",
                        from_date=from_date,
                        to_date=to_date,
                        page=slice_state.page,
                        per_page=100,
                    )
                    run.fetched_count += len(records)
                    slice_state.fetched += len(records)
                    retrieved_at = datetime.now(UTC)
                    for record in records:
                        if slice_state.accepted >= budget:
                            break
                        text = f"{record.title}\n{record.abstract or ''}"
                        if not text_matches_mot_problem(text, problem):
                            run.skipped_count += 1
                            slice_state.skipped += 1
                            continue
                        try:
                            with self.session.begin_nested():
                                paper, inserted = service.upsert_unscoped_record(
                                    record,
                                    retrieved_at=retrieved_at,
                                )
                                classify_paper_mot(
                                    self.session,
                                    paper,
                                    topics_by_slug=topics,
                                    assignment_source="mot_pilot_keyword_candidate",
                                )
                        except ValueError as exc:
                            run.error_count += 1
                            run.skipped_count += 1
                            slice_state.skipped += 1
                            run.error_message = f"identity conflict: {exc}"[:1000]
                            continue
                        run.accepted_count += 1
                        slice_state.accepted += 1
                        if inserted:
                            run.inserted_count += 1
                            slice_state.inserted += 1
                        else:
                            run.updated_count += 1
                            slice_state.updated += 1

                    pages_this_run += 1
                    last_page = (
                        not records
                        or len(records) < 100
                        or slice_state.page >= 100
                        or result_count <= slice_state.page * 100
                    )
                    if slice_state.accepted >= budget or last_page:
                        slice_state.completed = True
                    else:
                        slice_state.page += 1
                    state.updated_at = datetime.now(UTC).isoformat()
                    state.last_error = None
                    run.checkpoint = {
                        "problem": problem.slug,
                        "lane": lane,
                        "page": slice_state.page,
                        "accepted": slice_state.accepted,
                        "budget": budget,
                        "updated_at": state.updated_at,
                    }
                    self.session.commit()
                    self._save_state(state)
                slices_processed += 1

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
            return self.status(state=state) | {"run_id": str(run.id), "status": "completed"}
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
            return self.status(state=state) | {"run_id": str(run.id), "status": "paused"}
        finally:
            self.close()

    def status(self, *, state: MotPilotState | None = None) -> dict[str, Any]:
        current = state or self._read_state_for_status()
        coverage = self.session.execute(
            select(Topic.slug, func.count(PaperTopic.paper_id))
            .outerjoin(PaperTopic, PaperTopic.topic_id == Topic.id)
            .where(Topic.kind == "mot_problem")
            .group_by(Topic.slug)
            .order_by(Topic.slug)
        ).all()
        return {
            "taxonomy_version": MOT_TAXONOMY_VERSION,
            "source": MOT_PILOT_SOURCE,
            "corpus_count": int(self.session.scalar(select(func.count()).select_from(Paper)) or 0),
            "problem_coverage": {slug: int(count) for slug, count in coverage},
            "slices": {key: asdict(value) for key, value in sorted(current.slices.items())},
            "last_error": current.last_error,
            "updated_at": current.updated_at,
            "state_path": str(self.state_path),
        }

    def _read_state_for_status(self) -> MotPilotState:
        if not self.state_path.exists():
            return self._load_state(
                recent_from_year=2017,
                recent_to_year=2026,
                foundation_from_year=1950,
                foundation_to_year=2016,
                recent_budget_per_problem=12,
                foundation_budget_per_problem=4,
                max_pages_per_slice=2,
            )
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        raw["slices"] = {
            key: MotPilotSliceState(**value) for key, value in (raw.get("slices") or {}).items()
        }
        return MotPilotState(**raw)

    def _load_state(
        self,
        *,
        recent_from_year: int,
        recent_to_year: int,
        foundation_from_year: int,
        foundation_to_year: int,
        recent_budget_per_problem: int,
        foundation_budget_per_problem: int,
        max_pages_per_slice: int,
    ) -> MotPilotState:
        expected = (
            recent_from_year,
            recent_to_year,
            foundation_from_year,
            foundation_to_year,
        )
        if self.state_path.exists():
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            raw["slices"] = {
                key: MotPilotSliceState(**value) for key, value in (raw.get("slices") or {}).items()
            }
            state = MotPilotState(**raw)
            actual = (
                state.recent_from_year,
                state.recent_to_year,
                state.foundation_from_year,
                state.foundation_to_year,
            )
            if actual != expected:
                raise ValueError("Existing MOT pilot date ranges differ from requested ranges")
            return state
        now = datetime.now(UTC).isoformat()
        state = MotPilotState(
            recent_from_year=recent_from_year,
            recent_to_year=recent_to_year,
            foundation_from_year=foundation_from_year,
            foundation_to_year=foundation_to_year,
            recent_budget_per_problem=recent_budget_per_problem,
            foundation_budget_per_problem=foundation_budget_per_problem,
            max_pages_per_slice=max_pages_per_slice,
            started_at=now,
            updated_at=now,
        )
        self._save_state(state)
        return state

    def _save_state(self, state: MotPilotState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(asdict(state), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _slice_key(problem_slug: str, lane: str) -> str:
    return f"{problem_slug}:{lane}"
