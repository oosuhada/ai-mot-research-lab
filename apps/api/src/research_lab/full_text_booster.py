from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.models import FullTextQueueItem, FullTextSourceAttempt, Paper, PaperContentProfile
from research_lab.pdf_pipeline import PdfEvidenceService


@dataclass(frozen=True)
class ProviderArtifact:
    source_kind: str
    source_url: str
    pdf_bytes: bytes


class ProviderFailure(RuntimeError):
    def __init__(self, failure_kind: str, message: str) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind


class PdfProvider(Protocol):
    name: str

    def fetch(self, paper: Paper, *, max_pdf_bytes: int) -> ProviderArtifact: ...


@dataclass(frozen=True)
class CommandOutput:
    stdout: str
    stderr: str


class SubprocessRunner:
    """Run one CLI in its own process group so timeout cleanup is deterministic."""

    def run(self, args: list[str], *, cwd: Path, timeout_seconds: float) -> CommandOutput:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            raise ProviderFailure("timeout", f"Provider exceeded {timeout_seconds:g}s timeout") from exc
        if process.returncode != 0:
            detail = (stderr or stdout or f"exit code {process.returncode}").strip()[-500:]
            raise ProviderFailure("provider_error", detail)
        return CommandOutput(stdout=stdout, stderr=stderr)


