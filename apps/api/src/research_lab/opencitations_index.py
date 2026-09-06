from __future__ import annotations

import csv
import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from research_lab.ingestion.normalization import normalize_doi, normalize_openalex_id
from research_lab.models import Citation, IngestionRun, Paper
from research_lab.taxonomy import TAXONOMY_VERSION

SOURCE = "opencitations_index_v7"


@dataclass(slots=True)
class OpenCitationsIndexStats:
    run_id: str
    status: str
    records_scanned: int
    local_edges: int
    inserted_edges: int
    duplicate_edges: int
    skipped_nonlocal: int
    invalid_rows: int
    csv_members: int


def parse_index_identifier(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    stripped = value.strip()
    if not stripped:
        return {}

    identifiers: dict[str, str] = {}
    for token in stripped.split():
        if ":" not in token:
            continue
        prefix, raw = token.split(":", 1)
        prefix = prefix.lower().strip()
        raw = raw.strip()
        if not raw:
            continue
        if prefix == "omid":
            identifiers["omid"] = raw
        elif prefix == "doi":
            normalized = normalize_doi(raw)
            if normalized:
                identifiers["doi"] = normalized
        elif prefix == "openalex":
            normalized = normalize_openalex_id(raw)
            if normalized:
                identifiers["openalex"] = normalized

    # Older COCI CSV releases used a bare DOI in citing/cited.
    if not identifiers and stripped.lower().startswith("10."):
        normalized = normalize_doi(stripped)
        if normalized:
            identifiers["doi"] = normalized
    return identifiers


class OpenCitationsIndexImporter:
    """Stream one OpenCitations Index ZIP shard and keep local-to-local edges only."""

    def __init__(
        self,
        session: Session,
        *,
        batch_size: int = 5_000,
        state_path: Path | None = None,
    ) -> None:
        self.session = session
        self.batch_size = max(batch_size, 100)
        self.state_path = state_path
        self._omid: dict[str, uuid.UUID] = {}
        self._doi: dict[str, uuid.UUID] = {}
        self._openalex: dict[str, uuid.UUID] = {}

    def run(self, zip_path: Path) -> OpenCitationsIndexStats:
        if not zip_path.is_file():
            raise FileNotFoundError(zip_path)
        self._load_lookup()
        run = IngestionRun(
            source=SOURCE,
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={"zip": str(zip_path), "batch_size": self.batch_size},
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        stats = {
            "records_scanned": 0,
            "local_edges": 0,
            "inserted_edges": 0,
            "duplicate_edges": 0,
            "skipped_nonlocal": 0,
            "invalid_rows": 0,
            "csv_members": 0,
        }
        pending: list[dict[str, object]] = []
        try:
            with zipfile.ZipFile(zip_path) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
                if not members:
                    raise ValueError(f"No CSV members in {zip_path}")
                for member in members:
                    stats["csv_members"] += 1
                    with archive.open(member) as raw:
                        text_stream = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                        reader = csv.DictReader(text_stream)
                        required = {"citing", "cited"}
                        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                            raise ValueError(
                                f"Unexpected OpenCitations Index CSV schema in {zip_path}:{member}"
                            )
                        for row_number, row in enumerate(reader, start=2):
                            stats["records_scanned"] += 1
                            run.fetched_count += 1
                            citing_id = self._resolve(row.get("citing"))
                            cited_id = self._resolve(row.get("cited"))
                            if citing_id is None or cited_id is None:
                                stats["skipped_nonlocal"] += 1
                                run.skipped_count += 1
                                self._heartbeat(run, zip_path, member, row_number, stats)
                                continue
                            if citing_id == cited_id:
                                stats["invalid_rows"] += 1
                                run.error_count += 1
                                self._heartbeat(run, zip_path, member, row_number, stats)
                                continue

                            cited_external = _preferred_external_id(row.get("cited"))
                            if not cited_external:
                                cited_external = f"local:{cited_id}"
                            pending.append(
                                {
                                    "id": uuid.uuid4(),
                                    "citing_paper_id": citing_id,
                                    "cited_paper_id": cited_id,
                                    "cited_external_id": cited_external,
                                    "source": SOURCE,
                                    "is_influential": None,
                                    "context_locator": _context_locator(row),
                                }
                            )
                            stats["local_edges"] += 1
                            run.accepted_count += 1
                            if len(pending) >= self.batch_size:
                                inserted = self._flush(pending)
                                stats["inserted_edges"] += inserted
                                stats["duplicate_edges"] += len(pending) - inserted
                                run.inserted_count += inserted
                                run.skipped_count += len(pending) - inserted
                                pending.clear()
                                self._heartbeat(run, zip_path, member, row_number, stats, force=True)

            if pending:
                inserted = self._flush(pending)
                stats["inserted_edges"] += inserted
                stats["duplicate_edges"] += len(pending) - inserted
                run.inserted_count += inserted
                run.skipped_count += len(pending) - inserted
                pending.clear()

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            run.checkpoint = {
                "updated_at": datetime.now(UTC).isoformat(),
                "zip": str(zip_path),
                **stats,
            }
            self.session.commit()
            self._save_state(zip_path, stats)
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

        return OpenCitationsIndexStats(run_id=str(run.id), status=run.status, **stats)

    def _load_lookup(self) -> None:
        rows = self.session.execute(
            select(Paper.id, Paper.opencitations_omid, Paper.doi, Paper.openalex_id)
        ).all()
        self._omid = {omid: paper_id for paper_id, omid, _, _ in rows if omid}
        self._doi = {
            doi: paper_id
            for paper_id, _, raw_doi, _ in rows
            if (doi := normalize_doi(raw_doi))
        }
        self._openalex = {
            openalex: paper_id
            for paper_id, _, _, raw_openalex in rows
            if (openalex := normalize_openalex_id(raw_openalex))
        }

    def _resolve(self, raw: str | None) -> uuid.UUID | None:
        identifiers = parse_index_identifier(raw)
        for key, lookup in (
            ("omid", self._omid),
            ("doi", self._doi),
            ("openalex", self._openalex),
        ):
            value = identifiers.get(key)
            if value and value in lookup:
                return lookup[value]
        return None

    def _flush(self, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0
        table = Citation.__table__
        dialect = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect == "postgresql":
            statement = pg_insert(table).values(rows).on_conflict_do_nothing(
                constraint="uq_citations_edge"
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(table).values(rows).on_conflict_do_nothing(
                index_elements=["citing_paper_id", "cited_paper_id", "cited_external_id"]
            )
        else:
            inserted = 0
            for row in rows:
                existing = self.session.scalar(
                    select(Citation.id).where(
                        Citation.citing_paper_id == row["citing_paper_id"],
                        Citation.cited_paper_id == row["cited_paper_id"],
                        Citation.cited_external_id == row["cited_external_id"],
                    )
                )
                if existing is None:
                    self.session.add(Citation(**row))
                    inserted += 1
            self.session.commit()
            return inserted
        result = self.session.execute(statement)
        self.session.commit()
        return max(int(result.rowcount or 0), 0)

    def _heartbeat(
        self,
        run: IngestionRun,
        zip_path: Path,
        member: str,
        row_number: int,
        stats: dict[str, int],
        *,
        force: bool = False,
    ) -> None:
        if not force and stats["records_scanned"] % 25_000:
            return
        run.checkpoint = {
            "updated_at": datetime.now(UTC).isoformat(),
            "zip": str(zip_path),
            "member": member,
            "row": row_number,
            "records_scanned": stats["records_scanned"],
            "local_edges": stats["local_edges"],
            "inserted_edges": stats["inserted_edges"],
        }
        self.session.commit()

    def _save_state(self, zip_path: Path, stats: dict[str, int]) -> None:
        if self.state_path is None:
            return
        previous: dict[str, object] = {}
        if self.state_path.exists():
            try:
                loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    previous = loaded
            except (OSError, json.JSONDecodeError):
                pass
        completed = set(previous.get("completed_files") or [])
        completed.add(zip_path.name)
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "completed_files": sorted(completed),
            "last_file": zip_path.name,
            "last_stats": stats,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)


def _preferred_external_id(raw: str | None) -> str | None:
    identifiers = parse_index_identifier(raw)
    for key in ("omid", "doi", "openalex"):
        value = identifiers.get(key)
        if value:
            return f"{key}:{value}"
    return raw.strip()[:255] if raw and raw.strip() else None


def _context_locator(row: dict[str, str]) -> str | None:
    parts = []
    for key in ("oci", "creation", "timespan", "journal_sc", "author_sc"):
        value = (row.get(key) or "").strip()
        if value:
            parts.append(f"{key}={value}")
    text = ";".join(parts)
    return text or None
