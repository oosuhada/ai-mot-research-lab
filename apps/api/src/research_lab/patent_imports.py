from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.models import IngestionRun, PatentDocument
from research_lab.taxonomy import TAXONOMY_VERSION


@dataclass(slots=True)
class PatentImportRecord:
    application_number: str | None
    publication_number: str | None
    registration_number: str | None
    jurisdiction: str | None
    title: str | None
    abstract: str | None
    filing_date: date | None
    publication_date: date | None
    priority_date: date | None
    applicants: list[str]
    inventors: list[str]
    ipc_codes: list[str]
    cpc_codes: list[str]
    family_id: str | None
    legal_status: str | None
    raw: dict[str, str]


@dataclass(slots=True)
class PatentImportResult:
    run_id: uuid.UUID
    patent_ids: list[uuid.UUID]
    inserted_count: int
    updated_count: int
    error_count: int
    errors: list[str]


class PatentImportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def import_wips_csv(self, content: str) -> PatentImportResult:
        records = parse_wips_csv(content)
        if not records:
            raise HTTPException(status_code=422, detail="No importable patent records were found")

        run = IngestionRun(
            source="wips_on_export",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={"format": "wips_csv", "record_count": len(records)},
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        patent_ids: list[uuid.UUID] = []
        errors: list[str] = []
        for index, record in enumerate(records):
            run.fetched_count += 1
            try:
                patent, inserted = self._upsert(record, run, index)
                patent_ids.append(patent.id)
                run.accepted_count += 1
                if inserted:
                    run.inserted_count += 1
                else:
                    run.updated_count += 1
            except Exception as exc:
                self.session.rollback()
                run = self.session.get(IngestionRun, run.id) or run
                run.error_count += 1
                errors.append(f"record {index + 1}: {type(exc).__name__}: {exc}")
            run.checkpoint = {"record_index": index, "updated_at": datetime.now(UTC).isoformat()}
            self.session.commit()

        run.status = "completed_with_errors" if errors else "completed"
        run.error_message = "\n".join(errors) if errors else None
        run.finished_at = datetime.now(UTC)
        self.session.commit()
        return PatentImportResult(
            run_id=run.id,
            patent_ids=patent_ids,
            inserted_count=run.inserted_count,
            updated_count=run.updated_count,
            error_count=run.error_count,
            errors=errors,
        )

    def _upsert(
        self,
        record: PatentImportRecord,
        run: IngestionRun,
        index: int,
    ) -> tuple[PatentDocument, bool]:
        source_record_id = _source_record_id(record)
        patent = self.session.scalar(
            select(PatentDocument).where(
                PatentDocument.primary_source == "wips_on",
                PatentDocument.source_record_id == source_record_id,
            )
        )
        now = datetime.now(UTC)
        inserted = patent is None
        if patent is None:
            if not record.title:
                raise ValueError("WIPS patent export row requires a title")
            patent = PatentDocument(
                application_number=record.application_number,
                publication_number=record.publication_number,
                registration_number=record.registration_number,
                jurisdiction=record.jurisdiction,
                title=record.title,
                abstract=record.abstract,
                filing_date=record.filing_date,
                publication_date=record.publication_date,
                priority_date=record.priority_date,
                applicants=record.applicants,
                inventors=record.inventors,
                ipc_codes=record.ipc_codes,
                cpc_codes=record.cpc_codes,
                family_id=record.family_id,
                legal_status=record.legal_status,
                primary_source="wips_on",
                source_record_id=source_record_id,
                retrieved_at=now,
                provenance={},
            )
            self.session.add(patent)
            self.session.flush()
        else:
            patent.application_number = record.application_number or patent.application_number
            patent.publication_number = record.publication_number or patent.publication_number
            patent.registration_number = record.registration_number or patent.registration_number
            patent.jurisdiction = record.jurisdiction or patent.jurisdiction
            patent.title = record.title or patent.title
            patent.abstract = record.abstract or patent.abstract
            patent.filing_date = record.filing_date or patent.filing_date
            patent.publication_date = record.publication_date or patent.publication_date
            patent.priority_date = record.priority_date or patent.priority_date
            patent.applicants = record.applicants or patent.applicants
            patent.inventors = record.inventors or patent.inventors
            patent.ipc_codes = record.ipc_codes or patent.ipc_codes
            patent.cpc_codes = record.cpc_codes or patent.cpc_codes
            patent.family_id = record.family_id or patent.family_id
            patent.legal_status = record.legal_status or patent.legal_status
            patent.retrieved_at = now

        provenance = dict(patent.provenance or {})
        imports = list(provenance.get("wips_exports") or [])
        imports.append(
            {
                "run_id": str(run.id),
                "record": index,
                "imported_at": now.isoformat(),
                "raw": record.raw,
            }
        )
        provenance["wips_exports"] = imports[-10:]
        patent.provenance = provenance
        self.session.flush()
        return patent, inserted


def parse_wips_csv(content: str) -> list[PatentImportRecord]:
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if reader.fieldnames is None:
        return []
    headers = {_normalize_header(name): name for name in reader.fieldnames}
    if not _has_any(headers, "title", "발명의명칭", "발명명칭", "명칭"):
        raise HTTPException(status_code=422, detail="WIPS CSV requires a patent title column")

    rows: list[PatentImportRecord] = []
    for row in reader:
        application_number = _number(
            _value(row, headers, "applicationnumber", "applicationno", "appno", "출원번호")
        )
        publication_number = _number(
            _value(row, headers, "publicationnumber", "publicationno", "pubno", "공개번호")
        )
        registration_number = _number(
            _value(row, headers, "registrationnumber", "grantnumber", "등록번호")
        )
        jurisdiction = _value(row, headers, "jurisdiction", "country", "국가", "국가코드")
        jurisdiction = (jurisdiction.upper() if jurisdiction else _infer_jurisdiction(
            publication_number or application_number or registration_number
        ))
        rows.append(
            PatentImportRecord(
                application_number=application_number,
                publication_number=publication_number,
                registration_number=registration_number,
                jurisdiction=jurisdiction,
                title=_value(row, headers, "title", "inventiontitle", "발명의명칭", "발명명칭", "명칭"),
                abstract=_value(row, headers, "abstract", "summary", "요약", "초록"),
                filing_date=_parse_date(_value(row, headers, "filingdate", "applicationdate", "출원일")),
                publication_date=_parse_date(_value(row, headers, "publicationdate", "공개일")),
                priority_date=_parse_date(_value(row, headers, "prioritydate", "우선권일")),
                applicants=_split_values(
                    _value(row, headers, "applicants", "applicant", "assignee", "currentassignee", "출원인", "출원인명", "권리자")
                ),
                inventors=_split_values(_value(row, headers, "inventors", "inventor", "발명자")),
                ipc_codes=_split_values(_value(row, headers, "ipc", "ipccode", "ipcclass", "ipc분류", "ipc코드")),
                cpc_codes=_split_values(_value(row, headers, "cpc", "cpccode", "cpcclass", "cpc분류", "cpc코드")),
                family_id=_value(row, headers, "familyid", "simplefamily", "family", "패밀리", "특허패밀리"),
                legal_status=_value(row, headers, "legalstatus", "status", "법적상태", "상태"),
                raw={str(key): str(value or "") for key, value in row.items()},
            )
        )
    return rows


def _source_record_id(record: PatentImportRecord) -> str:
    for value in (record.publication_number, record.application_number, record.registration_number):
        if value:
            return f"{record.jurisdiction or 'XX'}:{value}"
    digest = hashlib.sha256(
        f"{record.jurisdiction}|{record.title}|{record.filing_date}".encode("utf-8")
    ).hexdigest()
    return f"derived:{digest}"


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]+", "", value.strip().lower())


def _has_any(headers: dict[str, str], *aliases: str) -> bool:
    return any(_normalize_header(alias) in headers for alias in aliases)


def _value(row: dict[str, str], headers: dict[str, str], *aliases: str) -> str | None:
    for alias in aliases:
        key = headers.get(_normalize_header(alias))
        if not key:
            continue
        raw = row.get(key, "")
        if raw and raw.strip():
            return raw.strip()
    return None


def _split_values(value: str | None) -> list[str]:
    if not value:
        return []
    values = [part.strip() for part in re.split(r"[;|\n]+", value) if part.strip()]
    seen: set[str] = set()
    deduped: list[str] = []
    for item in values:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) >= 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    match = re.search(r"((?:19|20)\d{2})", value)
    if match:
        return date(int(match.group(1)), 1, 1)
    return None


def _number(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", "", value).upper()


def _infer_jurisdiction(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"^([A-Z]{2})", value.upper())
    return match.group(1) if match else None
