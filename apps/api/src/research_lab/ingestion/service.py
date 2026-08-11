from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from research_lab.citation_graph import resolve_local_citation_edges
from research_lab.config import Settings
from research_lab.embeddings import EmbeddingProvider, build_embedding_provider
from research_lab.ingestion.normalization import (
    normalize_openalex_id,
    normalize_orcid,
    normalize_ror,
)
from research_lab.ingestion.openalex import OpenAlexClient, OpenAlexRecord
from research_lab.models import (
    Author,
    AuthorInstitution,
    Citation,
    CitationSnapshot,
    IngestionRun,
    Institution,
    Paper,
    PaperAuthor,
    PaperEmbedding,
    PaperTopic,
    PaperVersion,
    Topic,
    Venue,
)
from research_lab.taxonomy import (
    METHODOLOGY_TAXONOMY_VERSION,
    RESEARCH_AXES,
    TAXONOMY_VERSION,
    ResearchAxis,
    infer_methodology_labels,
    text_matches_axis,
)


@dataclass(slots=True)
class AxisStats:
    slug: str
    fetched: int = 0
    accepted: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


@dataclass(slots=True)
class IngestionResult:
    run_id: uuid.UUID
    status: str
    corpus_count: int
    fetched_count: int
    accepted_count: int
    inserted_count: int
    updated_count: int
    skipped_count: int
    error_count: int
    axis_stats: list[AxisStats]
    manifest_path: str


