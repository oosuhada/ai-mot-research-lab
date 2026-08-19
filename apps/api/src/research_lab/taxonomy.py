from __future__ import annotations

from dataclasses import dataclass

TAXONOMY_VERSION = "2026-08-25.v2"

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


@dataclass(frozen=True)
class ResearchAxis:
    slug: str
    display_name: str
    openalex_query: str
    context_terms: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class ResearchSubaxis:
    slug: str
    display_name: str
    parent_slug: str
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

RESEARCH_SUBAXES: tuple[ResearchSubaxis, ...] = (
    # AI adoption and business value · level 2
    ResearchSubaxis(
        "adoption-determinants",
        "Adoption determinants",
        "ai-adoption-business-value",
        ("adoption intention", "technology acceptance", "utaut", "tam", "adoption barrier"),
        "Drivers, barriers, and decision factors shaping organizational AI adoption.",
    ),
    ResearchSubaxis(
        "organizational-readiness",
        "Organizational readiness and complementary assets",
        "ai-adoption-business-value",
        ("organizational readiness", "organisational readiness", "complementary asset", "data readiness"),
        "Data, governance, leadership, and complementary assets required before adoption.",
    ),
    ResearchSubaxis(
        "ai-capability-development",
        "AI capability development",
        "ai-adoption-business-value",
        ("ai capability", "artificial intelligence capability", "analytics capability"),
        "How firms build, combine, and renew AI-related capabilities.",
    ),
    ResearchSubaxis(
        "workflow-transformation",
        "Workflow and process transformation",
        "ai-adoption-business-value",
        ("workflow", "business process", "process redesign", "process transformation"),
        "AI-enabled redesign of operational and knowledge-work processes.",
    ),
    ResearchSubaxis(
        "productivity-performance",
        "Productivity and operational performance",
        "ai-adoption-business-value",
        ("productivity", "operational performance", "firm performance", "performance improvement"),
        "Measured productivity, efficiency, and firm-performance outcomes.",
    ),
    ResearchSubaxis(
        "innovation-outcomes",
        "Innovation outcomes",
        "ai-adoption-business-value",
        ("innovation performance", "innovation outcome", "new product development"),
        "Product, process, and business-model innovation associated with AI adoption.",
    ),
    ResearchSubaxis(
        "value-roi",
        "Financial value and ROI measurement",
        "ai-adoption-business-value",
        ("return on investment", "business value", "financial performance", "value realization"),
        "Financial value realization, investment returns, and measurement frameworks.",
    ),
    ResearchSubaxis(
        "scaling-implementation",
        "Scaling and implementation",
        "ai-adoption-business-value",
        ("ai scaling", "scale ai", "implementation", "deployment", "production adoption"),
        "Implementation, diffusion, and scaling beyond pilots.",
    ),
    ResearchSubaxis(
        "workforce-human-ai",
        "Workforce, skills, and human–AI collaboration",
        "ai-adoption-business-value",
        ("human-ai", "human ai", "workforce", "employee skill", "job redesign"),
        "Skills, work design, and human–AI collaboration needed for value realization.",
    ),

    # AI adoption and business value · level 3
    ResearchSubaxis(
        "implementation-pilot-production",
        "Pilot-to-production transition",
        "scaling-implementation",
        (
            "pilot to production",
            "pilot-to-production",
            "production deployment",
            "productionization",
            "productionisation",
        ),
        "Moving AI initiatives from pilots and prototypes into stable production use.",
    ),
    ResearchSubaxis(
        "implementation-integration",
        "Systems and workflow integration",
        "scaling-implementation",
        (
            "system integration",
            "systems integration",
            "workflow integration",
            "legacy system",
            "enterprise integration",
        ),
        "Integration of AI with enterprise systems, data, and operational workflows.",
    ),
    ResearchSubaxis(
        "implementation-change-management",
        "Change management and organizational rollout",
        "scaling-implementation",
        (
            "change management",
            "organizational rollout",
            "organisational rollout",
            "implementation climate",
            "implementation readiness",
        ),
        "Organizational change, adoption support, and rollout practices for scaled AI use.",
    ),
    ResearchSubaxis(
        "implementation-scaling-governance",
        "Scaling governance and operating model",
        "scaling-implementation",
        ("scaling governance", "operating model", "ai operating model", "center of excellence", "centre of excellence"),
        "Operating models and governance mechanisms used to scale AI across the firm.",
    ),
    ResearchSubaxis(
        "workflow-process-automation",
        "Process automation and augmentation",
        "workflow-transformation",
        ("process automation", "workflow automation", "task automation", "process augmentation"),
        "Automation and augmentation of recurring business processes and tasks.",
    ),
    ResearchSubaxis(
        "workflow-knowledge-work",
        "Knowledge-work redesign",
        "workflow-transformation",
        ("knowledge work", "knowledge worker", "knowledge-work", "cognitive task", "professional work"),
        "Redesign of professional and knowledge-intensive work around AI capabilities.",
    ),
    ResearchSubaxis(
        "workflow-decision-process",
        "Decision-process redesign",
        "workflow-transformation",
        (
            "decision process",
            "decision workflow",
            "decision support",
            "decision-making process",
            "decision making process",
        ),
        "Changes in how organizational decisions are prepared, delegated, and reviewed.",
    ),
    ResearchSubaxis(
        "workflow-human-in-loop",
        "Human-in-the-loop workflow design",
        "workflow-transformation",
        ("human-in-the-loop", "human in the loop", "human oversight", "human review"),
        "Workflow architectures that preserve human review, escalation, or intervention.",
    ),
    ResearchSubaxis(
        "performance-productivity-efficiency",
        "Productivity and efficiency",
        "productivity-performance",
        ("productivity", "efficiency", "labor productivity", "labour productivity", "process efficiency"),
        "Measured productivity and efficiency outcomes associated with AI use.",
    ),
    ResearchSubaxis(
        "performance-firm-financial",
        "Firm and financial performance",
        "productivity-performance",
        ("firm performance", "financial performance", "profitability", "revenue growth", "market performance"),
        "Firm-level and financial performance outcomes.",
    ),
    ResearchSubaxis(
        "performance-operational-quality",
        "Operational quality and reliability",
        "productivity-performance",
        ("operational performance", "quality improvement", "service quality", "reliability", "cycle time"),
        "Quality, reliability, throughput, and other operational outcomes.",
    ),
    ResearchSubaxis(
        "workforce-skills-upskilling",
        "Skills, reskilling, and AI literacy",
        "workforce-human-ai",
        ("reskilling", "upskilling", "ai literacy", "digital skill", "employee skill", "skills development"),
        "Skill formation and workforce development for AI-enabled work.",
    ),
    ResearchSubaxis(
        "workforce-human-ai-collaboration",
        "Human–AI collaboration",
        "workforce-human-ai",
        (
            "human-ai collaboration",
            "human ai collaboration",
            "human-machine collaboration",
            "human machine collaboration",
            "hybrid intelligence",
        ),
        "Patterns and outcomes of collaborative work between people and AI systems.",
    ),
    ResearchSubaxis(
        "workforce-job-redesign",
        "Job and role redesign",
        "workforce-human-ai",
        ("job redesign", "role redesign", "task redesign", "job crafting", "work redesign"),
        "Changes to jobs, roles, tasks, and responsibility boundaries.",
    ),
    ResearchSubaxis(
        "workforce-employee-outcomes",
        "Employee outcomes and experience",
        "workforce-human-ai",
        (
            "employee outcome",
            "employee wellbeing",
            "employee well-being",
            "job satisfaction",
            "employee experience",
            "worker wellbeing",
        ),
        "Worker experience, satisfaction, wellbeing, and related employee outcomes.",
    ),
    ResearchSubaxis(
        "adoption-technology-factors",
        "Technology characteristics and fit",
        "adoption-determinants",
        (
            "technology compatibility",
            "relative advantage",
            "perceived usefulness",
            "perceived ease of use",
            "technology fit",
        ),
        "Technology-level characteristics shaping organizational adoption decisions.",
    ),
    ResearchSubaxis(
        "adoption-organizational-factors",
        "Organizational capabilities and leadership",
        "adoption-determinants",
        (
            "top management support",
            "leadership support",
            "organizational capability",
            "organisational capability",
            "organizational culture",
        ),
        "Organizational resources, leadership, and culture shaping adoption.",
    ),
    ResearchSubaxis(
        "adoption-environmental-factors",
        "Environmental and institutional pressures",
        "adoption-determinants",
        (
            "competitive pressure",
            "institutional pressure",
            "regulatory pressure",
            "environmental pressure",
            "industry pressure",
        ),
        "External competitive, institutional, and regulatory drivers of adoption.",
    ),
    ResearchSubaxis(
        "adoption-trust-risk",
        "Trust, risk, and adoption barriers",
        "adoption-determinants",
        ("adoption barrier", "perceived risk", "trust in ai", "ai trust", "privacy concern", "security concern"),
        "Trust, perceived risk, and barriers that inhibit organizational adoption.",
    ),

    # Technology and innovation management
    ResearchSubaxis(
        "tim-technology-strategy",
        "Technology strategy and portfolio management",
        "technology-innovation-management",
        (
            "technology strategy",
            "technology portfolio",
            "technology roadmap",
            "technology roadmapping",
            "portfolio management",
        ),
        "Strategic positioning, roadmapping, and portfolio choices around AI technologies.",
    ),
    ResearchSubaxis(
        "tim-rd-new-product",
        "R&D and new product development",
        "technology-innovation-management",
        ("r&d", "research and development", "new product development", "product development", "innovation project"),
        "AI in R&D management, experimentation, and new-product development.",
    ),
    ResearchSubaxis(
        "tim-dynamic-capabilities",
        "Dynamic capabilities and reconfiguration",
        "technology-innovation-management",
        ("dynamic capability", "dynamic capabilities", "sensing seizing", "resource reconfiguration"),
        "Dynamic-capability explanations of AI-enabled strategic adaptation.",
    ),
    ResearchSubaxis(
        "tim-absorptive-capacity",
        "Absorptive capacity and knowledge integration",
        "technology-innovation-management",
        ("absorptive capacity", "knowledge integration", "knowledge absorption", "knowledge acquisition"),
        "Learning and knowledge-integration capabilities supporting AI innovation.",
    ),
    ResearchSubaxis(
        "tim-diffusion-ecosystem",
        "Innovation diffusion and ecosystems",
        "technology-innovation-management",
        ("innovation diffusion", "technology diffusion", "innovation ecosystem", "technology ecosystem", "ecosystem"),
        "Diffusion of AI innovation across firms, industries, and innovation ecosystems.",
    ),
    ResearchSubaxis(
        "tim-innovation-performance",
        "Innovation performance and outcomes",
        "technology-innovation-management",
        ("innovation performance", "innovation outcome", "patent", "novelty", "innovation productivity"),
        "Innovation output and performance consequences of AI-related technology management.",
    ),

    # AI-enabled organizational change
    ResearchSubaxis(
        "org-job-work-redesign",
        "Job, task, and work redesign",
        "ai-organizational-change",
        ("job redesign", "task redesign", "work redesign", "job crafting", "role redesign"),
        "How AI changes jobs, tasks, roles, and division of labor.",
    ),
    ResearchSubaxis(
        "org-human-ai-collaboration",
        "Human–AI collaboration and augmentation",
        "ai-organizational-change",
        ("human-ai", "human ai", "human-machine collaboration", "augmentation", "hybrid intelligence"),
        "Collaboration, augmentation, and responsibility sharing between people and AI.",
    ),
    ResearchSubaxis(
        "org-decision-making",
        "Decision-making and delegation",
        "ai-organizational-change",
        ("decision making", "decision-making", "decision support", "delegation", "algorithmic decision"),
        "Changes in organizational decision rights, delegation, and decision quality.",
    ),
    ResearchSubaxis(
        "org-teams-coordination",
        "Teams, coordination, and structure",
        "ai-organizational-change",
        ("team", "coordination", "organizational structure", "organisational structure", "team performance"),
        "Team coordination and organizational-structure changes linked to AI.",
    ),
    ResearchSubaxis(
        "org-knowledge-work",
        "Knowledge work and professional expertise",
        "ai-organizational-change",
        ("knowledge work", "knowledge worker", "professional expertise", "expert work", "professional work"),
        "Effects of AI on knowledge-intensive and professional work.",
    ),
    ResearchSubaxis(
        "org-leadership-change",
        "Leadership and change management",
        "ai-organizational-change",
        (
            "leadership",
            "change management",
            "organizational change",
            "organisational change",
            "transformation leadership",
        ),
        "Leadership and change processes accompanying AI-enabled organizational transformation.",
    ),

    # Industrial AI and smart operations
    ResearchSubaxis(
        "industrial-smart-manufacturing",
        "Smart manufacturing and factory systems",
        "industrial-ai-smart-operations",
        ("smart manufacturing", "smart factory", "industry 4.0", "intelligent manufacturing"),
        "AI-enabled smart manufacturing and factory systems.",
    ),
    ResearchSubaxis(
        "industrial-predictive-maintenance",
        "Predictive maintenance and asset reliability",
        "industrial-ai-smart-operations",
        ("predictive maintenance", "condition monitoring", "remaining useful life", "asset reliability"),
        "Prediction and optimization of maintenance and industrial asset reliability.",
    ),
    ResearchSubaxis(
        "industrial-quality-yield",
        "Quality, yield, and process control",
        "industrial-ai-smart-operations",
        ("quality control", "quality inspection", "yield optimization", "yield improvement", "process control"),
        "AI for quality inspection, yield, and process control.",
    ),
    ResearchSubaxis(
        "industrial-digital-twin",
        "Digital twins and simulation",
        "industrial-ai-smart-operations",
        ("digital twin", "digital twins", "simulation model", "virtual commissioning"),
        "Digital-twin and simulation systems supporting industrial operations.",
    ),
    ResearchSubaxis(
        "industrial-supply-chain",
        "Supply chain and operations planning",
        "industrial-ai-smart-operations",
        ("supply chain", "production planning", "scheduling", "inventory", "operations planning"),
        "AI-assisted planning, scheduling, inventory, and supply-chain decisions.",
    ),
    ResearchSubaxis(
        "industrial-robotics-automation",
        "Robotics and autonomous operations",
        "industrial-ai-smart-operations",
        ("industrial robot", "robotics", "autonomous operation", "autonomous system", "robotic automation"),
        "Robotics, autonomous systems, and industrial automation.",
    ),

    # AI governance and responsible deployment
    ResearchSubaxis(
        "governance-responsible-ai",
        "Responsible AI principles and practice",
        "ai-governance-responsible-deployment",
        ("responsible ai", "responsible artificial intelligence", "responsible deployment", "responsible innovation"),
        "Responsible-AI frameworks and their organizational implementation.",
    ),
    ResearchSubaxis(
        "governance-trust-explainability",
        "Trust, transparency, and explainability",
        "ai-governance-responsible-deployment",
        ("trust", "explainability", "explainable ai", "transparency", "interpretability"),
        "Trust, transparency, interpretability, and explainability in AI deployment.",
    ),
    ResearchSubaxis(
        "governance-accountability-oversight",
        "Accountability and human oversight",
        "ai-governance-responsible-deployment",
        ("accountability", "human oversight", "oversight", "auditability", "ai audit"),
        "Accountability structures, audits, and human oversight mechanisms.",
    ),
    ResearchSubaxis(
        "governance-risk-safety",
        "AI risk, safety, and assurance",
        "ai-governance-responsible-deployment",
        ("ai risk", "risk management", "ai safety", "safety assurance", "model risk"),
        "Risk management, assurance, and safety practices for deployed AI.",
    ),
    ResearchSubaxis(
        "governance-regulation-compliance",
        "Regulation and compliance",
        "ai-governance-responsible-deployment",
        ("regulation", "regulatory", "compliance", "ai act", "legal requirement"),
        "Regulation, legal obligations, and organizational compliance responses.",
    ),
    ResearchSubaxis(
        "governance-fairness-ethics",
        "Fairness, ethics, and social impact",
        "ai-governance-responsible-deployment",
        ("fairness", "bias", "ethics", "ethical ai", "discrimination", "social impact"),
        "Fairness, bias, ethics, and social consequences of AI deployment.",
    ),

    # Agentic systems and enterprise workflows
    ResearchSubaxis(
        "agentic-agent-architecture",
        "Agent architectures and tool use",
        "agentic-enterprise-workflows",
        ("agent architecture", "tool use", "tool-use", "reasoning agent", "llm agent"),
        "Architectures, tool use, and execution patterns for enterprise AI agents.",
    ),
    ResearchSubaxis(
        "agentic-multi-agent-coordination",
        "Multi-agent coordination",
        "agentic-enterprise-workflows",
        ("multi-agent", "multi agent", "agent coordination", "agent collaboration", "agent communication"),
        "Coordination and collaboration among multiple AI agents.",
    ),
    ResearchSubaxis(
        "agentic-workflow-automation",
        "Agentic workflow automation",
        "agentic-enterprise-workflows",
        ("agentic workflow", "workflow automation", "business process automation", "agent workflow"),
        "Agent-driven automation of enterprise workflows and business processes.",
    ),
    ResearchSubaxis(
        "agentic-human-oversight",
        "Human oversight and intervention",
        "agentic-enterprise-workflows",
        ("human-in-the-loop", "human in the loop", "human oversight", "human intervention"),
        "Human supervision, intervention, and escalation in agentic workflows.",
    ),
    ResearchSubaxis(
        "agentic-delegation-control",
        "Delegation, autonomy, and control",
        "agentic-enterprise-workflows",
        ("delegation", "autonomy", "autonomous agent", "control mechanism", "delegated task"),
        "How autonomy and delegation are bounded and controlled in enterprise agents.",
    ),
    ResearchSubaxis(
        "agentic-enterprise-integration",
        "Enterprise integration and evaluation",
        "agentic-enterprise-workflows",
        ("enterprise integration", "enterprise system", "agent evaluation", "agent benchmark", "production agent"),
        "Integration, evaluation, and production operation of agents in enterprise systems.",
    ),
)

