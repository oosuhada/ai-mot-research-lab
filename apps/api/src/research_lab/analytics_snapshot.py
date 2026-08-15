from __future__ import annotations

import importlib
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session


class DuckDBConnection(Protocol):
    def execute(self, query: str, parameters: Any = None) -> DuckDBConnection: ...

    def executemany(self, query: str, parameters: list[tuple[Any, ...]]) -> DuckDBConnection: ...

    def close(self) -> None: ...


def build_analytics_snapshot(session: Session, output: Path) -> dict[str, Any]:
    """Build an atomic aggregate-only DuckDB snapshot from PostgreSQL.

    PostgreSQL remains the source of truth. The snapshot deliberately excludes paper
    text, credentials, and mutable workspace data; it is optimized for nightly trend
    analysis without adding OLAP load to production requests.
    """

    try:
        duckdb = importlib.import_module("duckdb")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install the 'analytics' extra to build DuckDB snapshots") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.unlink(missing_ok=True)
    generated_at = datetime.now(UTC)
    connection: DuckDBConnection = duckdb.connect(str(temporary))
    try:
        _create_schema(connection)
        summary = session.execute(
            text(
                """
                SELECT count(*) AS paper_count,
                       count(*) FILTER (WHERE abstract IS NOT NULL AND btrim(abstract) <> '') AS abstract_count,
                       count(*) FILTER (WHERE is_oa) AS open_access_count,
                       min(publication_year) AS min_year,
                       max(publication_year) AS max_year
                FROM papers
                """
            )
        ).one()
        full_text_count = session.execute(
            text(
                "SELECT count(*) FROM paper_content_profiles "
                "WHERE full_text_status = 'available'"
            )
        ).scalar_one()
        connection.execute(
            "INSERT INTO corpus_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
            [generated_at, *summary, full_text_count],
        )
        _copy_rows(
            connection,
            "INSERT INTO papers_by_year VALUES (?, ?, ?, ?)",
            generated_at,
            session.execute(
                text(
                    """
                    SELECT publication_year, count(*),
                           count(*) FILTER (WHERE abstract IS NOT NULL AND btrim(abstract) <> '')
                    FROM papers
                    WHERE publication_year IS NOT NULL
                    GROUP BY publication_year ORDER BY publication_year
                    """
                )
            ).all(),
        )
        _copy_rows(
            connection,
            "INSERT INTO papers_by_axis VALUES (?, ?, ?, ?)",
            generated_at,
            session.execute(
                text(
                    """
                    SELECT t.slug, t.display_name, count(DISTINCT pt.paper_id)
                    FROM topics t JOIN paper_topics pt ON pt.topic_id = t.id
                    WHERE t.kind = 'research_axis'
                    GROUP BY t.slug, t.display_name ORDER BY count(DISTINCT pt.paper_id) DESC
                    """
                )
            ).all(),
        )
        _copy_rows(
            connection,
            "INSERT INTO ingestion_activity VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            generated_at,
            session.execute(
                text(
                    """
                    SELECT source, status, count(*), coalesce(sum(fetched_count), 0),
                           coalesce(sum(accepted_count), 0), coalesce(sum(inserted_count), 0),
                           coalesce(sum(skipped_count), 0)
                    FROM ingestion_runs
                    GROUP BY source, status ORDER BY source, status
                    """
                )
            ).all(),
        )
        connection.execute("CHECKPOINT")
    finally:
        connection.close()
    temporary.replace(output)
    return {
        "output": str(output),
        "generated_at": generated_at.isoformat(),
        "paper_count": int(summary.paper_count),
        "abstract_count": int(summary.abstract_count),
        "full_text_count": int(full_text_count),
    }


def _create_schema(connection: DuckDBConnection) -> None:
    connection.execute(
        """
        CREATE TABLE corpus_summary (
            generated_at TIMESTAMPTZ, paper_count BIGINT, abstract_count BIGINT,
            open_access_count BIGINT, min_year INTEGER, max_year INTEGER, full_text_count BIGINT
        );
        CREATE TABLE papers_by_year (
            generated_at TIMESTAMPTZ, publication_year INTEGER,
            paper_count BIGINT, abstract_count BIGINT
        );
        CREATE TABLE papers_by_axis (
            generated_at TIMESTAMPTZ, axis_slug VARCHAR, axis_name VARCHAR, paper_count BIGINT
        );
        CREATE TABLE ingestion_activity (
            generated_at TIMESTAMPTZ, source VARCHAR, status VARCHAR, run_count BIGINT,
            fetched BIGINT, accepted BIGINT, inserted BIGINT, skipped BIGINT
        );
        """
    )


def _copy_rows(
    connection: DuckDBConnection,
    statement: str,
    generated_at: datetime,
    rows: Iterable[Any],
) -> None:
    values = [(generated_at, *tuple(row)) for row in rows]
    if values:
        connection.executemany(statement, values)
