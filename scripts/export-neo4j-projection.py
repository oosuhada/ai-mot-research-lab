from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps/api/src"
sys.path.insert(0, str(API_SRC))

from research_lab.db import SessionLocal
from research_lab.models import (
    Author,
    AuthorInstitution,
    Citation,
    Institution,
    Paper,
    PaperAuthor,
    PaperTopic,
    Topic,
)


def _write_rows(path: Path, header: tuple[str, ...], rows: object) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:  # type: ignore[assignment]
            writer.writerow(["" if value is None else value for value in row])
            count += 1
    return count


def export_projection(output: Path) -> dict[str, int | str]:
    output.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int | str] = {}
    with SessionLocal() as session:
        counts["papers"] = _write_rows(
            output / "papers.csv",
            (
                "paper_id:ID(Paper)",
                "title",
                "publication_year:int",
                "doi",
                "openalex_id",
                "s2_id",
                "s2_corpus_id",
                "is_oa:boolean",
                ":LABEL",
            ),
            (
                (
                    str(paper_id),
                    title,
                    publication_year,
                    doi,
                    openalex_id,
                    s2_id,
                    s2_corpus_id,
                    str(bool(is_oa)).lower(),
                    "Paper",
                )
                for paper_id, title, publication_year, doi, openalex_id, s2_id, s2_corpus_id, is_oa in session.execute(
                    select(
                        Paper.id,
                        Paper.title,
                        Paper.publication_year,
                        Paper.doi,
                        Paper.openalex_id,
                        Paper.s2_id,
                        Paper.s2_corpus_id,
                        Paper.is_oa,
                    ).execution_options(yield_per=5000)
                )
            ),
        )
        counts["authors"] = _write_rows(
            output / "authors.csv",
            ("author_id:ID(Author)", "display_name", "openalex_id", "orcid", ":LABEL"),
            (
                (str(author_id), display_name, openalex_id, orcid, "Author")
                for author_id, display_name, openalex_id, orcid in session.execute(
                    select(Author.id, Author.display_name, Author.openalex_id, Author.orcid).execution_options(
                        yield_per=5000
                    )
                )
            ),
        )
        counts["institutions"] = _write_rows(
            output / "institutions.csv",
            ("institution_id:ID(Institution)", "name", "openalex_id", "ror", "country_code", ":LABEL"),
            (
                (str(institution_id), name, openalex_id, ror, country_code, "Institution")
                for institution_id, name, openalex_id, ror, country_code in session.execute(
                    select(
                        Institution.id,
                        Institution.name,
                        Institution.openalex_id,
                        Institution.ror,
                        Institution.country_code,
                    ).execution_options(yield_per=5000)
                )
            ),
        )
        counts["topics"] = _write_rows(
            output / "topics.csv",
            ("topic_id:ID(Topic)", "slug", "display_name", "kind", "source", ":LABEL"),
            (
                (str(topic_id), slug, display_name, kind, source, "Topic")
                for topic_id, slug, display_name, kind, source in session.execute(
                    select(Topic.id, Topic.slug, Topic.display_name, Topic.kind, Topic.source).execution_options(
                        yield_per=5000
                    )
                )
            ),
        )
        counts["citations"] = _write_rows(
            output / "citations.csv",
            (":START_ID(Paper)", ":END_ID(Paper)", "source", "is_influential:boolean", ":TYPE"),
            (
                (str(citing), str(cited), source, "" if influential is None else str(bool(influential)).lower(), "CITES")
                for citing, cited, source, influential in session.execute(
                    select(
                        Citation.citing_paper_id,
                        Citation.cited_paper_id,
                        Citation.source,
                        Citation.is_influential,
                    )
                    .where(Citation.cited_paper_id.is_not(None))
                    .execution_options(yield_per=10000)
                )
            ),
        )
        counts["paper_authors"] = _write_rows(
            output / "paper_authors.csv",
            (":START_ID(Author)", ":END_ID(Paper)", "position:int", "is_corresponding:boolean", ":TYPE"),
            (
                (str(author_id), str(paper_id), position, str(bool(is_corresponding)).lower(), "AUTHORED")
                for author_id, paper_id, position, is_corresponding in session.execute(
                    select(
                        PaperAuthor.author_id,
                        PaperAuthor.paper_id,
                        PaperAuthor.author_position,
                        PaperAuthor.is_corresponding,
                    ).execution_options(yield_per=10000)
                )
            ),
        )
        counts["author_institutions"] = _write_rows(
            output / "author_institutions.csv",
            (":START_ID(Author)", ":END_ID(Institution)", "source", ":TYPE"),
            (
                (str(author_id), str(institution_id), source, "AFFILIATED_WITH")
                for author_id, institution_id, source in session.execute(
                    select(
                        AuthorInstitution.author_id,
                        AuthorInstitution.institution_id,
                        AuthorInstitution.source,
                    ).execution_options(yield_per=10000)
                )
            ),
        )
        counts["paper_topics"] = _write_rows(
            output / "paper_topics.csv",
            (":START_ID(Paper)", ":END_ID(Topic)", "score:float", "assignment_source", ":TYPE"),
            (
                (str(paper_id), str(topic_id), score, assignment_source, "HAS_TOPIC")
                for paper_id, topic_id, score, assignment_source in session.execute(
                    select(
                        PaperTopic.paper_id,
                        PaperTopic.topic_id,
                        PaperTopic.score,
                        PaperTopic.assignment_source,
                    ).execution_options(yield_per=10000)
                )
            ),
        )

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "projection": "ai-mot-research-graph-v1",
        "authoritative_source": "postgresql",
        "includes_unresolved_external_citations": False,
        **counts,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the canonical PostgreSQL corpus as a Neo4j read-model projection")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_projection(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
