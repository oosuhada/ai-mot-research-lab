from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[3] / "scripts/run-s2orc-remote-worker.py"
SPEC = importlib.util.spec_from_file_location("s2orc_remote_worker", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_filter_lines_keeps_only_matching_records(tmp_path: Path) -> None:
    index_path = tmp_path / "index.tsv.gz"
    with gzip.open(index_path, "wt", encoding="utf-8") as stream:
        stream.write("10.1000/example\t\t98765\ts2-1\t12345\n")
    index = MODULE.load_index(index_path)
    records = [
        {"corpusId": 12345, "text": "match"},
        {"externalIds": {"DOI": "10.9999/nope"}, "text": "skip"},
        {"externalIds": {"DOI": "https://doi.org/10.1000/EXAMPLE"}, "text": "match doi"},
    ]
    output = tmp_path / "matched.jsonl.gz"
    lines = [(json.dumps(record) + "\n").encode() for record in records]

    scanned, matched, invalid = MODULE.filter_lines(lines, index, output)

    assert (scanned, matched, invalid) == (3, 2, 0)
    with gzip.open(output, "rt", encoding="utf-8") as stream:
        kept = [json.loads(line) for line in stream]
    assert [record["text"] for record in kept] == ["match", "match doi"]


def test_arxiv_normalization_matches_versioned_record(tmp_path: Path) -> None:
    index_path = tmp_path / "index.tsv.gz"
    with gzip.open(index_path, "wt", encoding="utf-8") as stream:
        stream.write("\t2306.10134\t\t\n")
    index = MODULE.load_index(index_path)
    record = {"externalIds": {"ArXiv": "arXiv:2306.10134v3"}}

    assert MODULE.record_matches(record, index) is True


def test_pubmed_identifier_matches_papers_dump_record(tmp_path: Path) -> None:
    index_path = tmp_path / "index.tsv.gz"
    with gzip.open(index_path, "wt", encoding="utf-8") as stream:
        stream.write("\t\t12345678\t\t\n")
    index = MODULE.load_index(index_path)

    assert MODULE.record_matches({"externalids": {"PubMed": "12345678"}}, index) is True
