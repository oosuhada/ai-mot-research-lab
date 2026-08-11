import { createGapCanvas, editGapCanvas } from "./actions";
import { getGapAnalysis } from "@/lib/api";

const editableSections = [
  ["research_clusters", "Representative research clusters"],
  ["agreements", "Agreements"],
  ["conflicts", "Conflicts"],
  ["under_studied_contexts", "Under-studied contexts / coverage signals"],
  ["gap_candidates", "Gap candidates"],
  ["falsifiability_notes", "How to falsify the candidate gap"],
  ["follow_up_questions", "Follow-up research questions"],
  ["theoretical_lenses", "Candidate theoretical lenses"],
  ["candidate_data_methods", "Candidate data and methods"],
] as const;

export default async function GapCanvasPage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const params = await searchParams;
  const analysis = params.id ? await getGapAnalysis(params.id) : null;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Research Question & Gap Canvas</p>
          <h2 className="pageTitle">Treat a gap as a hypothesis to falsify.</h2>
          <p className="pageIntro">
            Retrieval coverage can suggest where to look, but sparse results are never presented as proof that a
            research gap exists. Generated fields remain editable and evidence status stays visible.
          </p>
        </div>
      </header>

      {!analysis ? (
        <section className="card">
          <form className="searchBar searchBarWrap" action={createGapCanvas}>
            <input
              className="input"
              name="topic"
              required
              minLength={3}
              placeholder="e.g. How does AI capability change innovation performance in manufacturing SMEs?"
            />
            <button className="button" type="submit">Create saved canvas</button>
          </form>
        </section>
      ) : (
        <div className="grid">
          <section className="card span12">
            <div className="resultSummary">
              <strong>{analysis.research_question}</strong>
              <span className="pill">{analysis.status}</span>
              <span className="pill">candidate hypotheses, not conclusions</span>
            </div>
            <div className="policyGrid">
              <div><span className="metricLabel">Search strategy</span><p>{analysis.search_strategy}</p></div>
              <div><span className="metricLabel">Include</span><p>{analysis.inclusion_criteria}</p></div>
              <div><span className="metricLabel">Exclude</span><p>{analysis.exclusion_criteria}</p></div>
            </div>
          </section>

          <section className="card span8">
            <h3 className="sectionTitle">Editable canvas</h3>
            <form action={editGapCanvas.bind(null, analysis.id)} className="editorStack">
              {editableSections.map(([field, label]) => (
                <label className="editorField" key={field}>
                  <span>{label}</span>
                  <textarea
                    className="input textarea"
                    name={field}
                    defaultValue={analysis[field] ?? ""}
                    rows={4}
                  />
                </label>
              ))}
              <button className="button" type="submit">Save my edits</button>
            </form>
          </section>

          <aside className="card span4">
            <h3 className="sectionTitle">Evidence status</h3>
            <div className="evidenceStack">
              {analysis.evidence_claims.map((claim) => (
                <article className="claimCard" key={claim.id}>
                  <span className={`statusBadge status-${claim.support_status}`}>{claim.support_status}</span>
                  <p>{claim.claim_text}</p>
                  {claim.evidence.slice(0, 4).map((evidence) => (
                    <a
                      className="evidenceLink"
                      key={`${claim.id}-${evidence.paper_id}`}
                      href={evidence.primary_url ?? (evidence.doi ? `https://doi.org/${evidence.doi}` : "#")}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {evidence.paper_title} ↗
                    </a>
                  ))}
                </article>
              ))}
            </div>
          </aside>

          <section className="card span6">
            <h3 className="sectionTitle">Evidence-linked scope distributions</h3>
            <p className="metricHelp">These counts describe the evidence-linked subset of this canvas, not the whole field.</p>
            <h4>Methodology heuristics</h4>
            <div className="tagCloud">{analysis.methodology_distribution.length ? analysis.methodology_distribution.map((item) => <span className="pill" key={item.slug}>{item.display_name}: {item.paper_count}</span>) : <span className="muted">No methodology heuristic evidence.</span>}</div>
            <h4>Publication years</h4>
            <div className="tagCloud">{analysis.year_distribution.map((item) => <span className="pill" key={item.year}>{item.year}: {item.paper_count}</span>)}</div>
          </section>

          <section className="card span6">
            <h3 className="sectionTitle">Structured candidate gap hypothesis</h3>
            {analysis.candidate_gap ? <div className="formStack">
              <span className="statusBadge status-insufficient_evidence">{analysis.candidate_gap.support_status}</span>
              <div><span className="metricLabel">Hypothesis</span><p>{analysis.candidate_gap.hypothesis}</p></div>
              <div><span className="metricLabel">Evidence for</span>{analysis.candidate_gap.evidence_for.map((item) => <p key={item}>{item}</p>)}</div>
              <div><span className="metricLabel">Evidence against / invalidation risk</span>{analysis.candidate_gap.evidence_against.map((item) => <p key={item}>{item}</p>)}</div>
              <div><span className="metricLabel">Falsifiability</span><p>{analysis.candidate_gap.falsifiability_note}</p></div>
              <div><span className="metricLabel">Next search query</span><code className="queryCode">{analysis.candidate_gap.next_search_query}</code></div>
              <div><span className="metricLabel">Candidate method</span><p>{analysis.candidate_gap.candidate_method ?? "Not specified."}</p></div>
            </div> : null}
          </section>
        </div>
      )}
    </>
  );
}
