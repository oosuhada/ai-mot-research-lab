from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from research_lab.ingestion.normalization import normalize_arxiv_id, normalize_doi
from research_lab.models import IngestionRun, Paper
from research_lab.taxonomy import TAXONOMY_VERSION

SOURCE = "semantic_scholar_papers_dump"
_PAPER_HASH_PATTERN = re.compile(r"/paper/([0-9a-f]{40})(?:[/?#]|$)", re.IGNORECASE)


@dataclass(slots=True)
class SemanticScholarPaperMappingResult:
    run_id: str
    status: str
    records_scanned: int
    matched: int
    updated: int
    already_mapped: int
    conflicts: int
    unmatched: int
    invalid: int


def semantic_scholar_ids(record: dict[str, object]) -> tuple[str | None, str | None]:
    corpus = record.get("corpusid") or record.get("corpusId")
    corpus_id = str(corpus) if corpus is not None else None
    paper_id = record.get("paperId") or record.get("paper_id")
    if paper_id:
        value = str(paper_id).strip()
        if value:
            return value, corpus_id
    url = record.get("url")
    if isinstance(url, str):
        match = _PAPER_HASH_PATTERN.search(url)
        if match:
            return match.group(1).lower(), corpus_id
    return None, corpus_id


class SemanticScholarPapersMapper:
    """Map S2AG papers dump records onto existing canonical papers.

    This mapper intentionally does not create new canonical papers. Its purpose is
    to backfill Semantic Scholar paper/corpus IDs so S2ORC v2 full-text shards can
    match the already curated AI x MOT corpus with high recall.
    """

    def __init__(self, session: Session, *, commit_every: int = 10_000) -> None:
        self.session = session
        self.commit_every = max(commit_every, 1_000)
        self._doi: dict[str, object] = {}
        self._arxiv: dict[str, object] = {}
        self._pubmed: dict[str, object] = {}
        self._s2: dict[str, object] = {}
        self._corpus: dict[str, object] = {}

    def run(self, path: Path) -> SemanticScholarPaperMappingResult:
        if not path.is_file():
            raise FileNotFoundError(path)
        self._load_lookup()
        run = IngestionRun(
            source=SOURCE,
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={"input": str(path)},
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        stats = {
            "records_scanned": 0,
            "matched": 0,
            "updated": 0,
            "already_mapped": 0,
            "conflicts": 0,
            "unmatched": 0,
            "invalid": 0,
        }
        try:
            with _open_maybe_gzip(path) as raw:
                for line_number, raw_line in enumerate(raw, start=1):
                    stats["records_scanned"] += 1
                    run.fetched_count += 1
                    try:
                        record = json.loads(raw_line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        stats["invalid"] += 1
                        run.error_count += 1
                        self._heartbeat(run, path, line_number, stats)
                        continue
                    if not isinstance(record, dict):
                        stats["invalid"] += 1
                        run.error_count += 1
                        self._heartbeat(run, path, line_number, stats)
                        continue
                    paper, conflict = self._match(record)
                    if conflict:
                        stats["conflicts"] += 1
                        run.error_count += 1
                    elif paper is None:
                        stats["unmatched"] += 1
                        run.skipped_count += 1
                    else:
                        stats["matched"] += 1
                        run.accepted_count += 1
                        if self._apply(paper, record):
                            stats["updated"] += 1
                            run.updated_count += 1
                        else:
                            stats["already_mapped"] += 1
                            run.skipped_count += 1
                    self._heartbeat(run, path, line_number, stats)

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            run.checkpoint = {
                "updated_at": datetime.now(UTC).isoformat(),
                "input": str(path),
                **stats,
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
        return SemanticScholarPaperMappingResult(run_id=str(run.id), status=run.status, **stats)

    def _load_lookup(self) -> None:
        rows = self.session.execute(
            select(
                Paper.id,
                Paper.doi,
                Paper.arxiv_id,
                Paper.pubmed_id,
                Paper.s2_id,
                Paper.s2_corpus_id,
            ).execution_options(yield_per=5000)
        )
        for paper_id, doi, arxiv_id, pubmed_id, s2_id, corpus_id in rows:
            if normalized_doi := normalize_doi(doi):
                self._doi[normalized_doi] = paper_id
            if normalized_arxiv := normalize_arxiv_id(arxiv_id):
                self._arxiv[normalized_arxiv] = paper_id
            if pubmed_id:
                self._pubmed[pubmed_id] = paper_id
            if s2_id:
                self._s2[s2_id] = paper_id
            if corpus_id:
                self._corpus[corpus_id] = paper_id

    def _match(self, record: dict[str, object]) -> tuple[Paper | None, bool]:
        external = record.get("externalids") or record.get("externalIds") or {}
        external = external if isinstance(external, dict) else {}
        paper_id, corpus_id = semantic_scholar_ids(record)
        candidates: set[object] = set()

        doi = normalize_doi(_str_or_none(external.get("DOI") or external.get("doi")))
        arxiv = normalize_arxiv_id(_str_or_none(external.get("ArXiv") or external.get("arxiv")))
        pubmed = _str_or_none(external.get("PubMed") or external.get("PMID") or external.get("pubmed"))
        for value, lookup in (
            (doi, self._doi),
            (arxiv, self._arxiv),
            (pubmed, self._pubmed),
            (paper_id, self._s2),
            (corpus_id, self._corpus),
        ):
            if value and value in lookup:
                candidates.add(lookup[value])
        if len(candidates) > 1:
            return None, True
        if not candidates:
            return None, False
        return self.session.get(Paper, next(iter(candidates))), False

    def _apply(self, paper: Paper, record: dict[str, object]) -> bool:
        paper_id, corpus_id = semantic_scholar_ids(record)
        if paper_id and paper.s2_id and paper.s2_id != paper_id:
            return False
        if corpus_id and paper.s2_corpus_id and paper.s2_corpus_id != corpus_id:
            return False
        if paper_id and paper_id in self._s2 and self._s2[paper_id] != paper.id:
            return False
        if corpus_id and corpus_id in self._corpus and self._corpus[corpus_id] != paper.id:
            return False

        changed = False
        if paper_id and not paper.s2_id:
            paper.s2_id = paper_id
            self._s2[paper_id] = paper.id
            changed = True
        if corpus_id and not paper.s2_corpus_id:
            paper.s2_corpus_id = corpus_id
            self._corpus[corpus_id] = paper.id
            changed = True

        provenance = dict(paper.provenance or {})
        snapshot = {
            "paper_id": paper_id,
            "corpus_id": corpus_id,
            "citation_count": _int_or_none(record.get("citationcount") or record.get("citationCount")),
            "reference_count": _int_or_none(record.get("referencecount") or record.get("referenceCount")),
            "is_open_access": record.get("isopenaccess") if "isopenaccess" in record else record.get("isOpenAccess"),
            "source": "Semantic Scholar Academic Graph papers dump",
        }
        if provenance.get("semantic_scholar_dump") != snapshot:
            provenance["semantic_scholar_dump"] = snapshot
            paper.provenance = provenance
            changed = True
        if changed:
            paper.retrieved_at = datetime.now(UTC)
        return changed

    def _heartbeat(
        self,
        run: IngestionRun,
        path: Path,
        line_number: int,
        stats: dict[str, int],
    ) -> None:
        if stats["records_scanned"] % self.commit_every:
            return
        run.checkpoint = {
            "updated_at": datetime.now(UTC).isoformat(),
            "input": str(path),
            "line": line_number,
            "records_scanned": stats["records_scanned"],
            "matched": stats["matched"],
            "updated": stats["updated"],
        }
        self.session.commit()


def _open_maybe_gzip(path: Path) -> BinaryIO:
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
