import { challengeGapCanvas, createGapCanvas, editGapCanvas } from "./actions";
import EvidenceWorkspace from "./EvidenceWorkspace";
import { getGapAnalysis, getResearchQuestion } from "@/lib/api";

const editableSections = [
  ["research_clusters", "Representative research clusters"],
  ["agreements", "Agreements"],
  ["conflicts", "Conflicts"],
  ["under_studied_contexts", "Under-studied contexts / coverage signals"],
  ["gap_candidates", "Candidate gap hypothesis"],
  ["falsifiability_notes", "How to falsify the candidate hypothesis"],
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
  const researchQuestion = analysis ? await getResearchQuestion(analysis.research_question_id) : null;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Research Question & Gap Canvas</p>
          <h2 className="pageTitle">Map the evidence before naming the gap.</h2>
          <p className="pageIntro">
            Trace research axes, papers, claims, support states, and candidate hypotheses without turning sparse
            retrieval into a conclusion. Paper claims, system inferences, and user notes remain visibly distinct.
          </p>
        </div>
      </header>

      {!analysis ? (
        <div className="grid">
          <section className="card span12">
            <div className="emptyState">
              <p className="eyebrow">Start an evidence map</p>
              <h3 className="sectionTitle">Ask a research question worth pressure-testing.</h3>
              <p>
                The canvas will retrieve local literature, expose evidence-linked research axes, separate claims by
                origin and support state, and frame any apparent gap as a candidate hypothesis that still needs
                falsification.
              </p>
              <form className="searchBar searchBarWrap" action={createGapCanvas}>
                <input
                  className="input"
                  name="topic"
                  required
                  minLength={3}
                  placeholder="e.g. How does AI capability change innovation performance in manufacturing SMEs?"
                />
                <button className="button" type="submit">Build evidence canvas</button>
              </form>
            </div>
          </section>
          <section className="card span4">
            <span className="metricLabel">01 · Retrieve</span>
            <h3 className="sectionTitle">Find relevant evidence</h3>
            <p className="metricHelp">Hybrid retrieval identifies a review set. Retrieval density is treated as coverage, not proof.</p>
          </section>
          <section className="card span4">
            <span className="metricLabel">02 · Structure</span>
            <h3 className="sectionTitle">Connect papers to claims</h3>
            <p className="metricHelp">Evidence links and research-axis taxonomy become a navigable Matrix and Map.</p>
          </section>
          <section className="card span4">
            <span className="metricLabel">03 · Challenge</span>
            <h3 className="sectionTitle">Falsify the candidate</h3>
            <p className="metricHelp">The final node is always a hypothesis to test against broader search, adjacent theories, and citation chains.</p>
          </section>
        </div>
      ) : (
        <>
          <EvidenceWorkspace analysis={analysis} history={researchQuestion?.gap_analyses ?? []} />

          <div className="grid">
            <section className="card span6">
              <div className="resultSummary">
                <span className="statusBadge status-insufficient_evidence">Candidate hypothesis</span>
                <span className="pill">Needs falsification</span>
              </div>
              <h3 className="sectionTitle">Structured candidate hypothesis</h3>
              {analysis.candidate_gap ? (
                <div className="formStack">
                  <div><span className="metricLabel">Hypothesis</span><p>{analysis.candidate_gap.hypothesis}</p></div>
                  <div><span className="metricLabel">Evidence currently supporting the signal</span>{analysis.candidate_gap.evidence_for.length ? analysis.candidate_gap.evidence_for.map((item) => <p key={item}>{item}</p>) : <p className="muted">No supported evidence claim is linked yet.</p>}</div>
                  <div><span className="metricLabel">Invalidation risk</span>{analysis.candidate_gap.evidence_against.map((item) => <p key={item}>{item}</p>)}</div>
                  <div><span className="metricLabel">Falsifiability</span><p>{analysis.candidate_gap.falsifiability_note}</p></div>
                  <div><span className="metricLabel">Next search query</span><code className="queryCode">{analysis.candidate_gap.next_search_query}</code></div>
                  <div><span className="metricLabel">Candidate method</span><p>{analysis.candidate_gap.candidate_method ?? "Not specified."}</p></div>
                  <form action={challengeGapCanvas.bind(null, analysis.research_question_id, analysis.candidate_gap.next_search_query)} className="formStack">
                    <button className="button" type="submit">Run broader falsification pass</button>
                    <p className="metricHelp">Creates a new analysis history entry with a broader 40-paper retrieval pass. New citation neighbors remain unscreened candidates until reviewed.</p>
                  </form>
                </div>
              ) : <div className="emptyState">No candidate hypothesis has been structured yet.</div>}
            </section>

            <section className="card span6">
              <h3 className="sectionTitle">Evidence-linked scope</h3>
              <p className="metricHelp">These distributions describe only papers linked as evidence on this canvas, not the full literature.</p>
              <h4>Methodology heuristics</h4>
              <div className="tagCloud">
                {analysis.methodology_distribution.length
                  ? analysis.methodology_distribution.map((item) => <span className="pill" key={item.slug}>{item.display_name}: {item.paper_count}</span>)
                  : <span className="muted">No methodology heuristic evidence.</span>}
              </div>
              <h4>Publication years</h4>
              <div className="tagCloud">
                {analysis.year_distribution.length
                  ? analysis.year_distribution.map((item) => <span className="pill" key={item.year}>{item.year}: {item.paper_count}</span>)
                  : <span className="muted">No publication-year distribution.</span>}
              </div>
              <h4>Research axes</h4>
              <div className="tagCloud">
                {analysis.evidence_clusters.length
                  ? analysis.evidence_clusters.map((cluster) => <span className="pill" key={cluster.slug}>{cluster.display_name}: {cluster.paper_ids.length}</span>)
                  : <span className="muted">No research-axis assignments linked to this evidence set.</span>}
              </div>
            </section>

            <section className="card span12">
              <h3 className="sectionTitle">Retrieval and review policy</h3>
              <div className="policyGrid">
                <div><span className="metricLabel">Search strategy</span><p>{analysis.search_strategy}</p></div>
                <div><span className="metricLabel">Include</span><p>{analysis.inclusion_criteria}</p></div>
                <div><span className="metricLabel">Exclude</span><p>{analysis.exclusion_criteria}</p></div>
              </div>
            </section>

            <section className="card span12">
              <div className="resultSummary">
                <h3 className="sectionTitle">Research synthesis notes</h3>
                <span className="pill">User edits become user-note claims</span>
              </div>
              <form action={editGapCanvas.bind(null, analysis.id)} className="editorStack">
                <div className="grid">
                  {editableSections.map(([field, label]) => (
                    <label className="editorField span6" key={field}>
                      <span>{label}</span>
                      <textarea
                        className="input textarea"
                        name={field}
                        defaultValue={analysis[field] ?? ""}
                        rows={4}
                      />
                    </label>
                  ))}
                </div>
                <button className="button" type="submit">Save synthesis notes</button>
              </form>
            </section>
          </div>
        </>
      )}
    </>
  );
}
