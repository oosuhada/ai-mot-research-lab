from __future__ import annotations

# The taxonomy is intentionally data-heavy: keeping each concept definition compact
# makes the operational vocabulary auditable as a single table-like declaration.
# ruff: noqa: E501
from dataclasses import dataclass

MOT_TAXONOMY_VERSION = "2026-09-23.v1"


@dataclass(frozen=True, slots=True)
class MotConcept:
    slug: str
    display_name: str
    kind: str
    terms: tuple[str, ...]
    description: str
    openalex_query: str | None = None
    strong_terms: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MotAssignmentCandidate:
    slug: str
    kind: str
    matched_terms: tuple[str, ...]
    evidence_kind: str
    evidence_text: str
    source_locator: str
    rule_id: str


# These areas are an operational taxonomy, not a claim that MOT has one official,
# exhaustive classification. They deliberately describe research problems rather
# than technologies. The source rationale is documented in docs/mot-taxonomy.md.
MOT_PROBLEMS: tuple[MotConcept, ...] = (
    MotConcept(
        slug="mot-technology-strategy-portfolio",
        display_name="Technology strategy and portfolio",
        kind="mot_problem",
        openalex_query=(
            '("technology strategy" OR "technology portfolio" OR "technology selection" '
            'OR "technology sourcing" OR "technology capability") AND '
            '(strategy OR competitive OR portfolio OR capability)'
        ),
        terms=(
            "technology strategy",
            "technology portfolio",
            "technology selection",
            "technology sourcing",
            "technology capability",
            "technological capability",
            "technology investment strategy",
            "technology positioning",
        ),
        strong_terms=("technology strategy", "technology portfolio", "technology selection"),
        description="Strategic choice, positioning, sourcing, capability and portfolio decisions involving technology.",
    ),
    MotConcept(
        slug="mot-rd-management-investment",
        display_name="R&D management and investment",
        kind="mot_problem",
        openalex_query=(
            '("research and development" OR "R&D" OR "research productivity" OR "R&D project") AND '
            '(management OR investment OR productivity OR portfolio OR evaluation OR performance)'
        ),
        terms=(
            "r&d management",
            "r&d investment",
            "r&d intensity",
            "r&d productivity",
            "research productivity",
            "research and development management",
            "research and development investment",
            "r&d portfolio",
            "r&d project",
            "research project selection",
            "research project evaluation",
        ),
        strong_terms=("r&d management", "r&d investment", "r&d productivity", "r&d portfolio"),
        description="R&D resources, productivity, portfolios, investment, project selection and evaluation.",
    ),
    MotConcept(
        slug="mot-foresight-roadmapping-intelligence",
        display_name="Technology foresight, roadmapping and intelligence",
        kind="mot_problem",
        openalex_query=(
            '("technology forecasting" OR "technology foresight" OR "technology roadmapping" '
            'OR "technology intelligence" OR "technology scouting" OR "patent landscaping")'
        ),
        terms=(
            "technology forecasting",
            "technological forecasting",
            "technology foresight",
            "technological foresight",
            "technology roadmapping",
            "technology roadmap",
            "technology intelligence",
            "competitive technology intelligence",
            "technology scouting",
            "patent landscaping",
            "emerging technology identification",
        ),
        strong_terms=(
            "technology forecasting",
            "technology foresight",
            "technology roadmapping",
            "technology intelligence",
            "technology scouting",
        ),
        description="Anticipating, monitoring and mapping technological change to inform decisions.",
    ),
    MotConcept(
        slug="mot-organizational-learning-capabilities",
        display_name="Organizational learning, knowledge and capabilities",
        kind="mot_problem",
        openalex_query=(
            '("absorptive capacity" OR "dynamic capabilities" OR "organizational learning" '
            'OR "knowledge management" OR "knowledge integration") AND '
            '(innovation OR technology OR technological)'
        ),
        terms=(
            "absorptive capacity",
            "dynamic capability",
            "dynamic capabilities",
            "organizational learning",
            "organisational learning",
            "knowledge management",
            "knowledge integration",
            "knowledge transfer",
            "technological capability",
            "innovation capability",
            "innovation capabilities",
        ),
        strong_terms=("absorptive capacity", "dynamic capabilities", "organizational learning"),
        description="Learning, knowledge flows and capability development that shape technological and innovation outcomes.",
    ),
    MotConcept(
        slug="mot-technology-adoption-diffusion",
        display_name="Technology adoption and diffusion",
        kind="mot_problem",
        openalex_query=(
            '("technology adoption" OR "technology acceptance" OR "innovation adoption" '
            'OR "technology diffusion" OR "diffusion of innovation")'
        ),
        terms=(
            "technology adoption",
            "technological adoption",
            "technology acceptance",
            "innovation adoption",
            "technology diffusion",
            "technological diffusion",
            "diffusion of innovation",
            "diffusion of innovations",
            "adoption intention",
            "adoption decision",
        ),
        strong_terms=("technology adoption", "technology acceptance", "technology diffusion"),
        description="Individual and organizational decisions to adopt, use and diffuse technologies and innovations.",
    ),
    MotConcept(
        slug="mot-entrepreneurship-commercialization",
        display_name="Technology entrepreneurship and commercialization",
        kind="mot_problem",
        openalex_query=(
            '("technology entrepreneurship" OR "technology commercialization" OR "research commercialization" '
            'OR "academic entrepreneurship" OR "university spin-off" OR "university spinoff")'
        ),
        terms=(
            "technology entrepreneurship",
            "technological entrepreneurship",
            "technology commercialization",
            "technology commercialisation",
            "research commercialization",
            "research commercialisation",
            "academic entrepreneurship",
            "university spin-off",
            "university spin off",
            "university spinoff",
            "science-based venture",
            "technology venture",
        ),
        strong_terms=("technology entrepreneurship", "technology commercialization", "academic entrepreneurship"),
        description="Venture creation, commercialization and university–industry pathways for technology and research.",
    ),
    MotConcept(
        slug="mot-ip-licensing-transfer",
        display_name="Intellectual property, licensing and technology transfer",
        kind="mot_problem",
        openalex_query=(
            '("technology transfer" OR "technology licensing" OR "patent licensing" '
            'OR "intellectual property strategy" OR "patent strategy" OR "university technology transfer")'
        ),
        terms=(
            "technology transfer",
            "technological transfer",
            "technology licensing",
            "patent licensing",
            "licensing strategy",
            "intellectual property strategy",
            "ip strategy",
            "patent strategy",
            "patent management",
            "university technology transfer",
            "technology transfer office",
        ),
        strong_terms=("technology transfer", "technology licensing", "patent licensing"),
        description="IP strategy, patenting, licensing and transfer of knowledge or technology across organizations.",
    ),
    MotConcept(
        slug="mot-open-innovation-networks-ecosystems",
        display_name="Open innovation, networks and ecosystems",
        kind="mot_problem",
        openalex_query=(
            '("open innovation" OR "innovation network" OR "innovation ecosystem" '
            'OR "innovation collaboration" OR "R&D alliance" OR "innovation partnership")'
        ),
        terms=(
            "open innovation",
            "innovation network",
            "innovation networks",
            "innovation ecosystem",
            "innovation ecosystems",
            "innovation collaboration",
            "innovation partnership",
            "r&d alliance",
            "research alliance",
            "collaborative innovation",
            "innovation intermediary",
        ),
        strong_terms=("open innovation", "innovation ecosystem", "innovation network"),
        description="External knowledge search, collaboration, alliances, networks and innovation ecosystems.",
    ),
    MotConcept(
        slug="mot-platforms-standards-business-models",
        display_name="Platforms, standards and business-model innovation",
        kind="mot_problem",
        openalex_query=(
            '("platform ecosystem" OR "digital platform" OR "technology standard" OR standardization '
            'OR "business model innovation" OR "service innovation") AND (innovation OR technology OR digital)'
        ),
        terms=(
            "platform ecosystem",
            "platform ecosystems",
            "digital platform",
            "technology platform",
            "technology standard",
            "technological standard",
            "standardization",
            "standardisation",
            "business model innovation",
            "service innovation",
            "servitization",
            "servitisation",
        ),
        strong_terms=("platform ecosystem", "technology standard", "business model innovation"),
        description="Platforms, standards, service innovation and changes in how technology-enabled value is created and captured.",
    ),
    MotConcept(
        slug="mot-operations-supply-chain-technology-change",
        display_name="Operations and supply-chain technology change",
        kind="mot_problem",
        openalex_query=(
            '("technology implementation" OR "digital manufacturing" OR "advanced manufacturing" '
            'OR "supply chain technology" OR "production technology" OR "process innovation") AND '
            '(operations OR manufacturing OR production OR "supply chain")'
        ),
        terms=(
            "digital manufacturing",
            "advanced manufacturing",
            "manufacturing technology",
            "production technology",
            "supply chain technology",
            "technology implementation",
            "process innovation",
            "operations innovation",
            "manufacturing innovation",
            "technology-enabled operations",
            "technology enabled operations",
        ),
        strong_terms=("digital manufacturing", "supply chain technology", "manufacturing technology"),
        description="Technological change in production, operations and supply chains, including implementation and process innovation.",
    ),
    MotConcept(
        slug="mot-innovation-policy-systems-regulation",
        display_name="Innovation policy, systems and regulation",
        kind="mot_problem",
        openalex_query=(
            '("innovation policy" OR "technology policy" OR "innovation system" '
            'OR "national innovation system" OR "regional innovation system" OR "technology regulation")'
        ),
        terms=(
            "innovation policy",
            "technology policy",
            "science and technology policy",
            "innovation system",
            "innovation systems",
            "national innovation system",
            "regional innovation system",
            "sectoral innovation system",
            "technology regulation",
            "innovation regulation",
            "public innovation policy",
        ),
        strong_terms=("innovation policy", "technology policy", "national innovation system"),
        description="Public policy, institutions, regulation and national/regional/sectoral systems shaping innovation.",
    ),
    MotConcept(
        slug="mot-sustainability-responsible-transition",
        display_name="Sustainability transitions and responsible innovation",
        kind="mot_problem",
        openalex_query=(
            '("sustainability transition" OR "socio-technical transition" OR "responsible innovation" '
            'OR "responsible research and innovation" OR "technology social impact" '
            'OR "just transition")'
        ),
        terms=(
            "sustainability transition",
            "sustainability transitions",
            "socio-technical transition",
            "socio technical transition",
            "responsible innovation",
            "responsible research and innovation",
            "responsible research & innovation",
            "just transition",
            "technology social impact",
            "social impact of technology",
            "responsible technology",
        ),
        strong_terms=("responsible innovation", "socio-technical transition", "sustainability transition"),
        description="Socio-technical transitions, responsibility, societal impacts, labor and sustainability implications of technology.",
    ),
)


