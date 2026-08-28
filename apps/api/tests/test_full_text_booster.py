from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.full_text_booster import (
    CommandOutput,
    FullTextBoosterWorker,
    LibgenCliProvider,
    ProviderArtifact,
    ProviderFailure,
    SciHubCliProvider,
)
from research_lab.models import FullTextQueueItem, FullTextSourceAttempt, Paper, PaperContentProfile
from research_lab.pdf_pipeline import PdfEvidenceService


class FakeProvider:
    def __init__(self, name: str, result: ProviderArtifact | ProviderFailure) -> None:
        self.name = name
        self.result = result
        self.calls = 0

    def fetch(self, _paper: Paper, *, max_pdf_bytes: int) -> ProviderArtifact:
        self.calls += 1
        if isinstance(self.result, ProviderFailure):
            raise self.result
        assert len(self.result.pdf_bytes) <= max_pdf_bytes
        return self.result


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperContentProfile.__table__,
        FullTextQueueItem.__table__,
        FullTextSourceAttempt.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _eligible_item(session: Session) -> tuple[Paper, PaperContentProfile, FullTextQueueItem]:
    paper = Paper(
        title="Open paper",
        doi="10.1234/open-paper",
        is_oa=True,
        primary_source="openalex",
        source_record_id="W-BOOST",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )
    session.add(paper)
    session.flush()
    profile = PaperContentProfile(
        paper_id=paper.id,
        full_text_status="queued",
        full_text_access="open_access",
        rights_status="open_access",
    )
    item = FullTextQueueItem(
        paper_id=paper.id,
        priority=90,
        status="pending",
        rights_status="open_access",
        attempts=1,
        failure_kind="source_exhausted",
        next_attempt_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add_all([profile, item])
    session.commit()
    return paper, profile, item


def test_booster_claims_exhausted_oa_item_and_completes(monkeypatch) -> None:
    session = _session()
    paper, profile, item = _eligible_item(session)
    provider = FakeProvider(
        "scihub_cli",
        ProviderArtifact("scihub_cli", "cli://scihub-cli/test", b"%PDF-1.7\nvalid"),
    )
    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=2, extraction_status="extracted"),
    )

    result = FullTextBoosterWorker(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        providers=(provider,),
        worker_id="test-booster",
    ).run(max_items=1)

    session.refresh(item)
    session.refresh(profile)
    assert result["completed"] == 1
    assert item.status == "completed"
    assert item.worker_id is None
    assert profile.full_text_status == "available"
    attempt = session.query(FullTextSourceAttempt).one()
    assert attempt.status == "completed"
    assert attempt.source_kind == "scihub_cli"
    assert provider.calls == 1
    session.close()


def test_booster_uses_libgen_only_after_scihub_failure(monkeypatch) -> None:
    session = _session()
    _paper, _profile, item = _eligible_item(session)
    scihub = FakeProvider("scihub_cli", ProviderFailure("no_result", "not found"))
    libgen = FakeProvider(
        "libgen_cli",
        ProviderArtifact("libgen_cli", "https://example.test/open.pdf", b"%PDF-1.7\nfallback"),
    )
    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=1, extraction_status="extracted"),
    )

    result = FullTextBoosterWorker(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        providers=(scihub, libgen),
    ).run(max_items=1)

    session.refresh(item)
    attempts = session.query(FullTextSourceAttempt).order_by(FullTextSourceAttempt.started_at).all()
    assert result["completed"] == 1
    assert [attempt.status for attempt in attempts] == ["failed", "completed"]
    assert scihub.calls == 1
    assert libgen.calls == 1
    session.close()


def test_booster_leaves_unknown_rights_item_unclaimed() -> None:
    session = _session()
    _paper, _profile, item = _eligible_item(session)
    item.rights_status = "unknown"
    session.commit()
    provider = FakeProvider("scihub_cli", ProviderFailure("no_result", "not found"))

    result = FullTextBoosterWorker(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        providers=(provider,),
    ).run(max_items=1)

    assert result["selected"] == 0
    assert provider.calls == 0
    session.close()


