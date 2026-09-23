from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import Base, IngestionRun, Paper
from research_lab.mot_pilot import MOT_PILOT_SOURCE, MotPilotCollector, mot_pilot_slices
from research_lab.mot_taxonomy import MOT_PROBLEMS


def test_mot_pilot_has_separate_recent_and_foundation_lanes() -> None:
    slices = mot_pilot_slices(
        recent_from_year=2017,
        recent_to_year=2026,
        foundation_from_year=1970,
        foundation_to_year=2016,
    )

    assert len(slices) == len(MOT_PROBLEMS) * 2
    first_problem = MOT_PROBLEMS[0].slug
    assert [(problem.slug, lane) for problem, lane, _, _ in slices[:2]] == [
        (first_problem, "recent"),
        (first_problem, "foundation"),
    ]
    assert slices[0][2].year == 2017
    assert slices[1][3].year == 2016


def test_mot_pilot_records_independent_source_and_state(tmp_path, monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    record = SimpleNamespace(
        title="University technology transfer and patent licensing",
        abstract="Technology transfer offices manage licensing and commercialization.",
        source_record_id="W-MOT-PILOT-1",
    )

    class FakeClient:
        def fetch_query_date_range_page(self, *_args, **_kwargs):
            return [record], 1

    class FakeService:
        def __init__(self, session, *_args, **_kwargs):
            self.session = session

        def prepare_for_batch(self):
            return None

        def upsert_unscoped_record(self, incoming, *, retrieved_at=None):
            paper = Paper(
                title=incoming.title,
                abstract=incoming.abstract,
                publication_year=2010,
                primary_source="openalex",
                source_record_id=incoming.source_record_id,
                retrieved_at=retrieved_at or datetime.now(UTC),
                provenance={},
            )
            self.session.add(paper)
            self.session.flush()
            return paper, True

    monkeypatch.setattr("research_lab.mot_pilot.OpenAlexIngestionService", FakeService)
    monkeypatch.setattr("research_lab.mot_pilot.ensure_mot_topics", lambda _session: {})
    monkeypatch.setattr(
        "research_lab.mot_pilot.classify_paper_mot",
        lambda *_args, **_kwargs: (0, 0, []),
    )

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        artifact_root=tmp_path,
    )
    with Session(engine) as session:
        collector = MotPilotCollector(session, settings, client=FakeClient())  # type: ignore[arg-type]
        result = collector.run(
            recent_from_year=2017,
            recent_to_year=2026,
            foundation_from_year=1970,
            foundation_to_year=2016,
            recent_budget_per_problem=1,
            foundation_budget_per_problem=1,
            max_pages_per_slice=1,
            max_slices=1,
        )

        run = session.scalar(select(IngestionRun).where(IngestionRun.source == MOT_PILOT_SOURCE))
        assert run is not None
        assert run.taxonomy_version == "2026-09-23.v1"
        assert result["source"] == MOT_PILOT_SOURCE
        assert collector.state_path == tmp_path / "mot-pilot" / "state.json"
        assert collector.state_path.exists()
        assert not (tmp_path / "corpus-expansion" / "state.json").exists()