MOT_CONTEXTS: tuple[MotConcept, ...] = (
    MotConcept("context-manufacturing", "Manufacturing", "technology_context", ("manufacturing", "factory", "production system", "industrial"), "Manufacturing and industrial production."),
    MotConcept("context-health-biotech", "Health and biotech", "technology_context", ("healthcare", "health care", "hospital", "biotech", "biotechnology", "pharmaceutical"), "Healthcare, life sciences and biotechnology."),
    MotConcept("context-mobility", "Mobility and transportation", "technology_context", ("automotive", "vehicle", "mobility", "transportation", "transport", "aviation"), "Mobility and transportation industries."),
    MotConcept("context-energy-environment", "Energy and environment", "technology_context", ("energy", "electricity", "renewable", "climate", "decarbonization", "decarbonisation", "environmental technology"), "Energy, climate and environmental technology contexts."),
    MotConcept("context-semiconductors-electronics", "Semiconductors and electronics", "technology_context", ("semiconductor", "microelectronics", "chip industry", "integrated circuit"), "Semiconductors, electronics and related production ecosystems."),
    MotConcept("context-telecommunications", "Telecommunications", "technology_context", ("telecommunication", "telecommunications", "5g", "6g", "broadband", "mobile network"), "Telecommunications and network industries."),
    MotConcept("context-software-digital", "Software and digital", "technology_context", ("software", "digital technology", "digital technologies", "information technology", "cloud computing", "digital transformation"), "Software, IT and digital technology contexts."),
    MotConcept("context-services-public", "Services and public sector", "technology_context", ("service industry", "service sector", "public sector", "government", "public service", "financial services"), "Service industries and public-sector settings."),
)


