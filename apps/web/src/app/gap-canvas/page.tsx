import { challengeGapCanvas, createGapCanvas, editGapCanvas } from "./actions";
import EvidenceWorkspace from "./EvidenceWorkspace";
import { MutationFeedback } from "@/components/MutationFeedback";
import { getGapAnalysis, getResearchQuestion, listResearchQuestions } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";
import styles from "./GapCanvas.module.css";

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
  searchParams: Promise<{ id?: string; feedback?: string }>;
}) {
  const params = await searchParams;
  const analysis = params.id ? await getGapAnalysis(params.id) : null;
  const readOnly = isWorkspaceReadOnly();
  const researchQuestion = analysis ? await getResearchQuestion(analysis.research_question_id) : null;
  const demoQuestions = !analysis && readOnly ? await listResearchQuestions() : [];
  const demoGapAnalyses = demoQuestions.flatMap((question) => question.gap_analyses.map((gap) => ({ ...gap, questionTitle: question.title })));
  const linkedPaperCount = analysis
    ? new Set(analysis.evidence_claims.flatMap((claim) => claim.evidence.map((evidence) => evidence.paper_id))).size
    : 0;
  const paperClaimCount = analysis
    ? analysis.evidence_claims.filter((claim) => claim.claim_kind === "paper_claim").length
    : 0;

  return (
    <>
      {!readOnly ? (
        <MutationFeedback
          feedback={params.feedback}
          messages={{
            created: { message: "Gap Canvas created. Treat the candidate as a hypothesis until it survives falsification." },
            challenged: { message: "Broader falsification pass completed and saved as a new analysis entry." },
            updated: { message: "Research synthesis notes saved." },
            "invalid-topic": { message: "Enter a research topic with at least three characters.", tone: "error" },
            "invalid-query": { message: "A falsification search query is required.", tone: "error" },
            error: { message: "The Gap Canvas change could not be completed. Existing evidence was not overwritten.", tone: "error" },
          }}
        />
      ) : null}
      <header className={styles.hero}>
        <div className={styles.heroInner}>
          <div>
            <p className={styles.heroKicker}><span className={styles.heroIndex}>05</span> Research Question · Gap Canvas</p>
            <h1 className={styles.heroTitle}>
              <span className={styles.heroTitleLine}>Map the evidence.</span>
              <span className={styles.heroTitleSignal}>Challenge the gap.</span>
            </h1>
            <p className={styles.heroIntro}>
              A claim-level research instrument for tracing papers, source-backed evidence, support states, and
              falsifiable candidate hypotheses without treating sparse retrieval as proof.
            </p>
            <div className={styles.heroMeta}>
              <span>evidence-first</span>
              <span>claim-level provenance</span>
              <span>candidate ≠ conclusion</span>
            </div>
          </div>
          <div className={styles.instrument} aria-label="Evidence workflow summary">
            <div className={styles.instrumentTop}>
              <span>Evidence instrument</span>
              <span className={styles.instrumentLive}>{analysis ? "analysis loaded" : "ready"}</span>
            </div>
            <div className={styles.instrumentFlow}>
              <div className={styles.instrumentStep}><i /><span>Research question</span><small>input</small></div>
              <div className={styles.instrumentStep}><i /><span>Evidence papers</span><small>{analysis ? linkedPaperCount : "retrieve"}</small></div>
              <div className={styles.instrumentStep}><i /><span>Paper-backed claims</span><small>{analysis ? paperClaimCount : "extract"}</small></div>
              <div className={styles.instrumentStep}><i /><span>Agreement / conflict</span><small>review</small></div>
              <div className={styles.instrumentStep}><i /><span>Candidate hypothesis</span><small>falsify</small></div>
            </div>
          </div>
        </div>
      </header>

      {!analysis ? (
        <section className={styles.launchPanel}>
          <div className={styles.launchComposer}>
            <p className="eyebrow">New analysis</p>
            <h3>Ask a question worth trying to disprove.</h3>
            <p>
              Start from a research question, retrieve the local corpus, inspect source-backed claims, then challenge
              the candidate hypothesis with broader search and citation neighbors.
            </p>
            {!readOnly ? <form className={styles.launchForm} action={createGapCanvas}>
              <input
                name="topic"
                required
                minLength={3}
                placeholder="How does AI capability change innovation performance in manufacturing SMEs?"
              />
              <button type="submit">Build evidence canvas →</button>
            </form> : <div className="readOnlyPanel"><strong>Public Demo · Read-only</strong><span>Create and edit actions are disabled on the portfolio deployment. Open a saved canvas to inspect the evidence map and falsification logic.</span><div className="tagCloud">{demoGapAnalyses.slice(0, 6).map((gap) => <a className="pill" href={`/gap-canvas?id=${gap.id}`} key={gap.id}>{gap.questionTitle}</a>)}</div></div>}
          </div>
          <aside className={styles.launchAside}>
            <div className={styles.launchAsideRow}><span>01</span><div><strong>Retrieve</strong><p>Build a review set without equating density with truth.</p></div></div>
            <div className={styles.launchAsideRow}><span>02</span><div><strong>Trace</strong><p>Move from paper → claim → source locator instead of opaque summaries.</p></div></div>
            <div className={styles.launchAsideRow}><span>03</span><div><strong>Challenge</strong><p>Use contradiction and citation candidates to falsify the hypothesis.</p></div></div>
          </aside>
        </section>
      ) : (
        <>
          <EvidenceWorkspace analysis={analysis} history={researchQuestion?.gap_analyses ?? []} />

          <div className={`grid ${styles.resultGrid}`}>
            <section className={`card span6 ${styles.candidatePanel}`}>
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
                  {!readOnly ? <form action={challengeGapCanvas.bind(null, analysis.id, analysis.research_question_id, analysis.candidate_gap.next_search_query)} className="formStack">
                    <button className="button" type="submit">Run broader falsification pass</button>
                    <p className="metricHelp">Creates a new analysis history entry with a broader 40-paper retrieval pass. New citation neighbors remain unscreened candidates until reviewed.</p>
                  </form> : <p className="metricHelp">Read-only demo: the broader falsification pass is visible as a workflow concept but cannot create a new shared analysis.</p>}
                </div>
              ) : <div className="emptyState">No candidate hypothesis has been structured yet.</div>}
            </section>

            <section className={`card span6 ${styles.scopePanel}`}>
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

            <section className={`card span12 ${styles.policyPanel}`}>
              <h3 className="sectionTitle">Retrieval and review policy</h3>
              <div className="policyGrid">
                <div><span className="metricLabel">Search strategy</span><p>{analysis.search_strategy}</p></div>
                <div><span className="metricLabel">Include</span><p>{analysis.inclusion_criteria}</p></div>
                <div><span className="metricLabel">Exclude</span><p>{analysis.exclusion_criteria}</p></div>
              </div>
            </section>

            <section className={`card span12 ${styles.notesPanel}`}>
              <div className="resultSummary">
                <h3 className="sectionTitle">Research synthesis notes</h3>
                <span className="pill">User edits become user-note claims</span>
              </div>
              {!readOnly ? <form action={editGapCanvas.bind(null, analysis.id)} className="editorStack">
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
              </form> : <div className="grid readOnlySynthesisGrid">{editableSections.map(([field, label]) => <div className="readOnlySynthesisField span6" key={field}><span className="metricLabel">{label}</span><p>{analysis[field] || "No note recorded."}</p></div>)}</div>}
            </section>
          </div>
        </>
      )}
    </>
  );
}
