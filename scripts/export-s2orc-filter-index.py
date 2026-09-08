#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

from sqlalchemy import exists, select

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(API_SRC))

from research_lab.db import SessionLocal  # noqa: E402
from research_lab.ingestion.normalization import normalize_arxiv_id, normalize_doi  # noqa: E402
from research_lab.models import Paper, PaperChunk  # noqa: E402


def export_index(output: Path) -> dict[str, int | str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    rows = identifiers = 0
    with SessionLocal() as session, gzip.open(temp, "wt", encoding="utf-8", newline="") as stream:
        statement = (
            select(Paper.doi, Paper.arxiv_id, Paper.s2_id, Paper.s2_corpus_id)
            .where(~exists(select(PaperChunk.id).where(PaperChunk.paper_id == Paper.id)))
            .execution_options(yield_per=5000)
        )
        for doi, arxiv_id, s2_id, corpus_id in session.execute(statement):
            normalized = (
                normalize_doi(doi) or "",
                normalize_arxiv_id(arxiv_id) or "",
                str(s2_id or ""),
                str(corpus_id or ""),
            )
            if not any(normalized):
                continue
            stream.write("\t".join(normalized) + "\n")
            rows += 1
            identifiers += sum(bool(value) for value in normalized)
    temp.replace(output)
    return {"output": str(output), "rows": rows, "identifiers": identifiers}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export unresolved paper IDs for remote S2ORC filtering")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_index(args.output)
    print(f"rows={result['rows']} identifiers={result['identifiers']} output={result['output']}")


if __name__ == "__main__":
    main()
