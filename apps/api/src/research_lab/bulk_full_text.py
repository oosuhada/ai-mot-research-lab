from __future__ import annotations

import gzip
import json
import socket
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urlparse

import httpx
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from research_lab.config import Settings
from research_lab.ingestion.normalization import normalize_arxiv_id, normalize_doi
from research_lab.models import (
    FullTextQueueItem,
    FullTextSourceAttempt,
    Paper,
    PaperChunk,
    PaperContentProfile,
)
from research_lab.xml_pipeline import XmlEvidenceService

PMC_ID_CONVERTER_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
EUROPE_PMC_FULL_TEXT_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class PmcBulkFullTextWorker:
    """Batch-map corpus DOIs to PMCIDs, then fetch only matching OA XML documents.

    The ID converter accepts up to 200 identifiers per request. This avoids one
    Europe PMC search request per paper and never downloads a multi-terabyte
    corpus snapshot onto the worker host.
    """

    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.worker_id = worker_id or f"pmc-bulk:{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "ai-mot-research-lab/0.1 (PMC OA bulk enrichment)"},
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run(
        self,
        *,
        max_items: int = 100,
        max_xml_bytes: int = 30_000_000,
        lease_minutes: int = 20,
        download_workers: int = 4,
    ) -> dict[str, int | str]:
        items = self._claim_batch(
            max_items=min(max(max_items, 1), 200),
            lease_minutes=max(lease_minutes, 1),
        )
        if not items:
            self.close()
            return {"worker_id": self.worker_id, "selected": 0, "mapped": 0, "completed": 0, "failed": 0}

        papers = {item.paper_id: self.session.get(Paper, item.paper_id) for item in items}
        valid_pairs = [(item, paper) for item in items if (paper := papers[item.paper_id]) is not None and paper.doi]
        doi_map: dict[str, dict[str, Any]] = {}
        try:
            doi_map = self._map_dois([paper.doi for _, paper in valid_pairs if paper.doi])
        except Exception as exc:
            for item, paper in valid_pairs:
                self._record_failure(item, paper, "pmc_bulk_id_map", PMC_ID_CONVERTER_URL, exc)
                self._release(item, "pmc_bulk_mapping_failure", str(exc), delay_minutes=10)
            self.close()
            return {
                "worker_id": self.worker_id,
                "selected": len(items),
                "mapped": 0,
                "completed": 0,
                "failed": len(items),
            }

        downloads: dict[uuid.UUID, tuple[str, str, bytes] | Exception] = {}
        mapped = 0
        with ThreadPoolExecutor(max_workers=min(max(download_workers, 1), 8)) as pool:
            futures = {}
            for item, paper in valid_pairs:
                record = doi_map.get(normalize_doi(paper.doi) or "")
                pmcid = record.get("pmcid") if record else None
                if not isinstance(pmcid, str) or not pmcid.startswith("PMC") or record.get("live") is False:
                    continue
                mapped += 1
                url = f"{EUROPE_PMC_FULL_TEXT_BASE_URL}/{pmcid}/fullTextXML"
                futures[pool.submit(self._download_xml, url, max_xml_bytes)] = (item.id, pmcid, url)
            for future in as_completed(futures):
                item_id, pmcid, url = futures[future]
                try:
                    downloads[item_id] = (pmcid, url, future.result())
                except Exception as exc:
                    downloads[item_id] = exc

        completed = failed = 0
        for item, paper in valid_pairs:
            downloaded = downloads.get(item.id)
            if downloaded is None:
                self._record_failure(
                    item,
                    paper,
                    "pmc_bulk_id_map",
                    PMC_ID_CONVERTER_URL,
                    RuntimeError("DOI is not present in the live PMC article dataset"),
                )
                self._release(item, "pmc_bulk_not_found", "DOI is not present in live PMC", delay_minutes=0)
                failed += 1
                continue
            if isinstance(downloaded, Exception):
                pmcid = str((doi_map.get(normalize_doi(paper.doi) or "") or {}).get("pmcid") or "")
                url = f"{EUROPE_PMC_FULL_TEXT_BASE_URL}/{pmcid}/fullTextXML"
                self._record_failure(item, paper, "pmc_bulk_xml", url, downloaded)
                self._release(item, "pmc_bulk_download_failure", str(downloaded), delay_minutes=10)
                failed += 1
                continue
            pmcid, url, xml_bytes = downloaded
            started_at = datetime.now(UTC)
            try:
                result = XmlEvidenceService(self.session, self.settings).ingest(
                    paper.id,
                    xml_bytes,
                    source="pmc_bulk_xml",
                    source_record_id=pmcid,
                    source_url=url,
                    license_label=paper.license or "PMC Open Access article-level license",
                    redistributable=False,
                    section_label="PMC / Europe PMC full text",
                )
                if result.chunk_count <= 0:
                    raise RuntimeError("PMC XML contained no extractable chunks")
                self._record_attempt(item, paper, "pmc_bulk_xml", url, started_at, "completed")
                self._mark_completed(item, paper, pmcid)
                completed += 1
            except Exception as exc:
                self.session.rollback()
                self._record_failure(item, paper, "pmc_bulk_xml", url, exc, started_at=started_at)
                self._release(item, "pmc_bulk_ingest_failure", str(exc), delay_minutes=10)
                failed += 1

        for item in items:
            if item.paper_id not in {paper.id for _, paper in valid_pairs}:
                self._release(item, "pmc_bulk_missing_identity", "Paper has no DOI", delay_minutes=0)
                failed += 1
        self.close()
        return {
            "worker_id": self.worker_id,
            "selected": len(items),
            "mapped": mapped,
            "completed": completed,
            "failed": failed,
        }

    def _claim_batch(self, *, max_items: int, lease_minutes: int) -> list[FullTextQueueItem]:
        now = datetime.now(UTC)
        already_checked = exists(
            select(FullTextSourceAttempt.id).where(
                FullTextSourceAttempt.paper_id == Paper.id,
                or_(
                    FullTextSourceAttempt.source_kind == "pmc_bulk_id_map",
                    (
                        (FullTextSourceAttempt.source_kind == "pmc_bulk_xml")
                        & (FullTextSourceAttempt.status == "completed")
                    ),
                ),
            )
        )
        items = list(
            self.session.scalars(
                select(FullTextQueueItem)
                .join(Paper, Paper.id == FullTextQueueItem.paper_id)
                .where(
                    FullTextQueueItem.status == "pending",
                    FullTextQueueItem.rights_status.in_(("open_access", "unknown")),
                    or_(
                        FullTextQueueItem.next_attempt_at.is_(None),
                        FullTextQueueItem.next_attempt_at <= now,
                    ),
                    Paper.doi.is_not(None),
                    ~already_checked,
                )
                .order_by(FullTextQueueItem.priority.desc(), FullTextQueueItem.created_at)
                .limit(max_items)
                .with_for_update(skip_locked=True)
            )
        )
        for item in items:
            item.status = "processing"
            item.attempts += 1
            item.worker_id = self.worker_id
            item.claimed_at = now
            item.lease_expires_at = now + timedelta(minutes=lease_minutes)
        if items:
            self.session.commit()
        return items

    def _map_dois(self, dois: list[str]) -> dict[str, dict[str, Any]]:
        email = self.settings.crossref_mailto or self.settings.unpaywall_email
        params = {
            "ids": ",".join(dois[:200]),
            "idtype": "doi",
            "format": "json",
            "tool": "ai_mot_research_lab",
        }
        if email:
            params["email"] = email
        response = self.client.get(PMC_ID_CONVERTER_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            doi = normalize_doi(record.get("doi"))
            if doi:
                result[doi] = record
        return result

    def _download_xml(self, url: str, max_xml_bytes: int) -> bytes:
        response = self.client.get(url, headers={"Accept": "application/xml"})
        response.raise_for_status()
        if len(response.content) > max_xml_bytes:
            raise ValueError(f"PMC XML exceeds {max_xml_bytes} bytes")
        ET.fromstring(response.content)
        return response.content

    def _record_failure(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        source_kind: str,
        source_url: str,
        error: Exception,
        *,
        started_at: datetime | None = None,
    ) -> None:
        self._record_attempt(
            item,
            paper,
            source_kind,
            source_url,
            started_at or datetime.now(UTC),
            "failed",
            failure_kind="provider_error",
            error=error,
        )

    def _record_attempt(
        self,
        item: FullTextQueueItem,
        paper: Paper,
        source_kind: str,
        source_url: str,
        started_at: datetime,
        status: str,
        *,
        failure_kind: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.session.add(
            FullTextSourceAttempt(
                queue_item_id=item.id,
                paper_id=paper.id,
                source_url=source_url,
                domain=urlparse(source_url).hostname,
                publisher=paper.publisher,
                source_kind=source_kind,
                status=status,
                failure_kind=failure_kind,
                error_message=(f"{type(error).__name__}: {error}"[:1000] if error else None),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        )
        self.session.commit()

    def _mark_completed(self, item: FullTextQueueItem, paper: Paper, pmcid: str) -> None:
        item.status = "completed"
        item.failure_kind = None
        item.last_error = None
        item.next_attempt_at = None
        self._clear_lease(item)
        provenance = dict(paper.provenance or {})
        provenance["pmcid"] = pmcid
        paper.provenance = provenance
        profile = self.session.get(PaperContentProfile, paper.id)
        if profile is not None:
            profile.full_text_status = "available"
            profile.full_text_access = "open_access"
            profile.full_text_updated_at = datetime.now(UTC)
        self.session.commit()

    def _release(
        self,
        item: FullTextQueueItem,
        failure_kind: str,
        message: str,
        *,
        delay_minutes: int,
    ) -> None:
        item.status = "pending"
        item.failure_kind = failure_kind
        item.last_error = message[:1000]
        item.next_attempt_at = (
            datetime.now(UTC) + timedelta(minutes=delay_minutes) if delay_minutes else datetime.now(UTC)
        )
        self._clear_lease(item)
        self.session.commit()

    @staticmethod
    def _clear_lease(item: FullTextQueueItem) -> None:
        item.worker_id = None
        item.claimed_at = None
        item.lease_expires_at = None


class S2OrcShardImporter:
    """Stream a Semantic Scholar S2ORC JSONL shard and ingest corpus matches only."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def run(self, path: Path, *, max_matches: int = 0) -> dict[str, int | str]:
        lookup = self._paper_lookup()
        scanned = matched = completed = failed = 0
        with _open_maybe_gzip(path) as stream:
            for raw_line in stream:
                scanned += 1
                try:
                    record = json.loads(raw_line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    failed += 1
                    continue
                if not isinstance(record, dict):
                    continue
                paper = _match_s2orc_record(record, lookup)
                if paper is None:
                    continue
                text = _s2orc_text(record)
                if not text:
                    continue
                matched += 1
                try:
                    xml_data = _text_as_xml(text)
                    source_id = str(
                        record.get("corpusid") or record.get("corpusId") or record.get("paperId") or paper.id
                    )
                    result = XmlEvidenceService(self.session, self.settings).ingest(
                        paper.id,
                        xml_data,
                        source="s2orc",
                        source_record_id=source_id,
                        source_url="https://api.semanticscholar.org/datasets/v1/",
                        license_label="ODC-By 1.0; underlying article rights apply",
                        redistributable=False,
                        section_label="S2ORC full text",
                    )
                    if result.chunk_count:
                        _mark_import_completed(self.session, paper)
                        completed += 1
                except Exception:
                    self.session.rollback()
                    failed += 1
                if max_matches > 0 and matched >= max_matches:
                    break
        return {
            "input": str(path),
            "records_scanned": scanned,
            "records_matched": matched,
            "completed": completed,
            "failed": failed,
        }

    def _paper_lookup(self) -> dict[str, dict[str, Paper]]:
        papers = list(
            self.session.scalars(
                select(Paper).where(~exists(select(PaperChunk.id).where(PaperChunk.paper_id == Paper.id)))
            )
        )
        return {
            "doi": {value: paper for paper in papers if (value := normalize_doi(paper.doi))},
            "arxiv": {value: paper for paper in papers if (value := normalize_arxiv_id(paper.arxiv_id))},
            "s2": {paper.s2_id: paper for paper in papers if paper.s2_id},
        }


def _open_maybe_gzip(path: Path) -> BinaryIO:
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def _match_s2orc_record(record: dict[str, Any], lookup: dict[str, dict[str, Paper]]) -> Paper | None:
    external = record.get("externalids") or record.get("externalIds") or {}
    external = external if isinstance(external, dict) else {}
    doi = normalize_doi(external.get("DOI") or external.get("doi") or record.get("doi"))
    if doi and doi in lookup["doi"]:
        return lookup["doi"][doi]
    arxiv = normalize_arxiv_id(external.get("ArXiv") or external.get("arxiv") or record.get("arxiv_id"))
    if arxiv and arxiv in lookup["arxiv"]:
        return lookup["arxiv"][arxiv]
    for key in (record.get("paperId"), record.get("paper_id"), record.get("corpusid"), record.get("corpusId")):
        if key is not None and str(key) in lookup["s2"]:
            return lookup["s2"][str(key)]
    return None


def _s2orc_text(record: dict[str, Any]) -> str:
    for value in (
        record.get("text"),
        (record.get("content") or {}).get("text") if isinstance(record.get("content"), dict) else None,
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    for container in (record, record.get("pdf_parse"), record.get("grobid_parse")):
        if not isinstance(container, dict):
            continue
        body = container.get("body_text")
        if not isinstance(body, list):
            continue
        paragraphs = [
            item.get("text", "").strip()
            for item in body
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        if paragraphs:
            return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
    return ""


def _text_as_xml(text: str) -> bytes:
    root = ET.Element("article")
    body = ET.SubElement(root, "body")
    for paragraph in text.split("\n\n"):
        cleaned = " ".join(paragraph.split())
        if cleaned:
            ET.SubElement(body, "p").text = cleaned
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _mark_import_completed(session: Session, paper: Paper) -> None:
    item = session.scalar(select(FullTextQueueItem).where(FullTextQueueItem.paper_id == paper.id))
    if item is not None:
        item.status = "completed"
        item.failure_kind = None
        item.last_error = None
        item.next_attempt_at = None
        item.worker_id = None
        item.claimed_at = None
        item.lease_expires_at = None
    profile = session.get(PaperContentProfile, paper.id)
    if profile is not None:
        profile.full_text_status = "available"
        profile.full_text_access = "open_access"
        profile.full_text_updated_at = datetime.now(UTC)
    session.commit()