MOT_UNITS: tuple[MotConcept, ...] = (
    MotConcept("unit-individual", "Individual", "unit_of_analysis", ("individual-level", "individual level", "consumer", "user", "employee"), "Individuals, users, consumers or employees."),
    MotConcept("unit-team", "Team", "unit_of_analysis", ("team-level", "team level", "project team", "r&d team", "research team"), "Teams and work groups."),
    MotConcept("unit-project", "Project", "unit_of_analysis", ("project-level", "project level", "r&d project", "innovation project", "development project"), "R&D, innovation and technology projects."),
    MotConcept("unit-firm", "Firm or organization", "unit_of_analysis", ("firm-level", "firm level", "organizational-level", "organizational level", "company-level", "company level", "firms"), "Firms and organizations."),
    MotConcept("unit-network", "Inter-organizational network", "unit_of_analysis", ("interorganizational", "inter-organizational", "alliance network", "collaboration network", "network-level"), "Alliances and inter-organizational networks."),
    MotConcept("unit-industry", "Industry or sector", "unit_of_analysis", ("industry-level", "industry level", "sector-level", "sector level", "industry structure"), "Industries and sectors."),
    MotConcept("unit-region", "Region or cluster", "unit_of_analysis", ("regional", "region-level", "regional cluster", "industrial cluster", "innovation cluster"), "Regions, clusters and local innovation systems."),
    MotConcept("unit-country", "Country or national system", "unit_of_analysis", ("country-level", "country level", "national-level", "national level", "national innovation system"), "Countries and national systems."),
)


