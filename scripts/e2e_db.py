from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from research_lab.corpus_intelligence import refresh_corpus_intelligence
from research_lab.embeddings import LocalHashEmbeddingProvider
from research_lab.models import (
    Author,
    Paper,
    PaperAuthor,
    PaperContentProfile,
    PaperEmbedding,
    PaperLocalization,
    PaperTopic,
    Topic,
    Venue,
)
from research_lab.taxonomy import ADOPTION_SUBAXES
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
DEFAULT_DATABASE_URL = "postgresql+psycopg://research:research@127.0.0.1:55432/research_lab_e2e"
SAFE_DATABASE_NAME = re.compile(r"^[A-Za-z0-9_]+_e2e$")


def database_url() -> str:
    return os.environ.get("E2E_DATABASE_URL", DEFAULT_DATABASE_URL)


def require_safe_database_name(url: str) -> str:
    name = make_url(url).database or ""
    if not SAFE_DATABASE_NAME.fullmatch(name):
        raise RuntimeError(f"Refusing E2E database operation for unsafe database name: {name!r}")
    return name


def admin_url(url: str) -> str:
    parsed = make_url(url)
    return parsed.set(database="postgres").render_as_string(hide_password=False)


def recreate_database(url: str) -> None:
    name = require_safe_database_name(url)
    engine = create_engine(admin_url(url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    finally:
        engine.dispose()


def drop_database(url: str) -> None:
    name = require_safe_database_name(url)
    engine = create_engine(admin_url(url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        engine.dispose()


def migrate(url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    env["APP_ENVIRONMENT"] = "test"
    env["READ_ONLY_MODE"] = "false"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        check=True,
    )


def seed(url: str) -> None:
    engine = create_engine(url)
    provider = LocalHashEmbeddingProvider()
    now = datetime.now(UTC)
    venue = Venue(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "e2e:venue"),
        name="E2E Research Journal",
        publisher="E2E Publisher",
        venue_type="journal",
    )
    author = Author(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "e2e:author"),
        display_name="E2E Researcher",
    )
    axis = Topic(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "e2e:axis"),
        slug="ai-adoption-business-value",
        display_name="AI adoption and business value",
        kind="research_axis",
        source="e2e_fixture",
    )
    methodology = Topic(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "e2e:methodology"),
        slug="methodology-case-study",
        display_name="Case study",
        kind="methodology",
        source="e2e_fixture",
    )
    subaxes = [
        Topic(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"e2e:subaxis:{definition.slug}"),
            slug=definition.slug,
            display_name=definition.display_name,
            kind="research_subaxis",
            source="e2e_fixture",
            parent_topic_id=axis.id,
        )
        for definition in ADOPTION_SUBAXES
    ]
    subaxis = next(topic for topic in subaxes if topic.slug == "ai-capability-development")

    try:
        with Session(engine) as session:
            session.add_all([venue, author, axis, methodology, *subaxes])
            session.flush()
            for index in range(1, 126):
                paper_id = uuid.uuid5(uuid.NAMESPACE_URL, f"e2e:paper:{index:03d}")
                year = 2020 + (index % 5)
                title = f"AI capability and innovation performance E2E paper {index:03d}"
                abstract = (
                    "AI capability and innovation performance are examined in an organizational change context. "
                    f"This deterministic E2E fixture is paper {index:03d} and supports retrieval workflow tests."
                )
                paper = Paper(
                    id=paper_id,
                    doi=f"10.9999/e2e.{index:03d}",
                    openalex_id=f"E2EW{index:06d}",
                    title=title,
                    abstract=abstract,
                    publication_date=date(year, 1, 1),
                    publication_year=year,
                    language="en",
                    work_type="article",
                    venue_id=venue.id,
                    publisher=venue.publisher,
                    oa_status="gold" if index % 2 == 0 else "closed",
                    is_oa=index % 2 == 0,
                    primary_url=f"https://example.invalid/e2e/{index:03d}",
                    primary_source="e2e_fixture",
                    source_record_id=f"e2e-{index:03d}",
                    retrieved_at=now,
                    provenance={"fixture": True, "index": index},
                )
                session.add(paper)
                session.add(PaperAuthor(paper_id=paper_id, author_id=author.id, author_position=1))
                session.add(
                    PaperTopic(
                        paper_id=paper_id,
                        topic_id=axis.id,
                        score=1.0,
                        assignment_source="e2e_fixture",
                    )
                )
                session.add(
                    PaperTopic(
                        paper_id=paper_id,
                        topic_id=subaxis.id,
                        score=1.0,
                        assignment_source="e2e_fixture",
                    )
                )
                session.add(
                    PaperContentProfile(
                        paper_id=paper_id,
                        abstract_status="available",
                        full_text_status="queued" if paper.is_oa else "restricted",
                        full_text_access="open_access" if paper.is_oa else "paywalled",
                        rights_status="open_access" if paper.is_oa else "unknown",
                        full_text_priority=60 if paper.is_oa else 0,
                        abstract_updated_at=now,
                    )
                )
                if index == 1:
                    session.add(
                        PaperLocalization(
                            paper_id=paper_id,
                            locale="ko",
                            title="AI 역량과 혁신 성과 E2E 논문 001",
                            abstract="AI 역량과 혁신 성과를 조직 변화의 맥락에서 분석한다.",
                            keywords=["AI 역량", "혁신 성과"],
                            status="completed",
                            source_hash="e2e-localization",
                            provider="e2e_fixture",
                            translated_at=now,
                        )
                    )
                if index % 2 == 0:
                    session.add(
                        PaperTopic(
                            paper_id=paper_id,
                            topic_id=methodology.id,
                            score=1.0,
                            assignment_source="e2e_fixture",
                        )
                    )
                session.add(
                    PaperEmbedding(
                        paper_id=paper_id,
                        provider=provider.name,
                        model=provider.model,
                        dimensions=provider.dimensions,
                        embedding=provider.embed_document(f"{title}\n{abstract}"),
                    )
                )
            session.commit()
            refresh_corpus_intelligence(session, discovery_days=3650)
    finally:
        engine.dispose()


def setup() -> None:
    url = database_url()
    recreate_database(url)
    migrate(url)
    seed(url)
    print(f"E2E database ready: {make_url(url).database}")


def cleanup() -> None:
    url = database_url()
    drop_database(url)
    print(f"E2E database removed: {make_url(url).database}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create, seed, or remove the isolated Playwright database.")
    parser.add_argument("command", choices=("setup", "cleanup"))
    args = parser.parse_args()
    if args.command == "setup":
        setup()
    else:
        cleanup()


if __name__ == "__main__":
    main()
