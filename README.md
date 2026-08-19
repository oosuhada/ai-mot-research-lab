# AI × MOT Research Lab

**An evidence-first research intelligence workspace for studying Artificial Intelligence through the lens of Management of Technology.**  
**인공지능을 기술경영 관점에서 연구하기 위한 evidence-first 연구 인텔리전스 워크스페이스입니다.**

**Live demo / 라이브 데모:** https://research.oosu.dev/

> Build the research domain as a durable, evidence-traceable workspace—not as a one-shot paper chatbot.  
> 연구를 일회성 논문 챗봇이 아니라, 근거가 축적되고 다시 추적되는 지속 가능한 연구 공간으로 만든다.

## Overview / 개요

AI × MOT Research Lab is a personal research system for graduate-level work at the intersection of **Artificial Intelligence** and **Management of Technology (MOT)**. It treats the literature corpus as a durable research asset and connects discovery, reading, comparison, gap testing, research-question development, research design, and proposal preparation on top of the same evidence model.

AI × MOT Research Lab은 **인공지능(AI)** 과 **기술경영(MOT)** 의 교차 영역에서 대학원 수준의 연구를 진행하기 위한 개인 연구 시스템입니다. 논문 코퍼스를 일회성 검색 결과가 아니라 지속적으로 축적되는 연구 자산으로 보고, 같은 evidence model 위에서 탐색·읽기·비교·연구공백 검증·연구질문 발전·연구설계·연구계획서 작성까지 연결합니다.

The central research question is:

> **How is AI changing organizations, industries, innovation activity, and managerial decision-making; what has existing research explained, and what question is worth testing next?**

프로젝트가 다루는 중심 질문은 다음과 같습니다.

> **AI는 조직·산업·혁신 활동·경영 의사결정을 어떻게 바꾸고 있으며, 기존 연구는 무엇을 설명했고, 다음에는 어떤 질문을 검증할 가치가 있는가?**

Instead of scattering search history, notes, comparison tables, PDFs, and research questions across different tools, the product keeps them connected to a canonical scholarly corpus with explicit provenance.

검색 기록, 메모, 비교표, PDF, 연구질문을 여러 도구에 흩어 놓는 대신 하나의 canonical scholarly corpus에 연결하고, 어떤 해석과 주장이 어느 근거에서 왔는지 추적할 수 있도록 설계했습니다.

## Research workflow / 연구 워크플로

The product is organized around a connected research loop rather than a collection of isolated AI features.

서로 분리된 AI 기능 모음이 아니라 하나의 연결된 연구 루프를 중심으로 구성합니다.

```text
Corpus Observatory
      ↓
Paper Library
      ↓
Reading + Research Cards
      ↓
Research Question Workspace
      ↓
Evidence Comparison
      ↓
Gap Falsification
      ↓
Research Direction + Design
      ↓
Proposal Builder
```

The corpus is the starting point, but every downstream surface is designed to turn literature into a concrete research decision: **what have I actually established, what remains uncertain, and what should I investigate next?**

코퍼스는 출발점이지만 이후의 모든 화면은 논문 숫자를 실제 연구 의사결정으로 바꾸는 역할을 합니다. **무엇을 실제로 확인했는지, 무엇이 아직 불확실한지, 다음에는 무엇을 조사해야 하는지**를 계속 이어서 판단할 수 있게 합니다.

## Product walkthrough / 제품 화면

### 1. Corpus Observatory / 코퍼스 관측소

![Corpus Observatory](docs/screenshots/01-corpus-observatory.png)

The home dashboard compares major AI × MOT research territories using live corpus volume and evidence depth. A territory can be inspected without leaving the dashboard, expanded into child topics, and decomposed again when a branch becomes too broad.

첫 화면은 주요 AI × MOT 연구영역을 실제 코퍼스 논문량과 evidence depth로 비교합니다. 페이지를 떠나지 않고 연구축을 검사하고, 하위 주제로 펼치고, 논문량이 많은 branch는 다시 세분화할 수 있습니다.

