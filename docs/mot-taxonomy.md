# MOT operational taxonomy

## Status and scope

This repository does **not** claim that management of technology (MOT) has one official,
complete taxonomy. The taxonomy implemented in `research_lab.mot_taxonomy` is an
operational structure for broad literature exploration. It separates dimensions that are
often conflated in search systems: research problem, technology/industry context, unit of
analysis, theory/construct, method/data, and the role of AI.

The intent is to support comparable exploration across MOT questions while preserving the
existing six AI-focused `research_axis` topics as legacy presets. A paper can receive
multiple labels in each dimension, and an automatic label remains a heuristic candidate
until a human review state says otherwise.

## Primary-source rationale

The operational scope was checked against multiple primary sources rather than copied from
one source.

### OECD / Eurostat Oslo Manual 2018

The Oslo Manual treats innovation activity more broadly than R&D alone. Chapter 4 lists
R&D; engineering/design/creative work; marketing and brand equity; intellectual property;
employee training; software and databases; tangible assets; and innovation management.
It also describes innovation management as planning, governing and controlling internal
and external resources, collaboration, external inputs, monitoring and learning.

- https://www.oecd.org/en/publications/oslo-manual-2018_9789264304604-en/full-report/component-10.html
- https://www.oecd.org/en/publications/oslo-manual-2018_9789264304604-en/full-report/component-11.html

Operational implication: R&D, IP/licensing, collaboration, organizational learning,
software/digital change, and innovation-management questions are all legitimate collection
targets. The Manual is an innovation-measurement standard, not an MOT field taxonomy, so it
is used as scope evidence rather than as a label hierarchy.

### IEEE Technology and Engineering Management Society (TEMS)

IEEE TEMS describes its field of interest as management sciences and practices for defining,
implementing and managing engineering and technology. Its stated topics include technology
policy development/assessment/transfer, research, product design and development,
manufacturing operations, innovation and entrepreneurship, program/project management,
strategy, organizational development and human behavior, and socioeconomic impact.

- https://www.ieee-tems.org/mission/

Operational implication: technology policy/transfer, R&D/project decisions, strategy,
operations, entrepreneurship, organization, and socioeconomic impacts should not require an
AI term to enter the corpus.

### ISPIM

Recent ISPIM conference themes and SIGs span business models, entrepreneurship, futures and
foresight, knowledge and technology transfer, open innovation, platforms/ecosystems/supply
chains, responsible innovation, innovation leadership/culture, methods for innovation
management research, and sustainability-oriented innovation management.

- https://www.ispim-innovation.com/post/call-for-submissions-ispim-connects-sendai
- https://www.ispim-innovation.com/sig-responsible-innovation

Operational implication: foresight, open innovation, ecosystem/platform questions,
business-model innovation, responsible innovation and sustainability transition need first-
class problem labels rather than being treated as miscellaneous AI applications.

## Operational dimensions

### 1. Research problem (`mot_problem`)

Current v1 problem families:

1. technology strategy and portfolio
2. R&D management and investment
3. technology foresight, roadmapping and intelligence
4. organizational learning, knowledge and capabilities
5. technology adoption and diffusion
6. technology entrepreneurship and commercialization
7. intellectual property, licensing and technology transfer
8. open innovation, networks and ecosystems
9. platforms, standards and business-model innovation
10. operations and supply-chain technology change
11. innovation policy, systems and regulation
12. sustainability transitions and responsible innovation

These families are deliberately problem-oriented. Adjacent economics, strategy,
organization, policy, information-systems and operations papers may qualify when the actual
research question concerns technological or innovation change. A paper is not core MOT only
because it contains the word `technology`, and a pure engineering performance paper is not
automatically core MOT.

### 2. Technology / industry context (`technology_context`)

Manufacturing; health/biotech; mobility/transportation; energy/environment;
semiconductors/electronics; telecommunications; software/digital; services/public sector.
Papers with no specific industry context remain valid.

### 3. Unit of analysis (`unit_of_analysis`)

Individual, team, project, firm/organization, inter-organizational network, industry/sector,
region/cluster, country/national system.

### 4. Theory / construct (`theory_construct`)

The current seed vocabulary includes absorptive capacity, dynamic capabilities,
resource-based view, institutional theory, organizational learning, technology acceptance,
diffusion of innovations, knowledge-based view, transaction-cost economics and real options.
The system only assigns these when the title/abstract exposes the corresponding term; it
does not infer a theory solely from a topic.

### 5. Method / data (`methodology`)

The new taxonomy extends the existing methodology dimension with explicit MOT-oriented
signals such as discrete choice/conjoint, survey, case/interview, panel/causal inference,
patent/bibliometric analysis, simulation/optimization, machine learning/computational
analysis, and structured review. Existing `methodology-*` labels remain compatible.

### 6. AI role (`ai_role`)

- `ai-role-research-target`: AI is the phenomenon being studied.
- `ai-role-analysis-method`: AI/ML is used as an analysis method.
- `ai-role-research-tool`: AI is explicitly used to conduct the research workflow.
- `ai-role-unrelated`: no AI role is evident in available title/abstract text for a paper
  already classified as a core MOT problem.
- `ai-role-unclear`: AI is mentioned but title/abstract evidence does not establish a role.

Roles can coexist. For example, a study of AI adoption that also uses ML classification can
receive both target and analysis-method roles.

## Evidence and review semantics

`paper_topics` remains the compatibility projection used by existing URLs and search. New
automatic MOT classifications add rows to `paper_topic_assignment_evidence` with taxonomy
version, assignment source, rule id, matched terms, evidence kind, source locator and review
status. The default status is `automatic_candidate`.

Evidence kinds distinguish title, abstract and full text. A title/abstract match is never
presented as full-text verification. Re-running the same taxonomy is idempotent through a
stable assignment key. Historical evidence remains even if current automatic links are
removed for reclassification. A current `human_rejected` assignment is not recreated by the
automatic classifier.

## Legacy AI-axis mapping

The old six `research_axis` topics are not renamed or deleted. `LEGACY_AXIS_MAPPINGS` records
their many-to-many correspondence to broad MOT problems so saved URLs and prior workflows
remain meaningful. The mapping is explanatory, not a migration that overwrites historical
labels.

## Collection boundaries

The `openalex_mot_pilot` collector is deliberately separate from `openalex_expansion` and its
checkpoint. Each problem has a bounded recent lane and a bounded foundation lane. The pilot
accepts non-AI literature and locally rechecks the title/abstract against the target problem
before ingestion. Duplicate handling continues to use canonical DOI, arXiv and OpenAlex
identities.

Low local counts mean **the current database is sparse for that operational label**. They do
not by themselves establish a research gap, field novelty, or lack of scholarship.