class OpenAlexIngestionService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        client: OpenAlexClient | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.client = client or OpenAlexClient(settings)
        self._owns_client = client is None
        self.embedding_provider = embedding_provider or build_embedding_provider(settings)

        self.papers_by_doi: dict[str, Paper] = {}
        self.papers_by_openalex: dict[str, Paper] = {}
        self.venues_by_openalex: dict[str, Venue] = {}
        self.authors_by_openalex: dict[str, Author] = {}
        self.institutions_by_openalex: dict[str, Institution] = {}
        self.topics_by_slug: dict[str, Topic] = {}
        self.author_institution_keys: set[tuple[uuid.UUID, uuid.UUID, str]] = set()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def ingest_seed(self, *, target: int = 600, from_year: int = 2018) -> IngestionResult:
        self._load_caches()
        self._ensure_axis_topics()

        run = IngestionRun(
            source="openalex",
            status="running",
            taxonomy_version=TAXONOMY_VERSION,
            query_spec={
                "target_minimum": target,
                "from_year": from_year,
                "axes": [
                    {"slug": axis.slug, "query": axis.openalex_query} for axis in RESEARCH_AXES
                ],
                "embedding_provider": self.embedding_provider.name,
                "embedding_model": self.embedding_provider.model,
            },
            checkpoint={},
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)

        retrieved_at = datetime.now(UTC)
        axis_stats: list[AxisStats] = []

        try:
            for axis in RESEARCH_AXES:
                stats = self._ingest_axis(
                    run,
                    axis,
                    target=self._axis_target(target, axis),
                    from_year=from_year,
                    retrieved_at=retrieved_at,
                )
                axis_stats.append(stats)

            resolve_local_citation_edges(self.session)

            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            persisted_run = self.session.get(IngestionRun, run.id)
            if persisted_run is not None:
                persisted_run.status = "failed"
                persisted_run.error_count += 1
                persisted_run.error_message = f"{type(exc).__name__}: {exc}"
                persisted_run.finished_at = datetime.now(UTC)
                self.session.commit()
            raise
        finally:
            self.close()

        corpus_count = self.session.scalar(select(func.count()).select_from(Paper)) or 0
        manifest_path = self._write_manifest(run, axis_stats, corpus_count)

        return IngestionResult(
            run_id=run.id,
            status=run.status,
            corpus_count=corpus_count,
            fetched_count=run.fetched_count,
            accepted_count=run.accepted_count,
            inserted_count=run.inserted_count,
            updated_count=run.updated_count,
            skipped_count=run.skipped_count,
            error_count=run.error_count,
            axis_stats=axis_stats,
            manifest_path=str(manifest_path),
        )

    def _axis_target(self, target: int, axis: ResearchAxis) -> int:
        if axis.slug == "agentic-enterprise-workflows":
            return max(10, math.ceil(target * 0.12))
        return max(10, math.ceil(target * 0.22))

    def _ingest_axis(
        self,
        run: IngestionRun,
        axis: ResearchAxis,
        *,
        target: int,
        from_year: int,
        retrieved_at: datetime,
    ) -> AxisStats:
        stats = AxisStats(slug=axis.slug)
        max_candidates = max(target * 4, 300)

        for record in self.client.iter_axis_records(
            axis,
            max_records=max_candidates,
            from_year=from_year,
        ):
            stats.fetched += 1
            run.fetched_count += 1

            if not self._is_in_scope(record, axis, from_year):
                stats.skipped += 1
                run.skipped_count += 1
                self._checkpoint(run, axis, stats)
                continue

            inserted = self._upsert_record(record, axis, retrieved_at)
            stats.accepted += 1
            run.accepted_count += 1
            if inserted:
                stats.inserted += 1
                run.inserted_count += 1
            else:
                stats.updated += 1
                run.updated_count += 1

            self._checkpoint(run, axis, stats)

            if stats.accepted >= target:
                break

        self.session.commit()
        return stats

    def _checkpoint(self, run: IngestionRun, axis: ResearchAxis, stats: AxisStats) -> None:
        run.checkpoint = {
            "axis": axis.slug,
            "axis_fetched": stats.fetched,
            "axis_accepted": stats.accepted,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if stats.fetched % 25 == 0:
            self.session.commit()

    def _is_in_scope(self, record: OpenAlexRecord, axis: ResearchAxis, from_year: int) -> bool:
        if record.publication_year is not None and record.publication_year < from_year:
            return False
        text = f"{record.title}\n{record.abstract or ''}"
        return text_matches_axis(text, axis)

    def _upsert_record(
        self,
        record: OpenAlexRecord,
        axis: ResearchAxis | None,
        retrieved_at: datetime,
    ) -> bool:
        paper = self._find_paper(record)
        inserted = paper is None
        venue = self._upsert_venue(record.venue)

        if paper is None:
            paper = Paper(
                doi=record.doi,
                openalex_id=record.source_record_id,
                title=record.title,
                abstract=record.abstract,
                publication_date=record.publication_date,
                publication_year=record.publication_year,
                language=record.language,
                work_type=record.work_type,
                venue_id=venue.id if venue else None,
                publisher=record.publisher,
                oa_status=record.oa_status,
                is_oa=record.is_oa,
                primary_url=record.primary_url,
                pdf_url=record.pdf_url,
                retraction_status="retracted" if record.is_retracted else "none",
                correction_status="none",
                license=record.license,
                primary_source="openalex",
                source_record_id=record.source_record_id,
                retrieved_at=retrieved_at,
                provenance={
                    "openalex": {
                        "source_record_ids": [record.source_record_id],
                        "retrieved_at": retrieved_at.isoformat(),
                        "license": "CC0 metadata",
                    }
                },
            )
            self.session.add(paper)
            self.session.flush()
        else:
            self._merge_openalex_fields(paper, record, venue, retrieved_at)

        if record.doi:
            self.papers_by_doi[record.doi] = paper
        self.papers_by_openalex[record.source_record_id] = paper

        if axis is not None:
            self._upsert_axis_topic(paper, axis)
        self._upsert_openalex_topics(paper, record.topics)
        self._upsert_methodology_topics(paper)
        self._replace_openalex_authorships(paper, record.authorships)
        self._upsert_external_citations(paper, record.referenced_works)
        self._snapshot_citations(paper, record, retrieved_at)
        self._upsert_version(paper, record, retrieved_at)
        self._upsert_embedding(paper)
        return inserted

    def upsert_openalex_record(
        self,
        record: OpenAlexRecord,
        *,
        retrieved_at: datetime | None = None,
    ) -> tuple[Paper, bool]:
        """Merge a single provider record without assigning a research axis.

        This is used by explicit DOI imports. Research-axis membership remains a separate
        local taxonomy decision rather than an implicit side effect of resolving a DOI.
        """
        self._load_caches()
        self._ensure_axis_topics()
        resolved_at = retrieved_at or datetime.now(UTC)
        inserted = self._upsert_record(record, None, resolved_at)
        paper = self._find_paper(record)
        if paper is None:
            raise RuntimeError("OpenAlex upsert did not produce a canonical paper")
        self.session.commit()
        return paper, inserted

    def _find_paper(self, record: OpenAlexRecord) -> Paper | None:
        doi_match = self.papers_by_doi.get(record.doi) if record.doi else None
        openalex_match = self.papers_by_openalex.get(record.source_record_id)

        if doi_match is not None and openalex_match is not None and doi_match.id != openalex_match.id:
            raise ValueError(
                "Strong identifier collision: "
                f"DOI {record.doi} and OpenAlex {record.source_record_id} map to different papers"
            )
        return doi_match or openalex_match

    def _merge_openalex_fields(
        self,
        paper: Paper,
        record: OpenAlexRecord,
        venue: Venue | None,
        retrieved_at: datetime,
    ) -> None:
        if paper.doi and record.doi and paper.doi != record.doi:
            raise ValueError(f"DOI collision for paper {paper.id}")

        if (
            paper.openalex_id
            and paper.openalex_id != record.source_record_id
            and (not paper.doi or not record.doi or paper.doi != record.doi)
        ):
            raise ValueError(f"OpenAlex identifier collision for paper {paper.id}")

        paper.openalex_id = paper.openalex_id or record.source_record_id
        paper.doi = paper.doi or record.doi
        paper.title = record.title or paper.title
        paper.abstract = record.abstract or paper.abstract
        paper.publication_date = record.publication_date or paper.publication_date
        paper.publication_year = record.publication_year or paper.publication_year
        paper.language = record.language or paper.language
        paper.work_type = record.work_type or paper.work_type
        paper.venue_id = venue.id if venue else paper.venue_id
        paper.publisher = record.publisher or paper.publisher
        paper.oa_status = record.oa_status
        paper.is_oa = record.is_oa
        paper.primary_url = record.primary_url or paper.primary_url
        paper.pdf_url = record.pdf_url or paper.pdf_url
        paper.retraction_status = "retracted" if record.is_retracted else paper.retraction_status
        paper.license = record.license or paper.license
        paper.retrieved_at = retrieved_at
        provenance = dict(paper.provenance or {})
        existing_openalex = provenance.get("openalex")
        openalex_metadata = dict(existing_openalex) if isinstance(existing_openalex, dict) else {}
        source_record_ids = set(openalex_metadata.get("source_record_ids") or [])
        legacy_source_record_id = openalex_metadata.get("source_record_id")
        if isinstance(legacy_source_record_id, str):
            source_record_ids.add(legacy_source_record_id)
        if paper.openalex_id:
            source_record_ids.add(paper.openalex_id)
        source_record_ids.add(record.source_record_id)
        provenance["openalex"] = {
            "source_record_ids": sorted(source_record_ids),
            "retrieved_at": retrieved_at.isoformat(),
            "license": "CC0 metadata",
        }
        paper.provenance = provenance

    def _upsert_venue(self, raw_venue: dict[str, Any] | None) -> Venue | None:
        if not raw_venue:
            return None
        openalex_id = normalize_openalex_id(raw_venue.get("id"))
        if not openalex_id:
            return None
        venue = self.venues_by_openalex.get(openalex_id)
        if venue is None:
            venue = Venue(
                openalex_id=openalex_id,
                name=str(raw_venue.get("display_name") or "Unknown venue"),
                issn_l=raw_venue.get("issn_l"),
                publisher=raw_venue.get("host_organization_name"),
                venue_type=raw_venue.get("type"),
            )
            self.session.add(venue)
            self.session.flush()
            self.venues_by_openalex[openalex_id] = venue
        return venue

    def _replace_openalex_authorships(self, paper: Paper, authorships: list[dict[str, Any]]) -> None:
        existing = {
            row.author_id: row
            for row in self.session.scalars(select(PaperAuthor).where(PaperAuthor.paper_id == paper.id))
        }

        for position, authorship in enumerate(authorships):
            raw_author = authorship.get("author") or {}
            openalex_id = normalize_openalex_id(raw_author.get("id"))
            if not openalex_id:
                continue
            author = self.authors_by_openalex.get(openalex_id)
            if author is None:
                author = Author(
                    openalex_id=openalex_id,
                    orcid=normalize_orcid(raw_author.get("orcid")),
                    display_name=str(raw_author.get("display_name") or "Unknown author"),
                )
                self.session.add(author)
                self.session.flush()
                self.authors_by_openalex[openalex_id] = author

            raw_affiliations = authorship.get("raw_affiliation_strings") or []
            raw_affiliation = "; ".join(dict.fromkeys(raw_affiliations)) or None
            row = existing.get(author.id)
            if row is None:
                row = PaperAuthor(
                    paper_id=paper.id,
                    author_id=author.id,
                    author_position=position,
                    is_corresponding=bool(authorship.get("is_corresponding")),
                    raw_affiliation=raw_affiliation,
                )
                self.session.add(row)
                existing[author.id] = row
            else:
                row.author_position = min(row.author_position, position)
                row.is_corresponding = row.is_corresponding or bool(authorship.get("is_corresponding"))
                row.raw_affiliation = self._merge_affiliations(row.raw_affiliation, raw_affiliation)

            for raw_institution in authorship.get("institutions") or []:
                institution = self._upsert_institution(raw_institution)
                if institution is None:
                    continue
                key = (author.id, institution.id, "openalex")
                if key not in self.author_institution_keys:
                    self.session.add(
                        AuthorInstitution(
                            author_id=author.id,
                            institution_id=institution.id,
                            source="openalex",
                        )
                    )
                    self.author_institution_keys.add(key)

    @staticmethod
    def _merge_affiliations(current: str | None, incoming: str | None) -> str | None:
        values: list[str] = []
        for raw in (current, incoming):
            if not raw:
                continue
            for value in raw.split("; "):
                if value and value not in values:
                    values.append(value)
        return "; ".join(values) or None

    def _upsert_institution(self, raw: dict[str, Any]) -> Institution | None:
        openalex_id = normalize_openalex_id(raw.get("id"))
        if not openalex_id:
            return None
        institution = self.institutions_by_openalex.get(openalex_id)
        if institution is None:
            institution = Institution(
                openalex_id=openalex_id,
                ror=normalize_ror(raw.get("ror")),
                name=str(raw.get("display_name") or "Unknown institution"),
                country_code=raw.get("country_code"),
                institution_type=raw.get("type"),
            )
            self.session.add(institution)
            self.session.flush()
            self.institutions_by_openalex[openalex_id] = institution
        return institution

    def _upsert_axis_topic(self, paper: Paper, axis: ResearchAxis) -> None:
        topic = self.topics_by_slug[axis.slug]
        link = self.session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id})
        if link is None:
            self.session.add(
                PaperTopic(
                    paper_id=paper.id,
                    topic_id=topic.id,
                    score=1.0,
                    assignment_source=f"local_taxonomy:{TAXONOMY_VERSION}",
                )
            )

    def _upsert_openalex_topics(self, paper: Paper, topics: list[dict[str, Any]]) -> None:
        for raw in topics[:3]:
            source_record_id = normalize_openalex_id(raw.get("id"))
            if not source_record_id:
                continue
            slug = f"openalex-{source_record_id.lower()}"
            topic = self.topics_by_slug.get(slug)
            if topic is None:
                topic = Topic(
                    slug=slug,
                    display_name=str(raw.get("display_name") or source_record_id),
                    kind="openalex_topic",
                    source="openalex",
                    source_record_id=source_record_id,
                )
                self.session.add(topic)
                self.session.flush()
                self.topics_by_slug[slug] = topic
            link = self.session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id})
            if link is None:
                self.session.add(
                    PaperTopic(
                        paper_id=paper.id,
                        topic_id=topic.id,
                        score=float(raw.get("score") or 0.0),
                        assignment_source="openalex",
                    )
                )

    def _upsert_methodology_topics(self, paper: Paper) -> None:
        labels = infer_methodology_labels(f"{paper.title}\n{paper.abstract or ''}")
        for label in labels:
            slug = f"methodology-{label}"
            topic = self.topics_by_slug.get(slug)
            if topic is None:
                topic = Topic(
                    slug=slug,
                    display_name=label.replace("-", " ").title(),
                    kind="methodology",
                    source="local_heuristic",
                    source_record_id=METHODOLOGY_TAXONOMY_VERSION,
                    description=(
                        "Keyword-derived coarse methodology label. Verify against the paper before treating "
                        "it as a study-design fact."
                    ),
                )
                self.session.add(topic)
                self.session.flush()
                self.topics_by_slug[slug] = topic
            link = self.session.get(PaperTopic, {"paper_id": paper.id, "topic_id": topic.id})
            if link is None:
                self.session.add(
                    PaperTopic(
                        paper_id=paper.id,
                        topic_id=topic.id,
                        score=1.0,
                        assignment_source=f"heuristic_methodology:{METHODOLOGY_TAXONOMY_VERSION}",
                    )
                )

    def backfill_methodologies(self) -> int:
        self._load_caches()
        papers = list(self.session.scalars(select(Paper)))
        for paper in papers:
            self._upsert_methodology_topics(paper)
        self.session.commit()
        return len(papers)

    def _upsert_external_citations(self, paper: Paper, references: list[str]) -> None:
        existing = set(
            self.session.scalars(
                select(Citation.cited_external_id).where(
                    Citation.citing_paper_id == paper.id,
                    Citation.source == "openalex",
                )
            )
        )
        for raw_reference in references:
            external_id = normalize_openalex_id(raw_reference)
            if not external_id or external_id in existing:
                continue
            self.session.add(
                Citation(
                    citing_paper_id=paper.id,
                    cited_external_id=external_id,
                    source="openalex",
                )
            )
            existing.add(external_id)

    def _snapshot_citations(
        self,
        paper: Paper,
        record: OpenAlexRecord,
        retrieved_at: datetime,
    ) -> None:
        snapshot = self.session.scalar(
            select(CitationSnapshot).where(
                CitationSnapshot.paper_id == paper.id,
                CitationSnapshot.source == "openalex",
                CitationSnapshot.captured_at == retrieved_at,
            )
        )
        if snapshot is None:
            self.session.add(
                CitationSnapshot(
                    paper_id=paper.id,
                    source="openalex",
                    citation_count=record.cited_by_count,
                    oa_status=record.oa_status,
                    captured_at=retrieved_at,
                )
            )

    def _upsert_version(self, paper: Paper, record: OpenAlexRecord, retrieved_at: datetime) -> None:
        raw_bytes = json.dumps(record.raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload_hash = hashlib.sha256(raw_bytes).hexdigest()
        existing = self.session.scalar(
            select(PaperVersion).where(
                PaperVersion.paper_id == paper.id,
                PaperVersion.source == "openalex",
                PaperVersion.source_record_id == record.source_record_id,
                PaperVersion.payload_hash == payload_hash,
            )
        )
        if existing is None:
            self.session.add(
                PaperVersion(
                    paper_id=paper.id,
                    source="openalex",
                    source_record_id=record.source_record_id,
                    version_label=str(record.raw.get("updated_date") or "openalex-current"),
                    retrieved_at=retrieved_at,
                    license="CC0 metadata",
                    payload_hash=payload_hash,
                    source_metadata=record.raw,
                )
            )

    def _upsert_embedding(self, paper: Paper) -> None:
        embedding = self.session.scalar(
            select(PaperEmbedding).where(
                PaperEmbedding.paper_id == paper.id,
                PaperEmbedding.provider == self.embedding_provider.name,
                PaperEmbedding.model == self.embedding_provider.model,
            )
        )
        vector = self.embedding_provider.embed_document(f"{paper.title}\n{paper.abstract or ''}")
        if embedding is None:
            self.session.add(
                PaperEmbedding(
                    paper_id=paper.id,
                    provider=self.embedding_provider.name,
                    model=self.embedding_provider.model,
                    dimensions=self.embedding_provider.dimensions,
                    embedding=vector,
                )
            )
        else:
            embedding.embedding = vector

    def _load_caches(self) -> None:
        self.papers_by_doi = {paper.doi: paper for paper in self.session.scalars(select(Paper)) if paper.doi}
        self.papers_by_openalex = {
            paper.openalex_id: paper for paper in self.session.scalars(select(Paper)) if paper.openalex_id
        }
        self.venues_by_openalex = {
            venue.openalex_id: venue
            for venue in self.session.scalars(select(Venue))
            if venue.openalex_id
        }
        self.authors_by_openalex = {
            author.openalex_id: author
            for author in self.session.scalars(select(Author))
            if author.openalex_id
        }
        self.institutions_by_openalex = {
            institution.openalex_id: institution
            for institution in self.session.scalars(select(Institution))
            if institution.openalex_id
        }
        self.topics_by_slug = {topic.slug: topic for topic in self.session.scalars(select(Topic))}
        self.author_institution_keys = set(
            self.session.execute(
                select(
                    AuthorInstitution.author_id,
                    AuthorInstitution.institution_id,
                    AuthorInstitution.source,
                )
            ).tuples()
        )

    def _ensure_axis_topics(self) -> None:
        for axis in RESEARCH_AXES:
            topic = self.topics_by_slug.get(axis.slug)
            if topic is None:
                topic = Topic(
                    slug=axis.slug,
                    display_name=axis.display_name,
                    kind="research_axis",
                    source="local_taxonomy",
                    source_record_id=TAXONOMY_VERSION,
                    description=axis.description,
                )
                self.session.add(topic)
                self.session.flush()
                self.topics_by_slug[axis.slug] = topic
        self.session.commit()

    def _write_manifest(
        self,
        run: IngestionRun,
        axis_stats: list[AxisStats],
        corpus_count: int,
    ) -> Path:
        output_dir = self.settings.artifact_root / "ingestion"
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"openalex-{run.id}.json"
        payload = {
            "run_id": str(run.id),
            "source": "OpenAlex",
            "source_license": "CC0 metadata",
            "taxonomy_version": TAXONOMY_VERSION,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "status": run.status,
            "query_spec": run.query_spec,
            "checkpoint": run.checkpoint,
            "counts": {
                "corpus": corpus_count,
                "fetched": run.fetched_count,
                "accepted": run.accepted_count,
                "inserted": run.inserted_count,
                "updated": run.updated_count,
                "skipped": run.skipped_count,
                "errors": run.error_count,
            },
            "axes": [asdict(stats) for stats in axis_stats],
            "notes": [
                "Metadata was collected through the official OpenAlex API.",
                "OA/PDF URLs are discovery metadata and are not treated as redistribution permission.",
                "The local_hash vector is a deterministic no-key retrieval baseline, not a neural semantic benchmark.",
            ],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