class SciHubCliProvider:
    """OA-first sci-hub-cli 0.5.x adapter using its documented input-file interface."""

    name = "scihub_cli"

    def __init__(
        self,
        *,
        executable: str = "scihub-cli",
        timeout_seconds: float = 90,
        runner: SubprocessRunner | None = None,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.runner = runner or SubprocessRunner()

    def fetch(self, paper: Paper, *, max_pdf_bytes: int) -> ProviderArtifact:
        identifier = paper.doi or (f"arxiv:{paper.arxiv_id}" if paper.arxiv_id else None)
        if not identifier:
            raise ProviderFailure("no_identifier", "scihub-cli requires a DOI or arXiv identifier")
        executable = shutil.which(self.executable)
        if executable is None:
            raise ProviderFailure("cli_unavailable", f"Executable not found: {self.executable}")

        with tempfile.TemporaryDirectory(prefix="research-lab-scihub-") as raw_temp:
            temp_dir = Path(raw_temp)
            input_path = temp_dir / "identifiers.txt"
            output_dir = temp_dir / "downloads"
            output_dir.mkdir()
            input_path.write_text(f"{identifier}\n", encoding="utf-8")
            self.runner.run(
                [
                    executable,
                    "--output",
                    str(output_dir),
                    "--parallel",
                    "1",
                    "--timeout",
                    str(max(1, int(self.timeout_seconds))),
                    "--retries",
                    "1",
                    str(input_path),
                ],
                cwd=temp_dir,
                timeout_seconds=self.timeout_seconds + 10,
            )
            return _first_valid_pdf(
                output_dir,
                source_kind=self.name,
                source_url=f"cli://scihub-cli/{quote(identifier, safe='')}",
                max_pdf_bytes=max_pdf_bytes,
            )


class LibgenCliProvider:
    """Best-effort libgen-downloader 0.0.104 fallback through its libgen-cli entrypoint."""

    name = "libgen_cli"
    _url_pattern = re.compile(r"https?://[^\s<>'\"]+")

    def __init__(
        self,
        *,
        executable: str = "libgen-cli",
        timeout_seconds: float = 45,
        runner: SubprocessRunner | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.runner = runner or SubprocessRunner()
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)

    def fetch(self, paper: Paper, *, max_pdf_bytes: int) -> ProviderArtifact:
        query = paper.doi or paper.title
        if len(query.strip()) < 3:
            raise ProviderFailure("no_identifier", "libgen-cli requires a searchable DOI or title")
        executable = shutil.which(self.executable)
        if executable is None:
            raise ProviderFailure("cli_unavailable", f"Executable not found: {self.executable}")

        with tempfile.TemporaryDirectory(prefix="research-lab-libgen-") as raw_temp:
            output = self.runner.run(
                [executable, "--only-links", "1", query],
                cwd=Path(raw_temp),
                timeout_seconds=self.timeout_seconds,
            )
        urls = [match.rstrip(".,);]") for match in self._url_pattern.findall(output.stdout)]
        if not urls:
            raise ProviderFailure("no_result", "libgen-cli returned no download link")
        source_url = urls[0]
        try:
            response = self.client.get(source_url)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderFailure("timeout", "LibGen download timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderFailure(f"http_{exc.response.status_code}", "LibGen download failed") from exc
        except httpx.RequestError as exc:
            raise ProviderFailure("network_error", "LibGen download failed") from exc
        return _validate_pdf_bytes(
            response.content,
            source_kind=self.name,
            source_url=source_url,
            max_pdf_bytes=max_pdf_bytes,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()


class FullTextBoosterWorker:
    """Run bounded, leased fallback enrichment after rights-safe OA sources are exhausted."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        providers: tuple[PdfProvider, ...] | None = None,
        worker_id: str | None = None,
        provider_timeout_seconds: float = 90,
        enable_libgen_fallback: bool = True,
    ) -> None:
        self.session = session
        self.settings = settings
        self.worker_id = worker_id or f"booster:{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        if providers is None:
            configured: list[PdfProvider] = [
                SciHubCliProvider(
                    executable=settings.scihub_cli_executable,
                    timeout_seconds=provider_timeout_seconds,
                )
            ]
            if enable_libgen_fallback:
                configured.append(
                    LibgenCliProvider(
                        executable=settings.libgen_cli_executable,
                        timeout_seconds=min(provider_timeout_seconds, 60),
                    )
                )
            providers = tuple(configured)
        self.providers = providers

    def run(
        self,
        *,
        max_items: int = 3,
        max_pdf_bytes: int = 30_000_000,
        lease_minutes: int = 20,
        min_attempts: int = 1,
        cooldown_hours: int = 24,
        direct: bool = False,
    ) -> dict[str, object]:
        selected = completed = failed = 0
        for _ in range(max(max_items, 1)):
            item = self._claim_next_item(
                lease_minutes=max(lease_minutes, 1),
                min_attempts=max(min_attempts, 1),
                direct=direct,
            )
            if item is None:
                break
            selected += 1
            paper = self.session.get(Paper, item.paper_id)
            if paper is None:
                self._mark_exhausted(item, "missing_paper", "Queue item has no paper", cooldown_hours)
                failed += 1
                continue
            if self._process_item(item, paper, max_pdf_bytes=max_pdf_bytes, cooldown_hours=cooldown_hours):
                completed += 1
            else:
                failed += 1
        for provider in self.providers:
            close = getattr(provider, "close", None)
            if callable(close):
                close()
        return {
            "worker_id": self.worker_id,
            "mode": "direct" if direct else "booster",
            "selected": selected,
            "completed": completed,
            "failed": failed,
        }

    def _claim_next_item(
        self,
        *,
        lease_minutes: int,
        min_attempts: int,
        direct: bool,
    ) -> FullTextQueueItem | None:
        now = datetime.now(UTC)
        eligibility = [
            FullTextQueueItem.status == "pending",
            FullTextQueueItem.rights_status == "open_access",
            or_(FullTextQueueItem.next_attempt_at.is_(None), FullTextQueueItem.next_attempt_at <= now),
        ]
        if not direct:
            eligibility.extend(
                (
                    FullTextQueueItem.failure_kind == "source_exhausted",
                    FullTextQueueItem.attempts >= min_attempts,
                )
            )
        item = self.session.scalar(
            select(FullTextQueueItem)
            .where(*eligibility)
            .order_by(FullTextQueueItem.priority.desc(), FullTextQueueItem.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if item is None:
            return None
        item.status = "processing"
        item.attempts += 1
        item.worker_id = self.worker_id
        item.claimed_at = now
        item.lease_expires_at = now + timedelta(minutes=lease_minutes)
        self.session.commit()
        return item

    def _process_item(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        *,
        max_pdf_bytes: int,
        cooldown_hours: int,
    ) -> bool:
        last_failure = ProviderFailure("no_result", "No fallback provider returned a PDF")
        for provider in self.providers:
            started_at = datetime.now(UTC)
            source_url = f"cli://{provider.name}/{quote(paper.doi or paper.title, safe='')}"
            try:
                artifact = provider.fetch(paper, max_pdf_bytes=max_pdf_bytes)
                source_url = artifact.source_url
                result = PdfEvidenceService(self.session, self.settings).ingest(
                    paper.id,
                    f"{paper.openalex_id or paper.id}.pdf",
                    artifact.pdf_bytes,
                    source=artifact.source_kind,
                    source_url=artifact.source_url,
                    license_label=paper.license or "Open-access source; redistribution not granted",
                    redistributable=False,
                )
                if result.chunk_count <= 0 or result.extraction_status != "extracted":
                    raise ProviderFailure("extraction_failure", "PDF contained no extractable text")
                self._record_attempt(
                    item,
                    paper,
                    source_kind=artifact.source_kind,
                    source_url=artifact.source_url,
                    started_at=started_at,
                    status="completed",
                )
                self._mark_completed(item, paper, artifact)
                return True
            except ProviderFailure as exc:
                last_failure = exc
            except Exception as exc:
                self.session.rollback()
                last_failure = ProviderFailure("extraction_failure", f"{type(exc).__name__}: {exc}")
            self._record_attempt(
                item,
                paper,
                source_kind=provider.name,
                source_url=source_url,
                started_at=started_at,
                status="failed",
                failure_kind=last_failure.failure_kind,
                error=last_failure,
            )
        self._mark_exhausted(item, last_failure.failure_kind, str(last_failure), cooldown_hours)
        return False

    def _record_attempt(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        *,
        source_kind: str,
        source_url: str,
        started_at: datetime,
        status: str,
        failure_kind: str | None = None,
        error: Exception | None = None,
    ) -> None:
        parsed = urlparse(source_url)
        self.session.add(
            FullTextSourceAttempt(
                queue_item_id=item.id,
                paper_id=paper.id,
                source_url=source_url,
                domain=parsed.hostname or source_kind,
                publisher=paper.publisher,
                source_kind=source_kind,
                status=status,
                failure_kind=failure_kind,
                http_status=None,
                error_message=(f"{type(error).__name__}: {error}"[:1000] if error else None),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        )
        self.session.commit()

    def _mark_completed(self, item: FullTextQueueItem, paper: Paper, artifact: ProviderArtifact) -> None:
        item.status = "completed"
        item.last_error = None
        item.failure_kind = None
        item.next_attempt_at = None
        self._clear_lease(item)
        factors = dict(item.reason_factors or {})
        factors["booster"] = {
            "completed_at": datetime.now(UTC).isoformat(),
            "source_kind": artifact.source_kind,
        }
        item.reason_factors = factors
        profile = self.session.get(PaperContentProfile, paper.id)
        if profile is not None:
            profile.full_text_status = "available"
            profile.full_text_access = "open_access"
            profile.full_text_updated_at = datetime.now(UTC)
        self.session.commit()

    def _mark_exhausted(
        self,
        item: FullTextQueueItem,
        failure_kind: str,
        error: str,
        cooldown_hours: int,
    ) -> None:
        item.status = "pending"
        item.failure_kind = "source_exhausted"
        item.last_error = f"booster_{failure_kind}: {error}"[:1000]
        item.next_attempt_at = datetime.now(UTC) + timedelta(hours=max(cooldown_hours, 1))
        self._clear_lease(item)
        factors = dict(item.reason_factors or {})
        previous_raw = factors.get("booster")
        previous = previous_raw if isinstance(previous_raw, dict) else {}
        factors["booster"] = {
            "last_failed_at": datetime.now(UTC).isoformat(),
            "failure_kind": failure_kind,
            "failure_count": int(previous.get("failure_count") or 0) + 1,
        }
        item.reason_factors = factors
        profile = self.session.get(PaperContentProfile, item.paper_id)
        if profile is not None:
            profile.full_text_status = "queued"
        self.session.commit()

    @staticmethod
    def _clear_lease(item: FullTextQueueItem) -> None:
        item.worker_id = None
        item.claimed_at = None
        item.lease_expires_at = None


def _first_valid_pdf(
    output_dir: Path,
    *,
    source_kind: str,
    source_url: str,
    max_pdf_bytes: int,
) -> ProviderArtifact:
    failures: list[ProviderFailure] = []
    for path in sorted(output_dir.rglob("*.pdf")):
        try:
            return _validate_pdf_bytes(
                path.read_bytes(),
                source_kind=source_kind,
                source_url=source_url,
                max_pdf_bytes=max_pdf_bytes,
            )
        except ProviderFailure as exc:
            failures.append(exc)
    if failures:
        raise failures[0]
    raise ProviderFailure("no_result", "Provider produced no PDF")


def _validate_pdf_bytes(
    data: bytes,
    *,
    source_kind: str,
    source_url: str,
    max_pdf_bytes: int,
) -> ProviderArtifact:
    if len(data) > max_pdf_bytes:
        raise ProviderFailure("pdf_too_large", f"PDF exceeds {max_pdf_bytes} byte limit")
    if not data.startswith(b"%PDF"):
        raise ProviderFailure("non_pdf_response", "Provider output is not a PDF")
    return ProviderArtifact(source_kind=source_kind, source_url=source_url, pdf_bytes=data)
