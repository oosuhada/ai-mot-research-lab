# Reference Adoption

## Adopted in Code

| Reference | License | Files / feature used | Changes made | Credit location |
| --- | --- | --- | --- | --- |
| D3 `d3-scale` | ISC | `apps/web/src/components/CitationAtlas.tsx` | Encodes independent research-axis volume as comparable evidence-band lengths and maps publication-year counts into territory/corpus sparklines | `CREDITS.md` |
| Motion | MIT | `apps/web/src/components/CitationAtlas.tsx` | Reorders research-axis bands when the analytical lens changes while preserving spatial continuity; `useReducedMotion()` removes nonessential motion | `CREDITS.md` |

## Visual Principles Adopted

| Reference | Observed principle | Our interpretation | Where visible |
| --- | --- | --- | --- |
| Graphite | Professional editors keep object identity, state, and controls visible in the same working surface | Corpus Observatory keeps the selected territory, evidence-depth diagnostics, methods, drill-down, and next actions in one inspector rather than sending the user through modal/card hops | Home `CitationAtlas` |
| Excalidraw | Spatial navigation should be justified by actual relationships rather than decorative free-pan space | The old empty pan/zoom corpus canvas was removed; spatial interaction remains only where the Gap Canvas has real argument relationships | Home `CitationAtlas`, Gap Canvas `EvidenceWorkspace` |
| Onlook | Object/task context precedes secondary controls | Research question and evidence object come before engineering controls | Home, Library, Evidence Chat |
| Open Generative UI | Interface should organize around task state, not chat chrome | Evidence protocol and source ledger precede the conversational synthesis | Evidence Chat |
| genui-canvas | State and spatial representation stay synchronized | Gap claim, support state, paper, and research-question relationships share one argument model | Gap Canvas |
| D3 hierarchy documentation | Hierarchical layouts are useful only when the data is truly a partition/hierarchy | A treemap prototype was rejected for top-level axes because papers may belong to multiple axes; subareas are shown as explicit overlapping drill-down instead | Home `CitationAtlas` |

## Investigated but Rejected

| Reference | Reason rejected |
| --- | --- |
| D3 treemap / hierarchy | Visually strong, but top-level research axes overlap. A partition-based treemap would imply a false additive whole and was therefore rejected for the main corpus view. |
| xyflow | Strong fit for actual node/edge editors, but the corpus overview has only six top-level axes and does not need arbitrary graph editing; using it here would recreate the old empty-canvas problem. |
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

- Corpus Observatory evidence bands are keyboard-focusable buttons and can be sorted by corpus volume, full-text evidence ratio, or recent local coverage.
- Selecting an axis synchronizes evidence-depth ratios, local year coverage, top methodology signals, optional subareas, and the Library browse action.
- Subarea drill-down uses the same real Library topic filter; it is not a dead-end visual state.
- D3 scales consume API-provided counts; no visual sample data is synthesized. Axis bands are independent comparisons because axis membership can overlap.
- Motion is disabled by user preference through `useReducedMotion()` and existing CSS reduced-motion rules.
- Library selection, Compare links, Evidence Chat scope, provenance links, and Server Action contracts remain unchanged underneath the new structures.

## Screenshot status

No README screenshot, comparison screenshot, after screenshot, or GIF has been generated in this work session. Visual assets remain intentionally pending user approval.

