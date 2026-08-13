import Link from "next/link";

import {
  BROWSER_API_BASE_URL,
  getComparisonSet,
  getPaper,
  listComparisonSets,
  searchPapers,
  type PaperDetail,
} from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { createComparisonFromIds, createComparisonFromTopic, editComparisonCellAction } from "./actions";

const fields = [
  ["research_question", "Research question"], ["theoretical_lens", "Theoretical lens"],
  ["unit_of_analysis", "Unit of analysis"], ["context_industry_country", "Context / industry / country"],
  ["dataset_and_sample", "Dataset and sample"], ["methodology", "Methodology"],
  ["variables_or_constructs", "Variables or constructs"], ["findings", "Findings"],
  ["limitations", "Limitations"], ["claimed_contribution", "Claimed contribution"],
  ["future_research", "Future research"],
] as const;

type CompareSearchParams = {
  id?: string;
  paper?: string;
  papers?: string;
  q?: string;
};

function parsePaperIds(params: CompareSearchParams) {
  return [...new Set((params.papers ?? params.paper ?? "").split(",").map((value) => value.trim()).filter(Boolean))].slice(0, 6);
}

function pickerHref(ids: string[], query: string) {
  const search = new URLSearchParams();
  if (ids.length) search.set("papers", ids.join(","));
  if (query) search.set("q", query);
  return `/compare?${search.toString()}`;
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<CompareSearchParams> }) {
  const params = await searchParams;
  const comparison = params.id ? await getComparisonSet(params.id) : null;
  const readOnly = isWorkspaceReadOnly();
  const existingComparisons = await listComparisonSets();

  if (comparison) {
    return (
      <>
        <header className="pageHeader">
          <div>
            <p className="eyebrow">Compare Papers</p>
            <h2 className="pageTitle">Compare study design with evidence and origin visible.</h2>
            <p className="pageIntro">Evidence-backed cells stay distinct from system inference. Unsupported fields remain explicit rather than being filled with plausible text.</p>
          </div>
        </header>

        <section className="card comparisonCard">
          <div className="resultSummary comparisonSummary">
            <div><strong>{comparison.name}</strong><span className="pill">{comparison.papers.length} papers</span></div>
            <div className="comparisonSummaryActions">
              <Link className="textLink" href={`/chat?scope=comparison_set&ids=${comparison.id}`}>Ask about this comparison →</Link>
              <a className="textLink" href={`${BROWSER_API_BASE_URL}/api/v1/comparison-sets/${comparison.id}/export?format=markdown`}>Export Markdown ↗</a>
              <a className="textLink" href={`${BROWSER_API_BASE_URL}/api/v1/comparison-sets/${comparison.id}/export?format=csv`}>Export CSV ↗</a>
            </div>
          </div>
          <div className="tableScroller">
            <table className="comparisonTable">
              <thead>
                <tr>
                  <th>Field</th>
                  {comparison.papers.map((paper) => <th key={paper.id}><span className="tablePaperYear">{paper.publication_year ?? "—"}</span>{paper.title}</th>)}
                </tr>
              </thead>
              <tbody>
                {fields.map(([fieldName, label]) => (
                  <tr key={fieldName}>
                    <th>{label}</th>
                    {comparison.papers.map((paper) => {
                      const cell = comparison.cells.find((candidate) => candidate.paper_id === paper.id && candidate.field_name === fieldName);
                      return (
                        <td key={paper.id}>
                          {cell ? (
                            <>
                              <div className="rankRow">
                                <span className={`statusBadge status-${cell.support_status}`}>{cell.support_status}</span>
                                <span className="pill">origin: {cell.origin.replaceAll("_", " ")}</span>
                                <span className="pill">{cell.claim_kind.replaceAll("_", " ")}</span>
                              </div>
                              <p>{cell.value_text}</p>
                              {cell.evidence.map((evidence, index) => (
                                <a className="evidenceLink" key={`${cell.id}-${index}`} href={evidence.primary_url ?? (evidence.doi ? `https://doi.org/${evidence.doi}` : "#")} target="_blank" rel="noreferrer">
                                  Evidence: {evidence.source_locator ?? "paper"} ↗
                                </a>
                              ))}
                              {!readOnly ? (
                                <details className="comparisonEdit">
                                  <summary>Edit as user note</summary>
                                  <form action={editComparisonCellAction.bind(null, comparison.id, cell.id)} className="formStack">
                                    <textarea className="textarea" name="value_text" defaultValue={cell.value_text ?? ""} />
                                    <input className="input" name="evidence_chunk_id" placeholder="Optional evidence chunk ID" />
                                    <button className="button" type="submit">Save cell</button>
                                  </form>
                                </details>
                              ) : null}
                            </>
                          ) : <span className="muted">No cell.</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </>
    );
  }

  const selectedIds = parsePaperIds(params);
  const selectedPapers = (await Promise.all(selectedIds.map((id) => getPaper(id)))).filter((paper): paper is PaperDetail => Boolean(paper));
  const pickerQuery = params.q?.trim() ?? "";
  const pickerResults = pickerQuery ? await searchPapers(pickerQuery, "hybrid") : null;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Compare Papers</p>
          <h2 className="pageTitle">Choose papers by title, not by database ID.</h2>
          <p className="pageIntro">Select 2–6 papers from Library or search here. The comparison keeps claim origin and evidence support visible at cell level.</p>
        </div>
      </header>

      {existingComparisons.length ? (
        <section className="existingComparisonStrip">
          <div><span className="cardKicker">Ready to inspect</span><strong>Saved comparison sets</strong></div>
          <div className="existingComparisonLinks">
            {existingComparisons.slice(0, 6).map((item) => <Link className="pill" href={`/compare?id=${item.id}`} key={item.id}>{item.name} · {item.paper_count}</Link>)}
          </div>
        </section>
      ) : null}

      <section className="compareBuilder">
        <article className="comparePickerPanel">
          <div className="sectionHeadingRow">
            <div><span className="cardKicker">Paper picker</span><h3 className="sectionTitle">Build a comparison set</h3></div>
            <span className="pill">{selectedPapers.length}/6 selected</span>
          </div>

          <form className="compareSearchForm" action="/compare" method="get">
            {selectedIds.length ? <input type="hidden" name="papers" value={selectedIds.join(",")} /> : null}
            <label className="srOnly" htmlFor="compare-paper-search">Find papers to compare</label>
            <input className="input" id="compare-paper-search" name="q" defaultValue={pickerQuery} placeholder="Search paper titles, concepts, or methods…" />
            <button className="button buttonSecondary" type="submit">Find papers</button>
          </form>

          {selectedPapers.length ? (
            <div className="selectedPaperList">
              {selectedPapers.map((paper, index) => {
                const nextIds = selectedIds.filter((id) => id !== paper.id);
                return (
                  <div className="selectedPaperRow" key={paper.id}>
                    <span className="selectedPaperIndex">{String(index + 1).padStart(2, "0")}</span>
                    <div><strong>{paper.title}</strong><span>{paper.publication_year ?? "Year unknown"} · {paper.citation_count} citations</span></div>
                    <Link className="textLink" href={pickerHref(nextIds, pickerQuery)}>Remove</Link>
                  </div>
                );
              })}
            </div>
          ) : <div className="pickerEmpty">No papers selected yet. Select from Library or search below.</div>}

          {selectedIds.length ? (
            <div className="compareSelectionActions">
              <Link className="secondaryButton" href={`/chat?scope=papers&ids=${encodeURIComponent(selectedIds.join(","))}`}>Ask selected papers with evidence →</Link>
            </div>
          ) : null}

          {pickerResults ? (
            <div className="compareSearchResults">
              {pickerResults.items.slice(0, 8).map((paper) => {
                const selected = selectedIds.includes(paper.id);
                const nextIds = selected ? selectedIds.filter((id) => id !== paper.id) : [...selectedIds, paper.id].slice(0, 6);
                return (
                  <div className={`compareSearchResult${selected ? " compareSearchResultSelected" : ""}`} key={paper.id}>
                    <div><strong>{paper.title}</strong><span>{paper.publication_year ?? "Year unknown"} · {paper.citation_count} citations</span></div>
                    <Link className="paperSelectButton" href={pickerHref(nextIds, pickerQuery)}>{selected ? "✓ Added" : "+ Add"}</Link>
                  </div>
                );
              })}
            </div>
          ) : null}

          {!readOnly ? (
            <form className="createComparisonBar" action={createComparisonFromIds}>
              <input type="hidden" name="paper_ids" value={selectedIds.join(",")} />
              <label className="compactFieldLabel"><span>Comparison name</span><input className="input" name="name" placeholder="e.g. AI capability mechanisms" /></label>
              <button className="button" type="submit" disabled={selectedIds.length < 2}>Create comparison</button>
            </form>
          ) : <div className="readOnlyPanel"><strong>Public Demo · Read-only</strong><span>Use an existing comparison above to inspect the evidence matrix. Creating new sets is disabled on the portfolio deployment.</span></div>}
        </article>

        <aside className="compareTopicPanel">
          <span className="cardKicker">Fast path</span>
          <h3 className="sectionTitle">Let retrieval propose a starting set</h3>
          <p className="metricHelp">Useful for exploration. You should still inspect why each paper was retrieved before treating the set as representative.</p>
          {!readOnly ? (
            <form className="formStack" action={createComparisonFromTopic}>
              <label className="compactFieldLabel"><span>Research topic</span><input className="input" name="query" required minLength={2} placeholder="AI capability and firm performance" /></label>
              <button className="button buttonSecondary" type="submit">Compare top 3 candidates</button>
            </form>
          ) : <Link className="secondaryButton" href="/library">Select papers in Library →</Link>}
        </aside>
      </section>
    </>
  );
}
