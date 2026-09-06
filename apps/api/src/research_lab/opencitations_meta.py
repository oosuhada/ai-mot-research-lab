from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.ingestion.normalization import normalize_doi, normalize_openalex_id
from research_lab.models import IngestionRun, Paper
from research_lab.taxonomy import AI_TERMS, RESEARCH_AXES, TAXONOMY_VERSION

SOURCE = "opencitations_meta_dump"


@dataclass(slots=True)
class OpenCitationsMetaRecord:
    omid: str | None
    doi: str | None
    openalex_id: str | None
    title: str | None
    publication_date: date | None
    publication_year: int | None
    work_type: str | None
    venue: str | None
    publisher: str | None
    authors: str | None
    identifiers: str


@dataclass(slots=True)
class OpenCitationsImportResult:
    run_id: str
    status: str
    scanned: int
    matched_existing: int
    inserted: int
    updated: int
    skipped_irrelevant: int
    skipped_missing_identity: int
    identifier_conflicts: int
    files_completed: int


_AGENTIC_AI_TERMS = (
    "agentic ai",
    "ai agent",
    "ai agents",
    "llm agent",
    "llm agents",
    "multi agent",
    "multi-agent",
)
_CONTEXT_TERMS = tuple(
    sorted(
        {
            term.lower()
            for axis in RESEARCH_AXES
            for term in axis.context_terms
        }
        | {
            "technology management",
            "innovation management",
            "technology strategy",
            "management",
            "innovation",
            "organization",
            "organisational",
            "organizational",
            "enterprise",
            "business",
            "manufacturing",
            "operations",
            "governance",
            "adoption",
            "productivity",
            "workplace",
            "workflow",
            "capability",
            "capabilities",
            "strategy",
        },
        key=lambda value: (-len(value), value),
    )
)


def parse_opencitations_meta_row(row: dict[str, str]) -> OpenCitationsMetaRecord:
    identifiers = (row.get("id") or "").strip()
    parsed_ids = _parse_identifiers(identifiers)
    publication_date = _parse_date((row.get("pub_date") or "").strip())
    return OpenCitationsMetaRecord(
        omid=parsed_ids.get("omid"),
        doi=normalize_doi(parsed_ids.get("doi")),
        openalex_id=normalize_openalex_id(parsed_ids.get("openalex")),
        title=_clean(row.get("title")),
        publication_date=publication_date,
        publication_year=publication_date.year if publication_date else None,
        work_type=_clean(row.get("type")),
        venue=_clean(row.get("venue")),
        publisher=_strip_agent_identifiers(_clean(row.get("publisher"))),
        authors=_clean(row.get("author")),
        identifiers=identifiers,
    )


