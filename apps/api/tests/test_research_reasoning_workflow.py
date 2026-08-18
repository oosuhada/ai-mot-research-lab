from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from research_lab.models import (
    ComparisonSet,
    GapAnalysis,
    Paper,
    PaperChunk,
    PaperResearchCard,
    ResearchDesign,
    ResearchDirection,
    ResearchQuestion,
    ResearchQuestionComparisonSet,
    ResearchQuestionPaper,
)
from research_lab.research_workflow import (
    build_question_workspace,
    build_research_proposal,
    create_research_direction,
    get_paper_research_card,
    persist_paper_research_card,
    update_paper_research_card,
    update_question_paper,
    upsert_research_design,
)
from research_lab.schemas import (
    PaperResearchCardUpdate,
    ResearchCardFieldUpdate,
    ResearchDesignUpdate,
    ResearchDirectionCreate,
    ResearchQuestionPaperUpdate,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Paper.__table__,
        PaperChunk.__table__,
        ResearchQuestion.__table__,
        ResearchQuestionPaper.__table__,
        PaperResearchCard.__table__,
        ComparisonSet.__table__,
        ResearchQuestionComparisonSet.__table__,
        GapAnalysis.__table__,
        ResearchDirection.__table__,
        ResearchDesign.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _paper() -> Paper:
    return Paper(
        title="AI capability and innovation performance",
        abstract=(
            "This study examines how artificial intelligence capability affects innovation performance. "
            "Drawing on dynamic capabilities, we use a survey of 214 manufacturing firms and structural "
            "equation modeling. Results show that organizational readiness mediates the relationship. "
            "A limitation is the single-country cross-sectional sample. Future research should test the "
            "model with longitudinal multi-country data."
        ),
        publication_year=2025,
        primary_source="openalex",
        source_record_id="W-RESEARCH-CARD",
        retrieved_at=datetime.now(UTC),
        provenance={},
    )


def test_research_card_preview_persists_and_marks_human_verified_fields() -> None:
    with _session() as session:
        paper = _paper()
        session.add(paper)
        session.commit()

        preview = get_paper_research_card(session, paper.id)
        assert preview.persisted is False
        assert preview.evidence_depth == "abstract"
        assert preview.fields["research_question"].support_status == "supported"
        assert "dynamic capabilities" in (preview.fields["theoretical_lens"].value_text or "")
        assert "survey" in (preview.fields["methodology"].value_text or "")

        persisted = persist_paper_research_card(session, paper.id)
        assert persisted.persisted is True
        assert persisted.status == "candidate"

        reviewed = update_paper_research_card(
            session,
            paper.id,
            PaperResearchCardUpdate(
                fields={
                    "theoretical_lens": ResearchCardFieldUpdate(
                        value_text="Dynamic capabilities",
                        source_locator="abstract",
                    )
                },
                my_interpretation="Capability matters through organizational readiness.",
                questions_raised="Would the mechanism hold for Korean manufacturing SMEs?",
                status="reviewed",
            ),
        )
        assert reviewed.status == "reviewed"
        assert reviewed.reviewed_at is not None
        assert reviewed.fields["theoretical_lens"].origin == "user_note"
        assert reviewed.fields["theoretical_lens"].support_status == "supported"


def test_question_workflow_tracks_literature_tiers_directions_design_and_proposal() -> None:
    with _session() as session:
        paper = _paper()
        question = ResearchQuestion(
            title="AI capability in manufacturing SMEs",
            question_text="How does AI capability affect innovation performance in manufacturing SMEs?",
            motivation="AI investment does not automatically translate into innovation outcomes.",
            importance_notes="The mechanism is strategically relevant for technology management.",
            scope_notes="Manufacturing SMEs",
            evidence_status="insufficient_evidence",
            status="exploring",
        )
        session.add_all([paper, question])
        session.flush()
        session.add(
            ResearchQuestionPaper(
                research_question_id=question.id,
                paper_id=paper.id,
                relation="supports",
                literature_tier="candidate",
            )
        )
        session.commit()

        persist_paper_research_card(session, paper.id)
        update_paper_research_card(
            session,
            paper.id,
            PaperResearchCardUpdate(status="reviewed"),
        )
        update_question_paper(
            session,
            question.id,
            paper.id,
            ResearchQuestionPaperUpdate(
                relation="context",
                literature_tier="core",
                relationship_note="Closest empirical design in the current evidence set.",
            ),
        )

        direction = create_research_direction(
            session,
            question.id,
            ResearchDirectionCreate(
                title="Test organizational readiness as a mechanism in Korean manufacturing SMEs",
                rationale="Existing evidence provides a mechanism lead but not the target context.",
                status="selected",
                dimensions={
                    "novelty": 4,
                    "theory_fit": 5,
                    "data_feasibility": 4,
                    "method_feasibility": 4,
                    "scope_fit": 5,
                    "personal_interest": 5,
                },
                evidence_for="A reviewed core paper links AI capability to readiness and innovation.",
                evidence_against="The current evidence is cross-sectional and from another country.",
                next_test="Search Korean SME studies and longitudinal capability research.",
            ),
        )
        assert direction.score is not None and direction.score > 80

        design = upsert_research_design(
            session,
            question.id,
            ResearchDesignUpdate(
                selected_direction_id=direction.id,
                theoretical_framework="Dynamic capabilities",
                focal_constructs="AI capability; organizational readiness; innovation performance",
                independent_variables="AI capability",
                dependent_variables="Innovation performance",
                mediators="Organizational readiness",
                unit_of_analysis="Firm",
                context_population="Korean manufacturing SMEs",
                data_sources="Firm survey",
                methodology="Quantitative survey",
                analysis_plan="Structural equation modeling",
                hypotheses="H1: AI capability positively affects innovation performance.",
                expected_contribution="Clarify the organizational mechanism linking AI capability to value creation.",
                status="developing",
            ),
        )
        assert design.readiness_pct >= 80

        _, _, synthesis, workflow = build_question_workspace(session, question.id)
        assert synthesis.reviewed_card_count == 1
        assert workflow.core_papers == 1
        assert workflow.selected_directions == 1
        assert workflow.proposal_readiness_pct > 0

        proposal = build_research_proposal(session, question.id)
        assert proposal.readiness_pct == workflow.proposal_readiness_pct
        assert "Dynamic capabilities" in proposal.markdown
        assert "Korean manufacturing SMEs" in proposal.markdown
        assert any(section.key == "method" for section in proposal.sections)