Key interactions include territory sorting, publication-year trajectory, OA/full-text coverage, methodology signals, hierarchical topic expansion, and direct hand-off into a filtered paper library.

연구영역 정렬, 연도별 변화, OA·full-text coverage, methodology signal, 계층형 topic 탐색, 선택 영역을 그대로 Library 검색으로 넘기는 흐름을 제공합니다.

### 2. Paper Library / 논문 라이브러리

![Paper Library](docs/screenshots/02-paper-library.png)

Library combines PostgreSQL full-text search, pgvector retrieval, and reciprocal-rank-fused hybrid search while keeping filters, ranking signals, and evidence scope explicit.

Library는 PostgreSQL full-text search, pgvector retrieval, reciprocal-rank-fused hybrid search를 결합하면서 filter, ranking signal, evidence scope를 명확하게 보여줍니다.

Researchers can move between lexical, vector, and hybrid retrieval; filter by year, territory, methodology, venue, author, OA status, work type, tags, and reading state; and see the DOI/source link and matched evidence near every result.

Lexical·Vector·Hybrid 검색을 전환하고 연도, 연구영역, 방법론, 저널, 저자, OA, 논문유형, 태그, 읽기상태를 필터링할 수 있으며 각 결과 가까이에서 DOI/source와 실제 매칭 evidence를 확인할 수 있습니다.

### 3. Paper Detail & Research Card / 논문 상세와 리서치 카드

![Paper Research Card](docs/screenshots/03-paper-research-card.png)

Paper Detail turns a search result into a reusable research object. A structured Research Card records the paper's question, theory, constructs, context, sample, methodology, findings, limitations, contribution, and future-research leads.

Paper Detail은 검색 결과 한 건을 재사용 가능한 연구 객체로 바꿉니다. Research Card에는 연구질문, 이론, construct, 맥락, 표본, 방법론, 결과, 한계, 기여, future-research 후보를 구조화해 남깁니다.

Machine-extracted candidates and user-reviewed records remain distinct, and only explicitly reviewed cards contribute to higher-level Research Question synthesis.

자동 추출 후보와 사람이 검토한 기록은 분리해 유지하며, 상위 Research Question synthesis에는 명시적으로 reviewed 처리한 카드만 사용합니다.

### 4. Research Question Workspace / 연구 질문 워크스페이스

![Research Question Workspace](docs/screenshots/04-research-question-workspace.png)

The Research Question workspace is the persistent thread for a developing study. It connects candidate literature, reading/core/foundation tiers, saved searches, comparison sets, gap analyses, synthesis signals, candidate directions, research design, and proposal readiness under one question.

Research Question Workspace는 하나의 연구질문이 발전하는 과정을 보존하는 중심 공간입니다. Candidate·Reading·Core·Foundation literature tier, saved search, comparison set, gap analysis, synthesis signal, research direction, research design, proposal readiness를 하나의 질문 아래 연결합니다.

Its core question is simple: **what should I do next to make this research question more defensible?**

핵심 질문은 **“이 연구질문을 더 방어 가능한 상태로 만들기 위해 다음에 무엇을 해야 하는가?”**입니다.

### 5. Comparison Evidence Matrix / 논문 비교 근거 매트릭스

![Comparison Evidence Matrix](docs/screenshots/05-comparison-evidence-matrix.png)

Comparison sets place 2–6 papers side by side across theoretical lens, unit of analysis, context, dataset/sample, methodology, constructs, findings, limitations, contribution, and future research.

2–6편의 논문을 theoretical lens, unit of analysis, context, dataset/sample, methodology, construct, finding, limitation, contribution, future research 차원으로 나란히 비교합니다.

Every cell preserves whether it came from `paper_evidence`, `system_inference`, or `user_note`; missing support remains `insufficient_evidence` instead of being filled with plausible text.

각 셀은 `paper_evidence`, `system_inference`, `user_note` 중 어느 출처에서 만들어졌는지 유지하며, 근거가 없는 내용은 임의로 채우지 않고 `insufficient_evidence`로 남깁니다.

