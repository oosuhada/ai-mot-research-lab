# Visual Reference Catalog

This project interprets the shared `AI-UX-REFERENCE-CATALOG.md` through a scholarly-research product lens. The goal is not to reproduce showcase effects; every adopted principle must improve evidence navigation, provenance visibility, uncertainty handling, or the research-question workflow.

## Candidates reviewed

| Reference | License posture | Relevant idea | Decision |
| --- | --- | --- | --- |
| D3 / d3-scale | ISC | Encode quantitative coverage spatially without a dashboard chart wrapper | Adopted in Citation Atlas |
| Motion | MIT | Small state transitions with reduced-motion support | Adopted in Citation Atlas |
| xyflow | MIT | Directed evidence graph, viewport controls, node/edge semantics | Compared; existing custom Evidence Workspace retained |
| Graphite | Apache-2.0 | Professional node-editor hierarchy and inspectable connections | Visual principle only |
| Excalidraw | MIT | Canvas-first navigation and spatial argument tracing | Visual principle only |
| Rough.js | MIT | Editorial annotation marks and hand-drawn boundaries | Rejected; would reduce scholarly precision here |
| Sigma.js | MIT | Large graph exploration | Rejected; current evidence graph is small and typed |
| Cytoscape.js | MIT | Graph layout and relationship inspection | Rejected; unnecessary dependency for current graph size |
| Onlook | Apache-2.0 | Editor hierarchy: object first, controls second | Visual principle only |
| Open Generative UI | MIT | UI assembled around task state rather than chat chrome | Visual principle only |
| genui-canvas | MIT | Canvas state and task state remain synchronized | Visual principle only |
| React Three Fiber | MIT | Spatial information environments | Rejected; 3D adds no evidence value to this research workflow |

## Product translation

### Landscape → Citation Atlas

The home route no longer presents a collection of independent dashboard cards. The DOM now progresses from a research-question ledger to an interactive Citation Atlas and then to a corpus field journal. D3 scales encode real research-axis counts as territory size and real publication-year counts as a temporal ledger. Motion is limited to focus/hover/entry transitions and respects `prefers-reduced-motion`.

### Library → Scholarly Index

Search and browse results render as a numbered scholarly index. Every result has a bibliographic line, title, annotation or abstract, and a marginal evidence/retrieval column. Real hybrid scores and evidence locators remain inspectable rather than being replaced with decorative relevance labels.

### Paper Detail → Reading Document

The paper route is organized as a reading document: title and source context, abstract body, marginal reading state, then bibliographic/provenance apparatus. The research record is no longer laid out as a dashboard grid.

### Compare → Field-by-field Argument Notebook

The loaded comparison route no longer depends on a wide HTML table. Each comparison field is a horizontal argument band containing one evidence entry per paper, with support state, origin, claim kind, and evidence footnotes visible beside the text.

### Gap Canvas → Evidence Argument Map

The existing custom `EvidenceWorkspace` remains map-first because it already models the required argument chain: research question → research cluster → paper → claim → support state → candidate gap. xyflow, Graphite, and Excalidraw were evaluated as references, but replacing the existing implementation would add dependency and migration cost without improving the current typed evidence semantics.

### Evidence Chat → Evidence Protocol

The chat route now places scope, locator expectations, provenance policy, and unsupported-claim handling before the question composer. When an answer exists, the source ledger precedes the synthesis in DOM order so the mobile experience is evidence-first rather than a shrunken desktop chat layout.

## Guardrails

- No visualization invents papers, citations, scores, or relationships.
- Coverage density is explicitly labeled as corpus coverage, not field importance or gap proof.
- `paper_evidence`, `system_inference`, and `user_note` semantics remain distinct.
- `insufficient_evidence` remains a first-class state.
- Public-demo write restrictions remain enforced by both UI and API policy.
- Dependencies are retained only when used by a core interaction.

