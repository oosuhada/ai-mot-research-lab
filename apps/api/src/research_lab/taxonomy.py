from __future__ import annotations

from dataclasses import dataclass

TAXONOMY_VERSION = "2026-08-23.v1"

AI_TERMS = (
    "artificial intelligence",
    "machine learning",
    "generative ai",
    "large language model",
    "large language models",
    "llm",
    "ai system",
    "ai systems",
    "algorithmic decision",
    "algorithmic management",
    "intelligent system",
)


@dataclass(frozen=True, slots=True)
class ResearchAxis:
    slug: str
    display_name: str
    openalex_query: str
    context_terms: tuple[str, ...]
    description: str


RESEARCH_AXES: tuple[ResearchAxis, ...] = (
    ResearchAxis(
        slug="ai-adoption-business-value",
        display_name="AI adoption and business value",
        openalex_query=(
            '"artificial intelligence" AND '
            '(adoption OR productivity OR "firm performance" OR "business value" OR capability)'
        ),
        context_terms=(
            "adoption",
            "productivity",
            "firm performance",
            "organizational performance",
            "business value",
            "capability",
            "capabilities",
            "complementarity",
            "complementarities",
            "return on investment",
            "roi",
        ),
        description="Organizational AI adoption, productivity, performance, ROI, capabilities, and complementarities.",
    ),
    ResearchAxis(
        slug="technology-innovation-management",
        display_name="Technology and innovation management",
        openalex_query=(
            '"artificial intelligence" AND '
            '(innovation OR "technology management" OR "dynamic capabilities" '
            'OR "absorptive capacity" OR "R&D")'
        ),
        context_terms=(
            "innovation",
            "technology management",
            "technology strategy",
            "r&d",
            "research and development",
            "dynamic capabilities",
            "dynamic capability",
            "absorptive capacity",
            "diffusion",
            "technology diffusion",
        ),
        description=(
            "Technology strategy, R&D management, innovation diffusion, absorptive capacity, "
            "and dynamic capabilities."
        ),
    ),
    ResearchAxis(
        slug="ai-organizational-change",
        display_name="AI-enabled organizational change",
        openalex_query=(
            '"artificial intelligence" AND '
            '(organization OR workplace OR jobs OR "human-AI" OR "decision making" OR "knowledge work")'
        ),
        context_terms=(
            "organization",
            "organisational",
            "organizational",
            "workplace",
            "job redesign",
            "jobs",
            "human-ai",
            "human ai",
            "decision making",
            "decision-making",
            "knowledge work",
            "knowledge worker",
            "team",
            "employee",
            "workers",
        ),
        description=(
            "Job redesign, human-AI collaboration, decision-making, organizational structure, "
            "and knowledge work."
        ),
    ),
    ResearchAxis(
        slug="industrial-ai-smart-operations",
        display_name="Industrial AI and smart operations",
        openalex_query=(
            '("artificial intelligence" OR "machine learning") AND '
            '(manufacturing OR "smart factory" OR "predictive maintenance" OR "digital twin" OR operations)'
        ),
        context_terms=(
            "manufacturing",
            "smart factory",
            "smart manufacturing",
            "predictive maintenance",
            "digital twin",
            "industrial ai",
            "production",
            "quality control",
            "yield",
            "operations management",
            "operational decision",
        ),
        description=(
            "Manufacturing AI, smart factories, quality/yield, predictive maintenance, digital twins, "
            "and operations decisions."
        ),
    ),
    ResearchAxis(
        slug="ai-governance-responsible-deployment",
        display_name="AI governance and responsible deployment",
        openalex_query=(
            '"artificial intelligence" AND '
            '(governance OR responsible OR trust OR accountability OR oversight OR risk OR regulation)'
        ),
        context_terms=(
            "governance",
            "responsible ai",
            "responsible artificial intelligence",
            "trust",
            "accountability",
            "oversight",
            "human oversight",
            "risk management",
            "regulation",
            "regulatory",
            "ethics",
            "ethical",
            "deployment",
        ),
        description="Trust, accountability, human oversight, evaluation, risk management, regulation, and governance.",
    ),
    ResearchAxis(
        slug="agentic-enterprise-workflows",
        display_name="Agentic systems and enterprise workflows",
        openalex_query=(
            '("AI agent" OR "agentic AI" OR "multi-agent" OR "LLM agent") AND '
            '(enterprise OR workflow OR organization OR business OR "human-in-the-loop")'
        ),
        context_terms=(
            "enterprise",
            "workflow",
            "business process",
            "organization",
            "organizational",
            "human-in-the-loop",
            "human in the loop",
            "automation",
            "delegation",
            "coordination",
            "stateful",
        ),
        description=(
            "AI agents, multi-agent systems, enterprise workflow automation, stateful coordination, "
            "and human-in-the-loop work."
        ),
    ),
)

AXIS_BY_SLUG = {axis.slug: axis for axis in RESEARCH_AXES}


def text_matches_axis(text: str, axis: ResearchAxis) -> bool:
    normalized = " ".join(text.lower().split())
    has_ai = any(term in normalized for term in AI_TERMS)
    if axis.slug == "agentic-enterprise-workflows":
        has_ai = has_ai or any(
            term in normalized
            for term in (
                "ai agent",
                "agentic",
                "multi-agent",
                "multi agent",
                "llm agent",
                "autonomous agent",
            )
        )
    has_context = any(term in normalized for term in axis.context_terms)
    return has_ai and has_context

