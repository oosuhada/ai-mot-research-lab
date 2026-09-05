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
from research_lab.embeddings import build_embedding_provider
from research_lab.ingestion.normalization import normalize_doi
from research_lab.ingestion.openalex import OpenAlexClient
from research_lab.ingestion.service import OpenAlexIngestionService
from research_lab.models import CitationSnapshot, IngestionRun, Paper, PaperEmbedding, PaperVersion
from research_lab.taxonomy import TAXONOMY_VERSION

ImportFormat = Literal["doi", "bibtex", "ris", "csv", "scopus_csv"]


@dataclass(slots=True)
class ImportRecord:
    doi: str | None
    title: str | None
    abstract: str | None = None
    publication_year: int | None = None
    authors: str | None = None
    source: str = "user_import"
    source_record_id: str | None = None
    scopus_eid: str | None = None
    scopus_id: str | None = None
    cited_by_count: int | None = None
    source_title: str | None = None
    document_type: str | None = None
    affiliations: str | None = None
    keywords: str | None = None
    publisher: str | None = None
    primary_url: str | None = None
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
        self.embedding_provider = build_embedding_provider(settings)

    def close(self) -> None:
        self.openalex_client.close()

    def import_text(self, import_format: ImportFormat, content: str) -> ImportResult:
        records = parse_import(import_format, content)
        if not records:
            raise HTTPException(status_code=422, detail="No importable records were found")

        run_source = "scopus_export" if import_format == "scopus_csv" else "user_import"
        run = IngestionRun(
            source=run_source,
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
        paper = None
        if record.scopus_eid:
            paper = self.session.scalar(select(Paper).where(Paper.scopus_eid == record.scopus_eid))
        if paper is None and record.scopus_id:
            paper = self.session.scalar(select(Paper).where(Paper.scopus_id == record.scopus_id))
        if paper is None and doi:
            paper = self.session.scalar(select(Paper).where(Paper.doi == doi))
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

        imported_at = datetime.now(UTC)
        source_record_id = record.source_record_id or f"{run.id}:{index}"
        if paper is None:
            if not record.title:
                raise ValueError("A DOI that resolves through OpenAlex or a title is required")
            paper = Paper(
                doi=doi,
                scopus_eid=record.scopus_eid,
                scopus_id=record.scopus_id,
                title=record.title,
                abstract=record.abstract,
                publication_year=record.publication_year,
                publication_date=date(record.publication_year, 1, 1) if record.publication_year else None,
                work_type=_normalize_document_type(record.document_type) or "article",
                publisher=record.publisher,
                is_oa=False,
                primary_url=record.primary_url,
                retraction_status="none",
                correction_status="none",
                primary_source=record.source,
                source_record_id=source_record_id,
                retrieved_at=imported_at,
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
            paper.scopus_eid = paper.scopus_eid or record.scopus_eid
            paper.scopus_id = paper.scopus_id or record.scopus_id
            paper.publisher = paper.publisher or record.publisher
            paper.primary_url = paper.primary_url or record.primary_url
            if not paper.work_type:
                paper.work_type = _normalize_document_type(record.document_type)

        payload = {
            "doi": doi,
            "title": record.title,
            "abstract": record.abstract,
            "publication_year": record.publication_year,
            "authors": record.authors,
            "scopus_eid": record.scopus_eid,
            "scopus_id": record.scopus_id,
            "cited_by_count": record.cited_by_count,
            "source_title": record.source_title,
            "document_type": record.document_type,
            "affiliations": record.affiliations,
            "keywords": record.keywords,
            "publisher": record.publisher,
            "primary_url": record.primary_url,
            "raw": record.raw or {},
        }
        payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        version_source = "scopus_export" if record.source == "scopus_export" else "user_import"
        version_id = record.source_record_id or f"{run.id}:{index}"
        existing_version = self.session.scalar(
            select(PaperVersion).where(
                PaperVersion.paper_id == paper.id,
                PaperVersion.source == version_source,
                PaperVersion.source_record_id == version_id,
                PaperVersion.payload_hash == payload_hash,
            )
        )
        if existing_version is None:
            self.session.add(
                PaperVersion(
                    paper_id=paper.id,
                    source=version_source,
                    source_record_id=version_id,
                    version_label=("institutional-export" if record.source == "scopus_export" else "explicit-user-import"),
                    retrieved_at=imported_at,
                    license=None,
                    payload_hash=payload_hash,
                    source_metadata=payload,
                )
            )

        provenance = dict(paper.provenance or {})
        if record.source == "scopus_export":
            history = list(provenance.get("scopus_exports") or [])
            history.append(
                {
                    "run_id": str(run.id),
                    "record": index,
                    "eid": record.scopus_eid,
                    "scopus_id": record.scopus_id,
                    "imported_at": imported_at.isoformat(),
                }
            )
            provenance["scopus_exports"] = history[-20:]
            if record.cited_by_count is not None:
                self.session.add(
                    CitationSnapshot(
                        paper_id=paper.id,
                        source="scopus_export",
                        citation_count=record.cited_by_count,
                        oa_status=paper.oa_status,
                        captured_at=imported_at,
                    )
                )
        else:
            history = list(provenance.get("user_imports") or [])
            history.append({"run_id": str(run.id), "record": index, "imported_at": imported_at.isoformat()})
            provenance["user_imports"] = history[-20:]
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
        vector = self.embedding_provider.embed_document(f"{paper.title}\n{paper.abstract or ''}")
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
    if import_format == "scopus_csv":
        return _parse_scopus_csv(content)
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
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
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


def _parse_scopus_csv(content: str) -> list[ImportRecord]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if reader.fieldnames is None:
        return []
    headers = {_normalize_header(name): name for name in reader.fieldnames}
    if not _has_alias(headers, "title"):
        raise HTTPException(status_code=422, detail="Scopus CSV requires a Title column")

    records: list[ImportRecord] = []
    for row in reader:
        link = _row_alias(row, headers, "link", "scopuslink", "url")
        eid = _row_alias(row, headers, "eid") or _extract_scopus_eid(link)
        scopus_id = _row_alias(row, headers, "scopusid", "scopusidentifier")
        if not scopus_id and eid:
            match = re.search(r"2-s2\.0-(\d+)", eid)
            scopus_id = match.group(1) if match else None
        records.append(
            ImportRecord(
                doi=_row_alias(row, headers, "doi"),
                title=_row_alias(row, headers, "title", "documenttitle"),
                abstract=_row_alias(row, headers, "abstract"),
                publication_year=_safe_year(_row_alias(row, headers, "year", "publicationyear")),
                authors=_row_alias(row, headers, "authors", "authorfullnames", "authornames"),
                source="scopus_export",
                source_record_id=eid or scopus_id,
                scopus_eid=eid,
                scopus_id=scopus_id,
                cited_by_count=_safe_int(_row_alias(row, headers, "citedby", "citationcount")),
                source_title=_row_alias(row, headers, "sourcetitle", "publicationname"),
                document_type=_row_alias(row, headers, "documenttype", "type"),
                affiliations=_row_alias(row, headers, "affiliations", "authorswithaffiliations"),
                keywords=_row_alias(row, headers, "authorkeywords", "indexkeywords", "keywords"),
                publisher=_row_alias(row, headers, "publisher"),
                primary_url=link,
                raw={key: value for key, value in row.items()},
            )
        )
    return records


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", value.strip().lower())


def _has_alias(headers: dict[str, str], *aliases: str) -> bool:
    return any(_normalize_header(alias) in headers for alias in aliases)


def _row_alias(row: dict[str, str], headers: dict[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        key = headers.get(_normalize_header(alias))
        if key is None:
            continue
        value = row.get(key, "")
        if value and value.strip():
            return value.strip()
    return None


def _extract_scopus_eid(link: str | None) -> str | None:
    if not link:
        return None
    match = re.search(r"2-s2\.0-\d+", link)
    return match.group(0) if match else None


def _normalize_document_type(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    mapping = {
        "article": "article",
        "conference paper": "conference-paper",
        "review": "review",
        "book chapter": "book-chapter",
        "book": "book",
        "editorial": "editorial",
        "note": "note",
    }
    return mapping.get(lowered, lowered.replace(" ", "-"))


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


def _safe_int(value: str | None) -> int | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9-]", "", value)
    try:
        return int(normalized)
    except ValueError:
        return None
