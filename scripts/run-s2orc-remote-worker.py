#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

DOI_PREFIX_PATTERN = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
ARXIV_PREFIX_PATTERN = re.compile(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)", re.IGNORECASE)
ARXIV_VERSION_PATTERN = re.compile(r"v\d+$", re.IGNORECASE)


@dataclass(slots=True)
class FilterIndex:
    doi: set[str]
    arxiv: set[str]
    pubmed: set[str]
    s2: set[str]
    corpus: set[str]


@dataclass(slots=True)
class WorkerResult:
    shard_id: str
    mode: str
    records_scanned: int
    records_matched: int
    invalid_records: int
    bundle_path: str
    bundle_bytes: int
    bundle_sha256: str
    raw_path: str | None = None
    raw_bytes: int | None = None
    raw_sha256: str | None = None


def normalize_doi(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = DOI_PREFIX_PATTERN.sub("", value.strip()).strip().lower()
    return normalized or None


def normalize_arxiv_id(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = ARXIV_PREFIX_PATTERN.sub("", value.strip()).strip()
    if normalized.lower().endswith(".pdf"):
        normalized = normalized[:-4]
    normalized = ARXIV_VERSION_PATTERN.sub("", normalized)
    return normalized or None


def load_index(path: Path) -> FilterIndex:
    values = FilterIndex(set(), set(), set(), set(), set())
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            fields = line.rstrip("\n").split("\t")
            if len(fields) == 4:
                doi, arxiv, s2, corpus = fields
                pubmed = ""
            elif len(fields) == 5:
                doi, arxiv, pubmed, s2, corpus = fields
            else:
                continue
            if doi:
                values.doi.add(doi)
            if arxiv:
                values.arxiv.add(arxiv)
            if pubmed:
                values.pubmed.add(pubmed)
            if s2:
                values.s2.add(s2)
            if corpus:
                values.corpus.add(corpus)
    return values


def record_matches(record: dict[str, object], index: FilterIndex) -> bool:
    open_access_info = record.get("openaccessinfo") or record.get("openAccessInfo") or {}
    nested_external = (
        open_access_info.get("externalids") or open_access_info.get("externalIds") or {}
        if isinstance(open_access_info, dict)
        else {}
    )
    external = record.get("externalids") or record.get("externalIds") or nested_external or {}
    external = external if isinstance(external, dict) else {}
    doi = normalize_doi(external.get("DOI") or external.get("doi") or record.get("doi"))
    if doi and doi in index.doi:
        return True
    arxiv = normalize_arxiv_id(external.get("ArXiv") or external.get("arxiv") or record.get("arxiv_id"))
    if arxiv and arxiv in index.arxiv:
        return True
    pubmed = external.get("PubMed") or external.get("PMID") or external.get("pubmed")
    if pubmed is not None and str(pubmed) in index.pubmed:
        return True
    for value in (record.get("paperId"), record.get("paper_id")):
        if value is not None and str(value) in index.s2:
            return True
    for value in (record.get("corpusid"), record.get("corpusId")):
        if value is not None and str(value) in index.corpus:
            return True
    return False


def filter_lines(lines: Iterable[bytes], index: FilterIndex, output: Path) -> tuple[int, int, int]:
    scanned = matched = invalid = 0
    temp = output.with_suffix(output.suffix + ".tmp")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with gzip.open(temp, "wb", compresslevel=6) as target:
            for raw_line in lines:
                scanned += 1
                try:
                    record = json.loads(raw_line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    invalid += 1
                    continue
                if not isinstance(record, dict) or not record_matches(record, index):
                    continue
                target.write(raw_line.rstrip(b"\n") + b"\n")
                matched += 1
        temp.replace(output)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return scanned, matched, invalid


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _curl_download(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    config_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, dir=output.parent, prefix=".url-", suffix=".conf") as cfg:
            config_path = Path(cfg.name)
            os.chmod(config_path, 0o600)
            escaped = url.replace("\\", "\\\\").replace('"', '\\"')
            cfg.write(f'url = "{escaped}"\n')
        subprocess.run(
            [
                "/usr/bin/curl",
                "-L",
                "--fail",
                "--retry",
                "12",
                "--retry-delay",
                "10",
                "-C",
                "-",
                "-o",
                str(output),
                "--config",
                str(config_path),
            ],
            check=True,
        )
    finally:
        if config_path is not None:
            config_path.unlink(missing_ok=True)


def _stream_url(url: str) -> BinaryIO:
    request = urllib.request.Request(url, headers={"User-Agent": "ai-mot-s2orc-stream-worker/1.0"})
    return urllib.request.urlopen(request, timeout=90)  # type: ignore[return-value]


def run_worker(
    *,
    dataset: str,
    shard_id: str,
    mode: str,
    url_file: Path,
    index_path: Path,
    work_root: Path,
) -> WorkerResult:
    url = url_file.read_text(encoding="utf-8").strip()
    if not url.startswith("http"):
        raise RuntimeError("URL file does not contain an HTTP(S) URL")
    index = load_index(index_path)
    bundle = work_root / "bundles" / f"{dataset}-{shard_id}.matched.jsonl.gz"
    raw: Path | None = None
    scanned = matched = invalid = 0

    if mode == "cache":
        raw = work_root / "raw" / f"{dataset}-{shard_id}.jsonl.gz"
        _curl_download(url, raw)
        with gzip.open(raw, "rb") as stream:
            scanned, matched, invalid = filter_lines(stream, index, bundle)
    elif mode == "stream":
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                with _stream_url(url) as response, gzip.GzipFile(fileobj=response) as stream:
                    scanned, matched, invalid = filter_lines(stream, index, bundle)
                last_error = None
                break
            except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
                last_error = exc
                bundle.unlink(missing_ok=True)
                time.sleep(min(5 * (2 ** (attempt - 1)), 60))
        if last_error is not None:
            raise last_error
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    result = WorkerResult(
        shard_id=shard_id,
        mode=mode,
        records_scanned=scanned,
        records_matched=matched,
        invalid_records=invalid,
        bundle_path=str(bundle),
        bundle_bytes=bundle.stat().st_size,
        bundle_sha256=sha256_file(bundle),
        raw_path=str(raw) if raw else None,
        raw_bytes=raw.stat().st_size if raw else None,
        raw_sha256=sha256_file(raw) if raw else None,
    )
    manifest = work_root / "bundles" / f"{dataset}-{shard_id}.manifest.json"
    manifest.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    url_file.unlink(missing_ok=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download/stream and exact-filter one Semantic Scholar dataset shard"
    )
    parser.add_argument("--dataset", choices=("s2orc_v2", "papers"), default="s2orc_v2")
    parser.add_argument("--shard-id", required=True)
    parser.add_argument("--mode", choices=("cache", "stream"), required=True)
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    result = run_worker(
        dataset=args.dataset,
        shard_id=args.shard_id,
        mode=args.mode,
        url_file=args.url_file,
        index_path=args.index,
        work_root=args.work_root,
    )
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
