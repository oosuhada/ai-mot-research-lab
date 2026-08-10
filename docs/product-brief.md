# Product Brief — AI & Technology Management Research Lab

## Product statement

AI & Technology Management Research Lab is a greenfield personal research intelligence system for one narrow question:

> How is AI changing organizations, industries, innovation activity, and decision-making; how far has existing research explained those changes; and which next questions are worth testing?

It is intentionally not a general academic chatbot. The product helps a researcher build a durable corpus around the intersection of artificial intelligence and Management of Technology (MOT), then inspect the corpus as evidence rather than repeatedly rediscovering papers through ad-hoc searches.

## Primary user and jobs to be done

The primary user is an individual preparing for and conducting graduate-level research. The system should support recurring work across coursework, proposal writing, literature review, and thesis-topic narrowing.

The core jobs are:

1. Decide which papers deserve reading time and why.
2. Compare claims, theories, units of analysis, methods, data, and limitations.
3. Identify agreement and disagreement without flattening contradictory evidence.
4. See how topics, contexts, and methods shift over time.
5. Distinguish well-supported findings from uncertain or under-tested claims.
6. Turn evidence patterns into falsifiable research-question candidates.
7. Trace every generated conclusion back to paper metadata or source text.

## Research scope

The corpus is constrained to six axes. The taxonomy is versioned in code so ingestion and evaluation use the same definitions.

| Axis | Scope |
| --- | --- |
| AI adoption and business value | Adoption, productivity, performance, ROI, capabilities, complementarities |
| Technology and innovation management | Technology strategy, R&D management, diffusion, absorptive capacity, dynamic capabilities |
| AI-enabled organizational change | Job redesign, human-AI collaboration, decision-making, structure, knowledge work |
| Industrial AI and smart operations | Manufacturing AI, smart factory, quality/yield, predictive maintenance, digital twins, operations decisions |
| AI governance and responsible deployment | Trust, accountability, human oversight, evaluation, risk management, regulation, governance |
| Agentic systems and enterprise workflows | AI agents, multi-agent systems, workflow automation, stateful orchestration, human-in-the-loop work |

The default publication window begins in 2018. Older papers are admitted only when they are explicitly marked as theoretical foundations or seminal works. Pure model-performance papers are excluded unless they make a direct organizational, industrial, innovation-management, or governance contribution.

## Inclusion and exclusion principles

### Include

- Empirical or conceptual work that links AI/advanced digital technology to organizational, industrial, innovation, operational, or governance outcomes.
- Management and information-systems work that provides theory useful for explaining AI adoption or value creation.
- Industrial AI work with an operational decision or management implication.
- Agentic-system work when it studies enterprise workflows, delegation, coordination, reliability, governance, or human oversight.
- Seminal pre-2018 theory papers when a researcher explicitly marks them as foundations.

### Exclude by default

- Benchmark-only or architecture-only ML papers with no management/organization/industry connection.
- Generic web results that are not scholarly records.
- Full text with unclear redistribution or text-mining rights.
- Automatically inferred “research gaps” without inspectable evidence.
- Large indiscriminate corpus dumps before search quality has been validated.

## MVP product surfaces

### Research Landscape

Shows corpus counts by research axis and year, leading venues/authors/institutions, and evidence-backed topic relationships. The goal is orientation, not decorative analytics.

### Paper Library

Provides hybrid retrieval, filters, reading state, tags, notes, imports, and a detailed paper page with provenance, identifiers, citations, related records, and legal full-text locators when available.

### Compare Papers

Compares research question, theoretical lens, unit of analysis, context, dataset/sample, methodology, constructs, findings, limitations, contribution, and future research. Every populated field has one or more evidence links or is visibly marked `insufficient evidence`.

### Research Question & Gap Canvas

Stores an editable research exploration containing search strategy, inclusion/exclusion criteria, clusters, agreement/conflict, under-studied contexts/methods, candidate gaps, falsifiability notes, follow-up questions, theories, and candidate data/methods. Generated gap candidates are hypotheses to validate, never facts.

### Evidence-grounded Chat

Allows scope selection across search results, selected papers, comparison sets, or the corpus. Answers label source-backed facts, paper claims, system inference, and user notes separately. Each substantive generated claim must carry evidence or an explicit `insufficient evidence` state.

## Non-goals for the first release

- General web + literature fusion as a default retrieval mode.
- Role-play agents, virtual reviewers, defense games, or persona marketplaces.
- Payments, subscriptions, multi-tenant RBAC, or team collaboration workflows.
- Unauthorized full-text crawling.
- Marketing claims that the system “automatically discovers research gaps.”

## MVP success criteria

The MVP is useful when the owner can ingest at least 500 relevant metadata records idempotently, retrieve representative literature with hybrid search, maintain a reading workflow, compare papers with evidence states, save a gap canvas, and reproduce retrieval/evidence evaluations from a small manually curated test set.

Quantitative metrics are treated as diagnostics, not product claims, until the evaluation set is large enough to justify inference.