def is_ai_mot_title(title: str | None) -> bool:
    if not title:
        return False
    normalized = unicodedata.normalize("NFKC", title).lower()
    normalized = re.sub(r"[_–—/:]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    ai_hit = any(term in normalized for term in AI_TERMS + _AGENTIC_AI_TERMS)
    if not ai_hit and re.search(r"\bai\b", normalized):
        ai_hit = True
    if not ai_hit:
        return False
    return any(term in normalized for term in _CONTEXT_TERMS)


class OpenCitationsMetaImporter:
    """Stream OpenCitations Meta CSV shards into the canonical paper corpus."""

    def __init__(
        self,
        session: Session,
        *,
        from_year: int = 2017,
        to_year: int = 2027,
        max_new: int = 100_000,
        commit_every: int = 2_000,
        state_path: Path | None = None,
    ) -> None:
        self.session = session
        self.from_year = from_year
        self.to_year = to_year
        self.max_new = max_new
        self.commit_every = max(commit_every, 100)
        self.state_path = state_path
        self._doi: dict[str, Paper] = {}
        self._openalex: dict[str, Paper] = {}
        self._omid: dict[str, Paper] = {}

    def run(self, input_path: Path) -> OpenCitationsImportResult:
        files = _discover_csv_files(input_path)
        if not files:
            raise ValueError(f"No CSV files found under {input_path}")

        self._load_lookup()
        state = self._load_state()
        completed_files = set(state.get("completed_files") or [])
        resume_file = str(state.get("current_file") or "")
        resume_row = int(state.get("current_row") or 0)
        run = IngestionRun(
            source=SOURCE,
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={
                "input": str(input_path),
                "from_year": self.from_year,
                "to_year": self.to_year,
                "max_new": self.max_new,
                "files": len(files),
            },
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        stats = {
            "scanned": 0,
            "matched_existing": 0,
            "inserted": 0,
            "updated": 0,
            "skipped_irrelevant": 0,
            "skipped_missing_identity": 0,
            "identifier_conflicts": 0,
            "files_completed": 0,
        }
        try:
            for csv_path in files:
                key = str(csv_path.resolve())
                if key in completed_files:
                    stats["files_completed"] += 1
                    continue
                self._process_file(
                    csv_path,
                    run,
                    stats,
                    start_after_row=(resume_row if key == resume_file else 0),
                )
                completed_files.add(key)
                stats["files_completed"] += 1
                self._save_state(completed_files, csv_path, stats)
                if self.max_new > 0 and stats["inserted"] >= self.max_new:
                    break

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            run.checkpoint = {
                "updated_at": datetime.now(UTC).isoformat(),
                "files_completed": stats["files_completed"],
                "scanned": stats["scanned"],
                "inserted": stats["inserted"],
            }
            self.session.commit()
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

        return OpenCitationsImportResult(run_id=str(run.id), status=run.status, **stats)

    def _process_file(
        self,
        csv_path: Path,
        run: IngestionRun,
        stats: dict[str, int],
        *,
        start_after_row: int = 0,
    ) -> None:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            expected = {"id", "title", "pub_date", "type"}
            if reader.fieldnames is None or not expected.issubset(set(reader.fieldnames)):
                raise ValueError(f"Unexpected OpenCitations Meta CSV schema in {csv_path}")
            for row_number, row in enumerate(reader, start=2):
                if row_number <= start_after_row:
                    continue
                stats["scanned"] += 1
                run.fetched_count += 1
                record = parse_opencitations_meta_row(row)
                paper, conflict = self._match(record)
                if conflict:
                    stats["identifier_conflicts"] += 1
                    run.error_count += 1
                    self._maybe_commit(run, csv_path, row_number, stats)
                    continue

                if paper is not None:
                    stats["matched_existing"] += 1
                    run.accepted_count += 1
                    if self._enrich_existing(paper, record):
                        stats["updated"] += 1
                        run.updated_count += 1
                    else:
                        run.skipped_count += 1
                else:
                    if self.max_new > 0 and stats["inserted"] >= self.max_new:
                        break
                    if record.publication_year is None or not (
                        self.from_year <= record.publication_year <= self.to_year
                    ) or not is_ai_mot_title(record.title):
                        stats["skipped_irrelevant"] += 1
                        run.skipped_count += 1
                        self._maybe_commit(run, csv_path, row_number, stats)
                        continue
                    if not record.omid and not record.doi and not record.openalex_id:
                        stats["skipped_missing_identity"] += 1
                        run.skipped_count += 1
                        self._maybe_commit(run, csv_path, row_number, stats)
                        continue
                    self._insert_new(record)
                    stats["inserted"] += 1
                    run.inserted_count += 1
                    run.accepted_count += 1

                self._maybe_commit(run, csv_path, row_number, stats)
        self.session.commit()

    def _load_lookup(self) -> None:
        papers = self.session.scalars(select(Paper)).all()
        self._doi = {doi: paper for paper in papers if (doi := normalize_doi(paper.doi))}
        self._openalex = {
            value: paper
            for paper in papers
            if (value := normalize_openalex_id(paper.openalex_id))
        }
        self._omid = {
            paper.opencitations_omid: paper
            for paper in papers
            if paper.opencitations_omid
        }

    def _match(self, record: OpenCitationsMetaRecord) -> tuple[Paper | None, bool]:
        matches: dict[str, Paper] = {}
        if record.omid and record.omid in self._omid:
            matches[str(self._omid[record.omid].id)] = self._omid[record.omid]
        if record.doi and record.doi in self._doi:
            matches[str(self._doi[record.doi].id)] = self._doi[record.doi]
        if record.openalex_id and record.openalex_id in self._openalex:
            matches[str(self._openalex[record.openalex_id].id)] = self._openalex[record.openalex_id]
        if len(matches) > 1:
            return None, True
        return (next(iter(matches.values())) if matches else None), False

    def _enrich_existing(self, paper: Paper, record: OpenCitationsMetaRecord) -> bool:
        changed = False
        if record.omid and not paper.opencitations_omid and record.omid not in self._omid:
            paper.opencitations_omid = record.omid
            self._omid[record.omid] = paper
            changed = True
        if record.doi and not paper.doi and record.doi not in self._doi:
            paper.doi = record.doi
            self._doi[record.doi] = paper
            changed = True
        if record.openalex_id and not paper.openalex_id and record.openalex_id not in self._openalex:
            paper.openalex_id = record.openalex_id
            self._openalex[record.openalex_id] = paper
            changed = True
        for field, value in (
            ("publication_date", record.publication_date),
            ("publication_year", record.publication_year),
            ("work_type", record.work_type),
            ("publisher", record.publisher),
        ):
            if value is not None and getattr(paper, field) in (None, ""):
                setattr(paper, field, value)
                changed = True

        provenance = dict(paper.provenance or {})
        snapshot = self._provenance(record)
        if provenance.get("opencitations_meta") != snapshot:
            provenance["opencitations_meta"] = snapshot
            paper.provenance = provenance
            changed = True
        if changed:
            paper.retrieved_at = datetime.now(UTC)
        return changed

    def _insert_new(self, record: OpenCitationsMetaRecord) -> Paper:
        source_record_id = record.omid or record.doi or record.openalex_id
        assert source_record_id is not None
        paper = Paper(
            doi=record.doi,
            openalex_id=record.openalex_id,
            opencitations_omid=record.omid,
            title=record.title or "Untitled work",
            publication_date=record.publication_date,
            publication_year=record.publication_year,
            work_type=_normalize_work_type(record.work_type),
            publisher=record.publisher,
            is_oa=False,
            primary_url=(f"https://doi.org/{record.doi}" if record.doi else None),
            retraction_status="none",
            correction_status="none",
            primary_source=SOURCE,
            source_record_id=source_record_id,
            retrieved_at=datetime.now(UTC),
            provenance={"opencitations_meta": self._provenance(record)},
        )
        self.session.add(paper)
        self.session.flush()
        if record.doi:
            self._doi[record.doi] = paper
        if record.openalex_id:
            self._openalex[record.openalex_id] = paper
        if record.omid:
            self._omid[record.omid] = paper
        return paper

    @staticmethod
    def _provenance(record: OpenCitationsMetaRecord) -> dict[str, object]:
        return {
            "omid": record.omid,
            "identifiers": record.identifiers,
            "venue": record.venue,
            "authors": record.authors,
            "source": "OpenCitations Meta June 2026 CSV dump",
        }

    def _maybe_commit(
        self,
        run: IngestionRun,
        csv_path: Path,
        row_number: int,
        stats: dict[str, int],
    ) -> None:
        if stats["scanned"] % self.commit_every:
            return
        run.checkpoint = {
            "updated_at": datetime.now(UTC).isoformat(),
            "file": str(csv_path),
            "row": row_number,
            "scanned": stats["scanned"],
            "inserted": stats["inserted"],
            "matched_existing": stats["matched_existing"],
        }
        self.session.commit()
        self._save_state(set(), csv_path, stats, current_row=row_number)

    def _load_state(self) -> dict[str, object]:
        if self.state_path is None or not self.state_path.exists():
            return {}
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _save_state(
        self,
        completed_files: set[str],
        current_file: Path,
        stats: dict[str, int],
        *,
        current_row: int | None = None,
    ) -> None:
        if self.state_path is None:
            return
        previous = self._load_state()
        merged_completed = set(previous.get("completed_files") or []) | completed_files
        payload = {
            "updated_at": datetime.now(UTC).isoformat(),
            "current_file": str(current_file.resolve()),
            "current_row": current_row,
            "completed_files": sorted(merged_completed),
            "stats": stats,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)


def _parse_identifiers(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for token in value.split():
        if ":" not in token:
            continue
        prefix, identifier = token.split(":", 1)
        prefix = prefix.strip().lower()
        identifier = identifier.strip()
        if prefix in {"doi", "openalex", "omid"} and identifier:
            parsed[prefix] = identifier
    return parsed


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    for pattern in (r"^(\d{4})-(\d{2})-(\d{2})$", r"^(\d{4})-(\d{2})$", r"^(\d{4})$"):
        match = re.match(pattern, value)
        if not match:
            continue
        parts = [int(item) for item in match.groups()]
        try:
            return date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
        except ValueError:
            return None
    return None


def _clean(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _strip_agent_identifiers(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s*\[[^]]*\]\s*$", "", value).strip() or None


def _normalize_work_type(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    mapping = {
        "journal article": "article",
        "proceedings article": "proceedings",
        "book chapter": "book-chapter",
        "book": "book",
        "report": "report",
        "dissertation": "dissertation",
    }
    return mapping.get(normalized, normalized or "article")


def _discover_csv_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() == ".csv":
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*.csv") if item.is_file())
    return []