MOT_THEORIES: tuple[MotConcept, ...] = (
    MotConcept("theory-absorptive-capacity", "Absorptive capacity", "theory_construct", ("absorptive capacity",), "Absorptive-capacity construct."),
    MotConcept("theory-dynamic-capabilities", "Dynamic capabilities", "theory_construct", ("dynamic capabilities", "dynamic capability"), "Dynamic-capabilities perspective."),
    MotConcept("theory-resource-based-view", "Resource-based view", "theory_construct", ("resource-based view", "resource based view", "rbv"), "Resource-based view."),
    MotConcept("theory-institutional", "Institutional theory", "theory_construct", ("institutional theory", "institutional pressure", "institutional pressures", "institutional isomorphism"), "Institutional-theory constructs."),
    MotConcept("theory-organizational-learning", "Organizational learning", "theory_construct", ("organizational learning", "organisational learning"), "Organizational-learning theory."),
    MotConcept("theory-technology-acceptance", "Technology acceptance", "theory_construct", ("technology acceptance model", "tam", "utaut", "unified theory of acceptance"), "Technology-acceptance theories."),
    MotConcept("theory-diffusion-innovations", "Diffusion of innovations", "theory_construct", ("diffusion of innovations", "diffusion of innovation", "innovation diffusion theory"), "Diffusion-of-innovations theory."),
    MotConcept("theory-knowledge-based-view", "Knowledge-based view", "theory_construct", ("knowledge-based view", "knowledge based view", "knowledge-based theory"), "Knowledge-based view of the firm."),
    MotConcept("theory-transaction-cost", "Transaction cost economics", "theory_construct", ("transaction cost economics", "transaction cost theory", "transaction costs"), "Transaction-cost economics."),
    MotConcept("theory-real-options", "Real options", "theory_construct", ("real options theory", "real option theory", "real options reasoning"), "Real-options reasoning for technology and R&D investment."),
)


