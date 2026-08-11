import { BROWSER_API_BASE_URL, getComparisonSet } from "@/lib/api";

import { createComparisonFromIds, createComparisonFromTopic, editComparisonCellAction } from "./actions";

const fields = [
  ["research_question", "Research question"], ["theoretical_lens", "Theoretical lens"],
  ["unit_of_analysis", "Unit of analysis"], ["context_industry_country", "Context / industry / country"],
  ["dataset_and_sample", "Dataset and sample"], ["methodology", "Methodology"],
  ["variables_or_constructs", "Variables or constructs"], ["findings", "Findings"],
  ["limitations", "Limitations"], ["claimed_contribution", "Claimed contribution"],
  ["future_research", "Future research"],
] as const;

export default async function ComparePage({ searchParams }: { searchParams: Promise<{ id?: string; paper?: string }> }) {
  const params = await searchParams;
  const comparison = params.id ? await getComparisonSet(params.id) : null;
  return <>
    <header className="pageHeader"><div><p className="eyebrow">Compare Papers</p><h2 className="pageTitle">Compare study design with evidence and origin visible.</h2><p className="pageIntro">Select 2–6 papers. Private full-text chunks are checked before abstract evidence; anything unsupported remains explicit. Manual edits become user notes unless you attach a chunk ID from the same paper.</p></div></header>
    {!comparison ? <section className="grid">
      <article className="card span6"><h3 className="sectionTitle">Compare by topic</h3><form className="formStack" action={createComparisonFromTopic}><input className="input" name="query" required minLength={2} placeholder="AI capability and firm performance" /><button className="button" type="submit">Compare top 3</button></form></article>
      <article className="card span6"><h3 className="sectionTitle">Compare selected papers</h3><form className="formStack" action={createComparisonFromIds}><input className="input" name="name" placeholder="Comparison name" /><textarea className="textarea" name="paper_ids" required defaultValue={params.paper ?? ""} placeholder="Paste 2–6 paper UUIDs, separated by commas or lines" /><button className="button" type="submit">Create selected comparison</button></form></article>
    </section> : <section className="card comparisonCard">
      <div className="resultSummary"><strong>{comparison.name}</strong><span className="pill">{comparison.papers.length} papers</span><a className="textLink" href={`${BROWSER_API_BASE_URL}/api/v1/comparison-sets/${comparison.id}/export?format=markdown`}>Export Markdown ↗</a><a className="textLink" href={`${BROWSER_API_BASE_URL}/api/v1/comparison-sets/${comparison.id}/export?format=csv`}>Export CSV ↗</a></div>
      <div className="tableScroller"><table className="comparisonTable"><thead><tr><th>Field</th>{comparison.papers.map((paper) => <th key={paper.id}><span className="tablePaperYear">{paper.publication_year ?? "—"}</span>{paper.title}</th>)}</tr></thead><tbody>
        {fields.map(([fieldName, label]) => <tr key={fieldName}><th>{label}</th>{comparison.papers.map((paper) => {
          const cell = comparison.cells.find((candidate) => candidate.paper_id === paper.id && candidate.field_name === fieldName);
          return <td key={paper.id}>{cell ? <><div className="rankRow"><span className={`statusBadge status-${cell.support_status}`}>{cell.support_status}</span><span className="pill">origin: {cell.origin}</span><span className="pill">{cell.claim_kind}</span></div><p>{cell.value_text}</p>{cell.evidence.map((evidence, index) => <a className="evidenceLink" key={`${cell.id}-${index}`} href={evidence.primary_url ?? (evidence.doi ? `https://doi.org/${evidence.doi}` : "#")} target="_blank" rel="noreferrer">Evidence: {evidence.source_locator ?? "paper"} ↗</a>)}<details><summary>Edit as user note</summary><form action={editComparisonCellAction.bind(null, comparison.id, cell.id)} className="formStack"><textarea className="textarea" name="value_text" defaultValue={cell.value_text ?? ""} /><input className="input" name="evidence_chunk_id" placeholder="Optional evidence chunk UUID" /><button className="button" type="submit">Save cell</button></form></details></> : <span className="muted">No cell.</span>}</td>;
        })}</tr>)}
      </tbody></table></div>
    </section>}
  </>;
}