### 6. Gap Canvas / 연구 공백 캔버스

![Gap Canvas](docs/screenshots/06-gap-canvas.png)

Gap Canvas is a **falsification surface**, not an automatic research-gap detector. Sparse coverage becomes a candidate signal that must survive broader synonyms, years, theories, venues, and citation-neighbor searches.

Gap Canvas는 자동으로 연구공백을 선언하는 기능이 아니라 **반증을 위한 화면**입니다. 현재 코퍼스에서 논문이 적다는 사실을 candidate signal로 두고, 동의어·연도·이론·저널·citation neighbor를 확장해 실제로 반증을 시도합니다.

The candidate hypothesis, supporting evidence, invalidation risk, falsifiability note, next search query, and candidate method remain visible together.

후보 가설, 현재 지지 근거, 무효화 위험, falsifiability note, 다음 검색어, 후보 연구방법을 한 화면에서 함께 유지합니다.

### 7. Proposal Builder / 연구계획서 빌더

![Proposal Builder](docs/screenshots/07-proposal-builder.png)

Proposal Builder assembles research state already developed in the workspace into a proposal structure. It does not invent missing theory, evidence, or research-design choices; unresolved sections stay visibly incomplete.

Proposal Builder는 Workspace에서 실제로 발전시킨 연구 상태를 연구계획서 구조로 조립합니다. 부족한 이론, 근거, 연구설계 결정을 임의로 만들어내지 않으며 해결되지 않은 항목은 그대로 미완성 상태로 남깁니다.

The builder connects problem statement, motivation, literature synthesis, candidate gap, research question, theory, constructs/hypotheses, research model, data, method, expected contribution, and references.

현재 Problem Statement, Motivation, Literature Synthesis, Candidate Gap, Research Question, Theory, Construct/Hypothesis, Research Model, Data, Method, Expected Contribution, Reference를 하나의 proposal 흐름으로 연결합니다.

## Research territory taxonomy / 연구영역 분류체계

![Hierarchical research territory taxonomy](docs/screenshots/08-research-taxonomy-hierarchy.png)

The corpus uses six overlapping top-level research axes. They are navigation structures rather than mutually exclusive academic labels, so counts across axes do not sum to the canonical corpus total.

코퍼스는 서로 중복 가능한 6개의 상위 연구축을 사용합니다. 상호 배타적인 학술 분류가 아니라 연구 탐색을 위한 navigation structure이므로 연구축별 논문 수의 합계는 canonical corpus 전체 수와 일치하지 않습니다.

1. **AI adoption and business value / AI 도입과 비즈니스 가치** — adoption, implementation, productivity, performance, ROI, capability, complementary assets
2. **AI-enabled organizational change / AI 기반 조직 변화** — decision-making, job/work redesign, human–AI collaboration, teams, leadership, knowledge work
3. **AI governance and responsible deployment / AI 거버넌스와 책임 있는 도입** — trust, explainability, regulation, compliance, fairness, accountability, risk, oversight
4. **Technology and innovation management / 기술·혁신 경영** — technology strategy, R&D, diffusion, innovation outcomes, dynamic capabilities, absorptive capacity
5. **Agentic systems and enterprise workflows / 에이전틱 시스템과 기업 워크플로** — multi-agent coordination, workflow automation, delegation, oversight, enterprise integration
6. **Industrial AI and smart operations / 산업 AI와 스마트 운영** — digital twins, predictive maintenance, smart manufacturing, supply chain, quality/yield, robotics

High-volume branches can be decomposed again while preserving their parent context. These labels are transparent research-navigation heuristics, not claims that a paper's scholarly contribution has been manually classified and verified.

논문량이 큰 branch는 상위 맥락을 유지한 채 다시 세분화할 수 있습니다. 이 taxonomy는 탐색을 돕기 위한 투명한 research-navigation heuristic이며, 개별 논문의 학술적 기여를 사람이 검증한 분류라고 주장하지 않습니다.

## Retrieval evidence / 검색 성능 근거