def test_booster_requires_one_completed_regular_attempt() -> None:
    session = _session()
    _paper, _profile, item = _eligible_item(session)
    item.attempts = 0
    session.commit()
    provider = FakeProvider("scihub_cli", ProviderFailure("no_result", "not found"))

    result = FullTextBoosterWorker(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        providers=(provider,),
    ).run(max_items=1)

    assert result["selected"] == 0
    assert provider.calls == 0
    session.close()


def test_direct_worker_claims_fresh_open_access_item_without_attempt_filter(monkeypatch) -> None:
    session = _session()
    _paper, _profile, item = _eligible_item(session)
    item.attempts = 0
    item.failure_kind = None
    session.commit()
    provider = FakeProvider(
        "scihub_cli",
        ProviderArtifact("scihub_cli", "cli://scihub-cli/direct", b"%PDF-1.7\nvalid"),
    )
    monkeypatch.setattr(
        PdfEvidenceService,
        "ingest",
        lambda *_args, **_kwargs: SimpleNamespace(chunk_count=1, extraction_status="extracted"),
    )

    result = FullTextBoosterWorker(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        providers=(provider,),
    ).run(max_items=1, direct=True)

    session.refresh(item)
    assert result["mode"] == "direct"
    assert result["completed"] == 1
    assert item.attempts == 1
    assert item.status == "completed"
    assert provider.calls == 1
    session.close()


def test_booster_records_failures_and_cooldown() -> None:
    session = _session()
    _paper, profile, item = _eligible_item(session)
    providers = (
        FakeProvider("scihub_cli", ProviderFailure("timeout", "slow")),
        FakeProvider("libgen_cli", ProviderFailure("no_result", "missing")),
    )

    result = FullTextBoosterWorker(
        session,
        Settings(database_url="sqlite+pysqlite:///:memory:"),
        providers=providers,
    ).run(max_items=1, cooldown_hours=12)

    session.refresh(item)
    session.refresh(profile)
    assert result["failed"] == 1
    assert item.status == "pending"
    assert item.failure_kind == "source_exhausted"
    assert item.next_attempt_at is not None
    assert item.next_attempt_at.replace(tzinfo=UTC) > datetime.now(UTC) + timedelta(hours=11)
    assert profile.full_text_status == "queued"
    assert session.query(FullTextSourceAttempt).count() == 2
    assert item.reason_factors["booster"]["failure_count"] == 1
    session.close()


def test_scihub_cli_uses_input_file_and_validates_pdf() -> None:
    class Runner:
        def __init__(self) -> None:
            self.args: list[str] = []

        def run(self, args: list[str], *, cwd: Path, timeout_seconds: float) -> CommandOutput:
            self.args = args
            output_dir = Path(args[args.index("--output") + 1])
            (output_dir / "paper.pdf").write_bytes(b"%PDF-1.7\ncli")
            assert Path(args[-1]).read_text(encoding="utf-8") == "10.1234/open-paper\n"
            assert timeout_seconds > 0
            return CommandOutput(stdout="", stderr="")

    runner = Runner()
    paper = SimpleNamespace(doi="10.1234/open-paper", arxiv_id=None)
    provider = SciHubCliProvider(executable="true", runner=runner)
    artifact = provider.fetch(paper, max_pdf_bytes=1024)

    assert "--output" in runner.args
    assert "--parallel" in runner.args
    assert artifact.pdf_bytes.startswith(b"%PDF")


def test_libgen_cli_parses_link_and_rejects_non_pdf() -> None:
    class Runner:
        def run(self, args: list[str], *, cwd: Path, timeout_seconds: float) -> CommandOutput:
            assert args[1:3] == ["--only-links", "1"]
            assert timeout_seconds > 0
            return CommandOutput(stdout="https://example.test/result\n", stderr="")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>blocked</html>", request=request)

    provider = LibgenCliProvider(
        executable="true",
        runner=Runner(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    paper = SimpleNamespace(doi="10.1234/open-paper", title="Open paper")

    try:
        provider.fetch(paper, max_pdf_bytes=1024)
    except ProviderFailure as exc:
        assert exc.failure_kind == "non_pdf_response"
    else:
        raise AssertionError("Expected non-PDF output to be rejected")
