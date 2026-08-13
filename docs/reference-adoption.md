# Reference Adoption

## Adopted in Code

| Reference | License | Files / feature used | Changes made | Credit location |
| --- | --- | --- | --- | --- |
| D3 `d3-scale` | ISC | `apps/web/src/components/CitationAtlas.tsx` | Uses linear scales to encode real axis paper counts as territory radii and publication-year counts as ledger heights | `CREDITS.md` |
| Motion | MIT | `apps/web/src/components/CitationAtlas.tsx` | Adds restrained state/entry transitions and uses `useReducedMotion()` so the atlas remains usable without animation | `CREDITS.md` |

## Visual Principles Adopted

| Reference | Observed principle | Our interpretation | Where visible |
| --- | --- | --- | --- |
| Graphite | Relationships and editing context are visible on the working surface | Evidence relationships remain spatial and typed instead of becoming summary cards | Gap Canvas `EvidenceWorkspace` |
| Excalidraw | Canvas navigation is primary for spatial reasoning | Map-first evidence argument traversal with pan/zoom and direct node inspection | Gap Canvas `EvidenceWorkspace` |
| Onlook | Object/task context precedes secondary controls | Research question and evidence object come before engineering controls | Home, Library, Evidence Chat |
| Open Generative UI | Interface should organize around task state, not chat chrome | Evidence protocol and source ledger precede the conversational synthesis | Evidence Chat |
| genui-canvas | State and spatial representation stay synchronized | Gap claim, support state, paper, and research-question relationships share one argument model | Gap Canvas |

## Investigated but Rejected

| Reference | Reason rejected |
| --- | --- |
| xyflow | Strong fit, but the existing typed Evidence Workspace already supplies the required graph, viewport, focus, and inspection behavior; replacement would be dependency churn rather than a product improvement. |
| Rough.js | Hand-drawn annotation would weaken the precise scholarly-document tone. |
| Sigma.js | Optimized for larger network exploration than the current claim-level argument map needs. |
| Cytoscape.js | No current graph-layout requirement justifies a second graph dependency. |
| React Three Fiber | 3D space would add GPU and accessibility complexity without improving evidence interpretation. |

## License Verification

- [x] `d3-scale` package license opened and read: ISC, copyright Mike Bostock.
- [x] Motion package license opened and read: MIT, copyright Motion B.V.
- [x] Attribution requirements recorded in `CREDITS.md`.
- [x] No unknown-license code copied.
- [x] No incompatible copyleft dependency introduced.
- [x] Unused investigated candidates were not installed.

## Interaction Proof

- Citation Atlas axis nodes are keyboard-focusable links to the real Library browse filter.
- Hover and keyboard focus update the same territory explanation.
- D3 scales consume API-provided counts; no visual sample data is synthesized.
- Motion is disabled by user preference through `useReducedMotion()` and existing CSS reduced-motion rules.
- Library selection, Compare links, Evidence Chat scope, provenance links, and Server Action contracts remain unchanged underneath the new structures.

## Screenshot status

No README screenshot, comparison screenshot, after screenshot, or GIF has been generated in this work session. Visual assets remain intentionally pending user approval.