MOT_METHODS: tuple[MotConcept, ...] = (
    MotConcept("mot-method-discrete-choice", "Discrete choice / conjoint", "methodology", ("discrete choice experiment", "choice experiment", "conjoint analysis", "conjoint experiment"), "Choice and conjoint methods."),
    MotConcept("mot-method-survey", "Survey", "methodology", ("survey data", "questionnaire survey", "cross-sectional survey"), "Survey-based empirical research."),
    MotConcept("mot-method-case-interview", "Case study / interview", "methodology", ("case study", "case studies", "semi-structured interview", "semistructured interview", "qualitative interview"), "Case and interview research."),
    MotConcept("mot-method-panel-causal", "Panel / causal inference", "methodology", ("panel data", "difference-in-differences", "difference in differences", "instrumental variable", "regression discontinuity", "synthetic control"), "Panel and causal-inference designs."),
    MotConcept("mot-method-patent-bibliometric", "Patent / bibliometric analysis", "methodology", ("patent analysis", "patent data", "bibliometric analysis", "bibliometrics", "citation analysis", "science mapping"), "Patent and bibliometric methods."),
    MotConcept("mot-method-simulation-optimization", "Simulation / optimization", "methodology", ("simulation model", "agent-based model", "agent based model", "optimization model", "optimisation model", "system dynamics"), "Simulation and optimization methods."),
    MotConcept("mot-method-machine-learning", "Machine learning / computational", "methodology", ("machine learning model", "machine learning method", "deep learning model", "natural language processing", "topic modeling", "topic modelling"), "ML and computational analysis methods."),
    MotConcept("mot-method-review", "Systematic / scoping review", "methodology", ("systematic literature review", "systematic review", "scoping review", "meta-analysis", "meta analysis"), "Structured literature synthesis."),
)


AI_TERMS = (
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "large language model",
    "large language models",
    "llm",
    "chatgpt",
    "neural network",
)

AI_TARGET_CUES = (
    "adoption",
    "acceptance",
    "implementation",
    "governance",
    "impact",
    "effect",
    "workplace",
    "strategy",
    "capability",
    "business value",
)

AI_METHOD_CUES = (
    "we use",
    "we employ",
    "we apply",
    "classifier",
    "classification",
    "prediction",
    "predictive model",
    "text analysis",
    "to analyze",
    "to analyse",
    "topic model",
)

AI_TOOL_CUES = (
    "ai-assisted",
    "ai assisted",
    "chatgpt-assisted",
    "chatgpt assisted",
    "llm-assisted",
    "llm assisted",
    "using chatgpt to",
    "using an llm to",
    "using a large language model to",
)


MOT_RELEVANCE_TOPICS: tuple[MotConcept, ...] = (
    MotConcept("mot-relevance-core", "Core MOT relevance", "mot_relevance", (), "Directly addresses an MOT research problem."),
    MotConcept("mot-relevance-adjacent", "Adjacent MOT background", "mot_relevance", (), "Relevant context or theory but not a direct MOT problem match."),
    MotConcept("mot-relevance-uncertain", "MOT relevance uncertain", "mot_relevance", (), "Insufficient title/abstract evidence for a stronger decision."),
)


AI_ROLE_TOPICS: tuple[MotConcept, ...] = (
    MotConcept("ai-role-research-target", "AI as research target", "ai_role", (), "AI is an object or phenomenon being studied."),
    MotConcept("ai-role-analysis-method", "AI as analysis method", "ai_role", (), "AI/ML is used as an analysis method."),
    MotConcept("ai-role-research-tool", "AI as research tool", "ai_role", (), "AI is explicitly used to conduct the research workflow."),
    MotConcept("ai-role-unrelated", "AI unrelated", "ai_role", (), "No AI role is evident in available title/abstract text."),
    MotConcept("ai-role-unclear", "AI role unclear", "ai_role", (), "AI is mentioned but its role is not clear from available evidence."),
)


