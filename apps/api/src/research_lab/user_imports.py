from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.embeddings import LocalHashEmbeddingProvider
from research_lab.ingestion.normalization import normalize_doi
from research_lab.ingestion.openalex import OpenAlexClient
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import IngestionRun, Paper, PaperEmbedding, PaperVersion
from research_lab.taxonomy import TAXONOMY_VERSION

ImportFormat = Literal["doi", "bibtex", "ris", "csv"]


@dataclass(slots=True)
class ImportRecord:
    doi: str | None
    title: str | None
    abstract: str | None = None
    publication_year: int | None = None
    authors: str | None = None
    raw: dict[str, object] | None = None


@dataclass(slots=True)
class ImportResult:
    run_id: uuid.UUID
    paper_ids: list[uuid.UUID]
    inserted_count: int
    updated_count: int
    error_count: int
    errors: list[str]


class UserImportService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.openalex_client = OpenAlexClient(settings)
        self.embedding_provider = LocalHashEmbeddingProvider()

    def close(self) -> None:
        self.openalex_client.close()

    def import_text(self, import_format: ImportFormat, content: str) -> ImportResult:
        records = parse_import(import_format, content)
        if not records:
            raise HTTPException(status_code=422, detail="No importable records were found")

        run = IngestionRun(
            source="user_import",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={"format": import_format, "record_count": len(records)},
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        paper_ids: list[uuid.UUID] = []
        errors: list[str] = []
        try:
            for index, record in enumerate(records):
                run.fetched_count += 1
                try:
                    paper, inserted = self._import_record(record, run, index)
                    paper_ids.append(paper.id)
                    run.accepted_count += 1
                    if inserted:
                        run.inserted_count += 1
                    else:
                        run.updated_count += 1
                except Exception as exc:  # one bad row must not rollback the whole import batch
                    self.session.rollback()
                    run = self.session.get(IngestionRun, run.id) or run
                    run.error_count += 1
                    errors.append(f"record {index + 1}: {type(exc).__name__}: {exc}")
                run.checkpoint = {"record_index": index, "updated_at": datetime.now(UTC).isoformat()}
                self.session.commit()
            run.status = "completed_with_errors" if errors else "completed"
            run.finished_at = datetime.now(UTC)
            run.error_message = "\n".join(errors) if errors else None
            self.session.commit()
        finally:
            self.close()

        return ImportResult(
            run_id=run.id,
            paper_ids=paper_ids,
            inserted_count=run.inserted_count,
            updated_count=run.updated_count,
            error_count=run.error_count,
            errors=errors,
        )

    def _import_record(self, record: ImportRecord, run: IngestionRun, index: int) -> tuple[Paper, bool]:
        doi = normalize_doi(record.doi)
        paper = self.session.scalar(select(Paper).where(Paper.doi == doi)) if doi else None
        inserted = False

        if paper is None and doi:
            provider_record = self.openalex_client.lookup_doi(doi)
            if provider_record is not None:
                provider_service = OpenAlexIngestionService(
                    self.session,
                    self.settings,
                    client=self.openalex_client,
                    embedding_provider=self.embedding_provider,
                )
                paper, inserted = provider_service.upsert_openalex_record(provider_record)

        if paper is None:
            if not record.title:
                raise ValueError("A DOI that resolves through OpenAlex or a title is required")
            paper = Paper(
                doi=doi,
                title=record.title,
                abstract=record.abstract,
                publication_year=record.publication_year,
                publication_date=date(record.publication_year, 1, 1) if record.publication_year else None,
                work_type="article",
                is_oa=False,
                retraction_status="none",
                correction_status="none",
                primary_source="user_import",
                source_record_id=f"{run.id}:{index}",
                retrieved_at=datetime.now(UTC),
                provenance={},
            )
            self.session.add(paper)
            self.session.flush()
            inserted = True
        else:
            if record.title and (not paper.title or paper.title == "Untitled work"):
                paper.title = record.title
            paper.abstract = paper.abstract or record.abstract
            paper.publication_year = paper.publication_year or record.publication_year

        payload = {
            "doi": doi,
            "title": record.title,
            "abstract": record.abstract,
            "publication_year": record.publication_year,
            "authors": record.authors,
            "raw": record.raw or {},
        }
        payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        imported_at = datetime.now(UTC)
        self.session.add(
            PaperVersion(
                paper_id=paper.id,
                source="user_import",
                source_record_id=f"{run.id}:{index}",
                version_label="explicit-user-import",
                retrieved_at=imported_at,
                license=None,
                payload_hash=hashlib.sha256(payload_json.encode()).hexdigest(),
                source_metadata=payload,
            )
        )
        provenance = dict(paper.provenance or {})
        import_history = list(provenance.get("user_imports") or [])
        import_history.append({"run_id": str(run.id), "record": index, "imported_at": imported_at.isoformat()})
        provenance["user_imports"] = import_history
        paper.provenance = provenance
        paper.retrieved_at = imported_at
        self._upsert_embedding(paper)
        self.session.flush()
        return paper, inserted

    def _upsert_embedding(self, paper: Paper) -> None:
        row = self.session.scalar(
            select(PaperEmbedding).where(
                PaperEmbedding.paper_id == paper.id,
                PaperEmbedding.provider == self.embedding_provider.name,
                PaperEmbedding.model == self.embedding_provider.model,
            )
        )
        vector = self.embedding_provider.embed(f"{paper.title}\n{paper.abstract or ''}")
        if row is None:
            self.session.add(
                PaperEmbedding(
                    paper_id=paper.id,
                    provider=self.embedding_provider.name,
                    model=self.embedding_provider.model,
                    dimensions=len(vector),
                    embedding=vector,
                )
            )
        else:
            row.embedding = vector


def parse_import(import_format: ImportFormat, content: str) -> list[ImportRecord]:
    if import_format == "doi":
        candidates = re.split(r"[\s,;]+", content.strip())
        dois = [normalize_doi(value) for value in candidates if value.strip()]
        return [ImportRecord(doi=doi, title=None, raw={"input": doi}) for doi in dois if doi]
    if import_format == "bibtex":
        return _parse_bibtex(content)
    if import_format == "ris":
        return _parse_ris(content)
    if import_format == "csv":
        return _parse_csv(content)
    raise ValueError(f"Unsupported import format: {import_format}")


def _parse_bibtex(content: str) -> list[ImportRecord]:
    entries: list[ImportRecord] = []
    for match in re.finditer(r"@\w+\s*\{[^,]+,(.*?)(?=\n\s*\}\s*(?:@|$))", content, flags=re.S | re.I):
        body = match.group(1)
        fields: dict[str, str] = {}
        for field in re.finditer(r"(\w+)\s*=\s*[\{\"](.*?)[\}\"]\s*,?\s*(?=\w+\s*=|$)", body, flags=re.S):
            fields[field.group(1).lower()] = " ".join(field.group(2).split())
        year = _safe_year(fields.get("year"))
        entries.append(
            ImportRecord(
                doi=fields.get("doi"),
                title=fields.get("title"),
                abstract=fields.get("abstract"),
                publication_year=year,
                authors=fields.get("author"),
                raw={key: value for key, value in fields.items()},
            )
        )
    return entries


def _parse_ris(content: str) -> list[ImportRecord]:
    entries: list[ImportRecord] = []
    current: dict[str, list[str]] = {}
    for line in content.splitlines():
        match = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", line.rstrip())
        if not match:
            continue
        key, value = match.groups()
        if key == "ER":
            if current:
                entries.append(_ris_record(current))
                current = {}
            continue
        current.setdefault(key, []).append(value.strip())
    if current:
        entries.append(_ris_record(current))
    return entries


def _ris_record(fields: dict[str, list[str]]) -> ImportRecord:
    return ImportRecord(
        doi=_first(fields, "DO"),
        title=_first(fields, "TI") or _first(fields, "T1"),
        abstract=_first(fields, "AB"),
        publication_year=_safe_year(_first(fields, "PY") or _first(fields, "Y1")),
        authors="; ".join(fields.get("AU", [])) or None,
        raw={key: values for key, values in fields.items()},
    )


def _parse_csv(content: str) -> list[ImportRecord]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return []
    normalized_headers = {name.lower().strip(): name for name in reader.fieldnames}
    if "doi" not in normalized_headers and "title" not in normalized_headers:
        raise HTTPException(status_code=422, detail="CSV requires a doi or title column")
    records: list[ImportRecord] = []
    for row in reader:
        records.append(
            ImportRecord(
                doi=_csv_value(row, normalized_headers, "doi"),
                title=_csv_value(row, normalized_headers, "title"),
                abstract=_csv_value(row, normalized_headers, "abstract"),
                publication_year=_safe_year(
                    _csv_value(row, normalized_headers, "year")
                    or _csv_value(row, normalized_headers, "publication_year")
                ),
                authors=_csv_value(row, normalized_headers, "authors")
                or _csv_value(row, normalized_headers, "author"),
                raw={key: value for key, value in row.items()},
            )
        )
    return records


def _csv_value(row: dict[str, str], headers: dict[str, str], name: str) -> str | None:
    key = headers.get(name)
    value = row.get(key, "") if key else ""
    return value.strip() or None


def _first(values: dict[str, list[str]], key: str) -> str | None:
    found = values.get(key) or []
    return found[0] if found else None


def _safe_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(?:19|20)\d{2}", value)
    return int(match.group(0)) if match else None