The project keeps a historical **529-paper evaluation snapshot** so retrieval changes can be compared against the same reference set. The evaluation contains 20 manually curated AI × MOT queries.

검색 방식의 변화를 같은 기준에서 비교하기 위해 historical **529-paper evaluation snapshot**을 유지합니다. 평가 세트는 사람이 직접 정리한 AI × MOT query 20개로 구성됩니다.

| Retrieval mode | Recall@5 | Recall@10 | nDCG@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: |
| Lexical | 0.3750 | 0.7750 | 0.4638 | 0.4110 |
| Vector (`local_hash`) | 0.3833 | 0.5083 | 0.3901 | 0.4336 |
| Hybrid RRF (`local_hash`) | 0.7000 | 0.7833 | 0.6554 | 0.6875 |
| Vector (FastEmbed MiniLM) | 0.6083 | 0.7500 | 0.5978 | 0.6573 |
| **Hybrid RRF (FastEmbed MiniLM)** | **0.8083** | **0.9583** | **0.8120** | **0.8196** |

On this snapshot, FastEmbed MiniLM + Hybrid RRF produced the strongest measured retrieval result. An additional cross-encoder reranker reduced the tracked metrics against the same candidate pool, so more model complexity was not treated as an automatic improvement.

이 snapshot에서는 FastEmbed MiniLM + Hybrid RRF가 가장 높은 측정값을 보였습니다. 동일 candidate pool에 cross-encoder reranker를 추가했을 때는 오히려 지표가 낮아져, 모델 복잡도를 늘리는 것 자체를 개선으로 간주하지 않았습니다.

The live corpus continues to grow, so the 529-paper snapshot is a reproducible evaluation reference rather than a claim about the current corpus size.

실제 production corpus는 계속 확장되므로 529편은 현재 논문 수를 의미하지 않고, retrieval 비교를 위한 재현 가능한 evaluation reference입니다.

## Evidence principles / 근거 설계 원칙

The product deliberately prefers incomplete but traceable research state over polished unsupported synthesis.

이 제품은 그럴듯하지만 근거가 없는 synthesis보다 **불완전하더라도 추적 가능한 연구 상태**를 우선합니다.

- Important claims keep paper/chunk evidence links.  
  중요한 claim은 paper/chunk evidence link를 유지합니다.
- `fact`, `paper_claim`, `system_inference`, and `user_note` remain different states.  
  `fact`, `paper_claim`, `system_inference`, `user_note`를 서로 다른 상태로 유지합니다.
- Unsupported fields remain `insufficient_evidence`.  
  근거가 없는 필드는 `insufficient_evidence`로 남깁니다.
- Sparse corpus coverage is a gap hypothesis to challenge, not proof of absence.  
  코퍼스 coverage가 낮다는 사실은 반증해야 할 gap hypothesis이며 연구 부재의 증명이 아닙니다.
- Higher-level synthesis uses reviewed Research Cards rather than silently promoting machine extraction.  
  상위 synthesis는 machine extraction을 그대로 승격하지 않고 reviewed Research Card를 사용합니다.
- English scholarly metadata remains canonical while Korean localization acts as a provenance-aware presentation and search layer.  
  영어 scholarly metadata를 canonical로 유지하고 한국어 localization은 provenance가 있는 표현·검색 layer로 사용합니다.

This distinction is the core of the product: AI can accelerate research organization and synthesis, but the workspace should make it easier—not harder—to see **what the evidence is, where it came from, and what remains uncertain**.

이 구분이 프로젝트의 핵심입니다. AI가 연구 정리와 synthesis를 빠르게 만들 수는 있지만, 결과적으로 **근거가 무엇인지, 어디에서 왔는지, 무엇이 아직 불확실한지** 더 쉽게 볼 수 있어야 합니다.

## What is implemented / 구현 내용

- Live corpus observatory with hierarchical AI × MOT territory exploration.  
  계층형 AI × MOT 연구영역 탐색을 제공하는 live corpus observatory.
- Lexical, vector, and Hybrid RRF scholarly retrieval with explicit evidence scope.  
  Explicit evidence scope를 가진 lexical, vector, Hybrid RRF scholarly retrieval.