ALL_MOT_CONCEPTS = (
    MOT_PROBLEMS
    + MOT_CONTEXTS
    + MOT_UNITS
    + MOT_THEORIES
    + MOT_METHODS
    + MOT_RELEVANCE_TOPICS
    + AI_ROLE_TOPICS
)
MOT_CONCEPT_BY_SLUG = {item.slug: item for item in ALL_MOT_CONCEPTS}
MOT_PROBLEM_BY_SLUG = {item.slug: item for item in MOT_PROBLEMS}


LEGACY_AXIS_MAPPINGS: dict[str, tuple[str, ...]] = {
    "ai-adoption-business-value": (
        "mot-technology-adoption-diffusion",
        "mot-technology-strategy-portfolio",
        "mot-organizational-learning-capabilities",
    ),
    "technology-innovation-management": (
        "mot-technology-strategy-portfolio",
        "mot-rd-management-investment",
        "mot-foresight-roadmapping-intelligence",
        "mot-organizational-learning-capabilities",
    ),
    "ai-organizational-change": (
        "mot-organizational-learning-capabilities",
        "mot-sustainability-responsible-transition",
    ),
    "industrial-ai-smart-operations": ("mot-operations-supply-chain-technology-change",),
    "ai-governance-responsible-deployment": (
        "mot-innovation-policy-systems-regulation",
        "mot-sustainability-responsible-transition",
    ),
    "agentic-enterprise-workflows": (
        "mot-platforms-standards-business-models",
        "mot-operations-supply-chain-technology-change",
        "mot-organizational-learning-capabilities",
    ),
}


TECHNOLOGY_INNOVATION_ANCHORS = (
    "technology",
    "technological",
    "innovation",
    "innovative",
    "r&d",
    "research and development",
    "patent",
    "commercialization",
    "commercialisation",
    "digital transformation",
    "new product development",
)


def text_matches_mot_problem(text: str, problem: MotConcept) -> bool:
    normalized = _normalize(text)
    if any(term in normalized for term in problem.strong_terms):
        return True
    has_problem_term = any(term in normalized for term in problem.terms)
    has_anchor = any(anchor in normalized for anchor in TECHNOLOGY_INNOVATION_ANCHORS)
    return has_problem_term and has_anchor


def infer_mot_assignments(title: str, abstract: str | None) -> list[MotAssignmentCandidate]:
    title_text = _normalize(title)
    abstract_text = _normalize(abstract or "")
    combined = f"{title_text}\n{abstract_text}".strip()
    candidates: list[MotAssignmentCandidate] = []

    problem_matches = _infer_concepts(title, abstract, MOT_PROBLEMS, require_problem_match=True)
    candidates.extend(problem_matches)
    candidates.extend(_infer_concepts(title, abstract, MOT_CONTEXTS))
    candidates.extend(_infer_concepts(title, abstract, MOT_UNITS))
    candidates.extend(_infer_concepts(title, abstract, MOT_THEORIES))
    candidates.extend(_infer_concepts(title, abstract, MOT_METHODS))

    if problem_matches:
        candidates.append(_synthetic_candidate("mot-relevance-core", "mot_relevance", title, abstract, "problem-match"))
    elif any(item.kind in {"technology_context", "theory_construct", "methodology"} for item in candidates) and any(
        anchor in combined for anchor in TECHNOLOGY_INNOVATION_ANCHORS
    ):
        candidates.append(_synthetic_candidate("mot-relevance-adjacent", "mot_relevance", title, abstract, "adjacent-match"))
    elif title_text or abstract_text:
        candidates.append(_synthetic_candidate("mot-relevance-uncertain", "mot_relevance", title, abstract, "insufficient-problem-evidence"))

    candidates.extend(_infer_ai_roles(title, abstract, mot_relevant=bool(problem_matches)))
    return _dedupe_candidates(candidates)