ADOPTION_SUBAXES = tuple(
    subaxis for subaxis in RESEARCH_SUBAXES if subaxis.parent_slug == "ai-adoption-business-value"
)
SUBAXIS_BY_SLUG = {subaxis.slug: subaxis for subaxis in RESEARCH_SUBAXES}

METHODOLOGY_TAXONOMY_VERSION = "2026-08-23.v1"
METHODOLOGY_PATTERNS: dict[str, tuple[str, ...]] = {
    "systematic-review": (
        "systematic literature review",
        "systematic review",
        "scoping review",
        "meta-analysis",
        "meta analysis",
    ),
    "survey": ("survey", "questionnaire"),
    "case-study": ("case study", "case studies"),
    "experiment": ("experiment", "randomized", "randomised", "controlled trial"),
    "qualitative": ("qualitative", "interview", "ethnograph"),
    "panel-longitudinal": ("panel data", "longitudinal"),
    "econometric": (
        "difference-in-differences",
        "difference in differences",
        "instrumental variable",
        "regression analysis",
        "econometric",
    ),
    "simulation": ("simulation", "simulated"),
    "conceptual": ("conceptual framework", "theoretical framework", "conceptual model"),
}


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


def infer_subaxis_labels(text: str, axis_slugs: set[str] | None = None) -> list[str]:
    """Return transparent keyword-derived sub-area labels for coverage auditing."""

    normalized = " ".join(text.lower().split())
    allowed_parents = set(axis_slugs or AXIS_BY_SLUG)
    matched: list[str] = []
    for subaxis in RESEARCH_SUBAXES:
        if subaxis.parent_slug not in allowed_parents:
            continue
        if any(term in normalized for term in subaxis.context_terms):
            matched.append(subaxis.slug)
            allowed_parents.add(subaxis.slug)
    return matched


def infer_methodology_labels(text: str) -> list[str]:
    """Return transparent keyword-based methodology labels.

    These labels are intentionally heuristic and are exposed as such in the UI/API. They are useful for
    coarse filtering but must not be presented as verified study-design facts without evidence extraction.
    """

    normalized = " ".join(text.lower().split())
    return [
        label
        for label, patterns in METHODOLOGY_PATTERNS.items()
        if any(pattern in normalized for pattern in patterns)
    ]