- Structured Paper Research Cards with machine-candidate / reviewed-state separation.  
  Machine candidate와 reviewed state를 분리한 구조화 Paper Research Card.
- Persistent Research Question workspaces with literature tiers and research-state hand-offs.  
  Literature tier와 research-state hand-off를 포함한 persistent Research Question workspace.
- Evidence comparison matrices that preserve evidence, inference, note, and insufficient-evidence state.  
  Evidence, inference, note, insufficient-evidence 상태를 보존하는 comparison matrix.
- Gap falsification workflow with broader-query and citation-neighbor expansion.  
  Broad query와 citation-neighbor 확장을 포함한 Gap falsification workflow.
- Research direction, design, and proposal-building flow over the same evidence model.  
  같은 evidence model 위에서 이어지는 research direction, design, proposal-building flow.
- OpenAlex-centered scholarly acquisition with DOI/OpenAlex canonical identity resolution.  
  DOI/OpenAlex canonical identity resolution을 사용하는 OpenAlex 중심 scholarly acquisition.
- Normalized scholarly entities, chunks, embeddings, citations, claims, and evidence links.  
  정규화된 scholarly entity, chunk, embedding, citation, claim, evidence link.
- English/Korean research presentation while preserving canonical scholarly metadata.  
  Canonical scholarly metadata를 보존하는 English/Korean 연구 표현.

## Architecture & Topics / 아키텍처 및 주제

```text
Next.js / React / TypeScript
          ↓
Research workflows + visualization
          ↓
FastAPI / Pydantic / SQLAlchemy
          ↓
┌───────────────┬────────────────┬────────────────────┐
│ ingestion     │ retrieval      │ research services  │
│ provenance    │ FTS + pgvector │ cards / RQ / gap   │
│ acquisition   │ Hybrid RRF     │ compare / proposal │
└───────────────┴────────────────┴────────────────────┘
          ↓
PostgreSQL + pgvector
          ↓
papers / authors / topics / chunks / embeddings
citations / research cards / questions / claims / evidence links
```

**Architecture / 아키텍처**  
[`evidence-first`](https://github.com/topics/evidence-first) · [`information-retrieval`](https://github.com/topics/information-retrieval) · [`hybrid-search`](https://github.com/topics/hybrid-search) · [`vector-search`](https://github.com/topics/vector-search) · [`provenance`](https://github.com/topics/provenance) · [`data-lineage`](https://github.com/topics/data-lineage) · [`human-in-the-loop`](https://github.com/topics/human-in-the-loop) · [`normalized-data`](https://github.com/topics/normalized-data) · [`full-stack`](https://github.com/topics/full-stack)

**Project context / 프로젝트 맥락**  
[`management-of-technology`](https://github.com/topics/management-of-technology) · [`research-intelligence`](https://github.com/topics/research-intelligence) · [`literature-review`](https://github.com/topics/literature-review) · [`scholarly-data`](https://github.com/topics/scholarly-data) · [`bibliometrics`](https://github.com/topics/bibliometrics) · [`research-methods`](https://github.com/topics/research-methods) · [`technology-management`](https://github.com/topics/technology-management) · [`innovation-management`](https://github.com/topics/innovation-management) · [`ai-governance`](https://github.com/topics/ai-governance) · [`organizational-change`](https://github.com/topics/organizational-change) · [`graduate-research`](https://github.com/topics/graduate-research)

**Implementation stack / 구현 스택**  
[`nextjs`](https://github.com/topics/nextjs) · [`react`](https://github.com/topics/react) · [`typescript`](https://github.com/topics/typescript) · [`fastapi`](https://github.com/topics/fastapi) · [`python`](https://github.com/topics/python) · [`postgresql`](https://github.com/topics/postgresql) · [`pgvector`](https://github.com/topics/pgvector) · [`sqlalchemy`](https://github.com/topics/sqlalchemy) · [`pydantic`](https://github.com/topics/pydantic) · [`d3`](https://github.com/topics/d3)