def _infer_concepts(
    title: str,
    abstract: str | None,
    concepts: tuple[MotConcept, ...],
    *,
    require_problem_match: bool = False,
) -> list[MotAssignmentCandidate]:
    title_norm = _normalize(title)
    abstract_norm = _normalize(abstract or "")
    combined = f"{title_norm}\n{abstract_norm}".strip()
    result: list[MotAssignmentCandidate] = []
    for concept in concepts:
        matched = tuple(term for term in concept.terms if term in combined)
        if not matched:
            continue
        if require_problem_match and not text_matches_mot_problem(combined, concept):
            continue
        first = matched[0]
        evidence_kind, source_text = ("title", title) if first in title_norm else ("abstract", abstract or "")
        result.append(
            MotAssignmentCandidate(
                slug=concept.slug,
                kind=concept.kind,
                matched_terms=matched[:8],
                evidence_kind=evidence_kind,
                evidence_text=_excerpt(source_text, first),
                source_locator=evidence_kind,
                rule_id=f"keyword:{concept.slug}",
            )
        )
    return result


def _infer_ai_roles(title: str, abstract: str | None, *, mot_relevant: bool) -> list[MotAssignmentCandidate]:
    title_norm = _normalize(title)
    abstract_norm = _normalize(abstract or "")
    combined = f"{title_norm}\n{abstract_norm}".strip()
    ai_hits = tuple(term for term in AI_TERMS if term in combined)
    if not ai_hits:
        if mot_relevant:
            return [_synthetic_candidate("ai-role-unrelated", "ai_role", title, abstract, "no-ai-term")]
        return []

    result: list[MotAssignmentCandidate] = []
    method_hit = any(cue in combined for cue in AI_METHOD_CUES)
    tool_hit = any(cue in combined for cue in AI_TOOL_CUES)
    target_hit = any(cue in combined for cue in AI_TARGET_CUES)
    if target_hit:
        result.append(_evidence_candidate("ai-role-research-target", "ai_role", title, abstract, ai_hits, "ai-target-cue"))
    if method_hit:
        result.append(_evidence_candidate("ai-role-analysis-method", "ai_role", title, abstract, ai_hits, "ai-method-cue"))
    if tool_hit:
        result.append(_evidence_candidate("ai-role-research-tool", "ai_role", title, abstract, ai_hits, "ai-tool-cue"))
    if not result:
        result.append(_evidence_candidate("ai-role-unclear", "ai_role", title, abstract, ai_hits, "ai-role-unclear"))
    return result


def _evidence_candidate(
    slug: str,
    kind: str,
    title: str,
    abstract: str | None,
    matched_terms: tuple[str, ...],
    rule_id: str,
) -> MotAssignmentCandidate:
    first = matched_terms[0] if matched_terms else ""
    title_norm = _normalize(title)
    evidence_kind, source = ("title", title) if first and first in title_norm else ("abstract", abstract or title)
    return MotAssignmentCandidate(
        slug=slug,
        kind=kind,
        matched_terms=matched_terms[:8],
        evidence_kind=evidence_kind,
        evidence_text=_excerpt(source, first),
        source_locator=evidence_kind,
        rule_id=rule_id,
    )


def _synthetic_candidate(
    slug: str,
    kind: str,
    title: str,
    abstract: str | None,
    rule_id: str,
) -> MotAssignmentCandidate:
    source = title or abstract or ""
    evidence_kind = "title" if title else "abstract"
    return MotAssignmentCandidate(
        slug=slug,
        kind=kind,
        matched_terms=(),
        evidence_kind=evidence_kind,
        evidence_text=_excerpt(source, ""),
        source_locator=evidence_kind,
        rule_id=rule_id,
    )


def _dedupe_candidates(candidates: list[MotAssignmentCandidate]) -> list[MotAssignmentCandidate]:
    seen: set[str] = set()
    result: list[MotAssignmentCandidate] = []
    for item in candidates:
        if item.slug in seen:
            continue
        seen.add(item.slug)
        result.append(item)
    return result


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("–", "-").replace("—", "-").split())


def _excerpt(text: str, term: str, *, radius: int = 120) -> str:
    compact = " ".join(text.split())
    if not compact:
        return ""
    if not term:
        return compact[: 2 * radius]
    index = compact.lower().find(term.lower())
    if index < 0:
        return compact[: 2 * radius]
    start = max(0, index - radius)
    end = min(len(compact), index + len(term) + radius)
    return compact[start:end]
