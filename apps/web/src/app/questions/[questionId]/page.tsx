import Link from "next/link";
import { notFound } from "next/navigation";

import { MutationFeedback } from "@/components/MutationFeedback";
import {
  getResearchQuestion,
  getResearchQuestionRecommendations,
  listComparisonSets,
  listSavedSearches,
} from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { addQuestionNoteAction, createQuestionGapAction, linkEntityAction, updateQuestionAction } from "./actions";

export default async function QuestionDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ questionId: string }>;
  searchParams: Promise<{ feedback?: string }>;
}) {
  const { questionId } = await params;
  const query = await searchParams;
  const [q, recommendations, savedSearches, comparisonSets] = await Promise.all([
    getResearchQuestion(questionId),
    getResearchQuestionRecommendations(questionId),
    listSavedSearches(),
    listComparisonSets(),
  ]);
  if (!q) notFound();
  const readOnly = isWorkspaceReadOnly();

  return (
    <>
      {!readOnly ? (
        <MutationFeedback
          feedback={query.feedback}
          messages={{
            created: { message: "Research question created." },
            updated: { message: "Research question state saved." },
            linked: { message: "Workspace item linked to this research question." },
            "note-added": { message: "Question note added." },
            "invalid-link": { message: "Choose a workspace item before linking it to this question.", tone: "error" },
            "invalid-note": { message: "Enter a question note before saving it.", tone: "error" },
            "gap-error": { message: "The Gap Canvas could not be created from this question.", tone: "error" },
            error: { message: "The research question change could not be saved.", tone: "error" },
          }}
        />
      ) : null}
      <header className="questionThreadHeader">
        <div>
          <p className="eyebrow">Living Research Journal · Question Thread</p>
          <h2 className="paperDetailTitle">{q.title}</h2>
          <p className="pageIntro">{q.question_text}</p>
          <div className="headerActionRow">
            <Link className="secondaryButton" href={`/chat?scope=research_question&ids=${q.id}`}>Ask this question with evidence →</Link>
            <Link className="secondaryButton" href="/library">Select supporting papers →</Link>
          </div>
        </div>
        <Link className="button buttonSecondary" href="/questions">← Questions</Link>
      </header>

      <article className="questionThreadDocument">
        <aside className="questionThreadRail" aria-label="Research question workflow thread">
          <div><span>01</span><strong>Frame</strong><small>question + uncertainty</small></div>
          <div><span>02</span><strong>Collect</strong><small>{q.papers.length} linked papers</small></div>
          <div><span>03</span><strong>Compare</strong><small>{q.comparison_sets.length} evidence sets</small></div>
          <div><span>04</span><strong>Challenge</strong><small>{q.gap_analyses.length} gap analyses</small></div>
          <div><span>05</span><strong>Synthesize</strong><small>with provenance</small></div>
        </aside>

        <div className="questionThreadBody">
        <section className="questionThreadEntry questionThreadEntryPrimary">
          <span className="questionThreadEntryIndex">01 · Frame</span>
          <div className="sectionHeadingRow"><h3 className="sectionTitle">Question state</h3>{readOnly ? <span className="readOnlyInline">Read-only demo</span> : null}</div>
          {readOnly ? (
            <dl className="questionStateSummary">
              <div><dt>Why this matters</dt><dd>{q.importance_notes || "Not documented yet."}</dd></div>
              <div><dt>Motivation</dt><dd>{q.motivation || "Not documented yet."}</dd></div>
              <div><dt>Scope</dt><dd>{q.scope_notes || "Not documented yet."}</dd></div>
              <div><dt>Uncertainty</dt><dd>{q.uncertainty_notes || "Not documented yet."}</dd></div>
              <div><dt>Evidence state</dt><dd><span className={`statusBadge status-${q.evidence_status}`}>{q.evidence_status}</span></dd></div>
            </dl>
          ) : (
            <form action={updateQuestionAction.bind(null, q.id)} className="formStack">
              <label className="fieldLabel">Why this matters<textarea className="textarea" name="importance_notes" defaultValue={q.importance_notes ?? ""} /></label>
              <label className="fieldLabel">Motivation<textarea className="textarea" name="motivation" defaultValue={q.motivation ?? ""} /></label>
              <label className="fieldLabel">Scope notes<textarea className="textarea" name="scope_notes" defaultValue={q.scope_notes ?? ""} /></label>
              <label className="fieldLabel">What is still uncertain<textarea className="textarea" name="uncertainty_notes" defaultValue={q.uncertainty_notes ?? ""} /></label>
              <div className="inlineForm">
                <label className="compactFieldLabel"><span>Evidence state</span><select className="select" name="evidence_status" defaultValue={q.evidence_status}><option value="insufficient_evidence">Insufficient evidence</option><option value="mixed">Mixed</option><option value="supported">Supported</option></select></label>
                <label className="compactFieldLabel"><span>Workflow status</span><input className="input" name="status" defaultValue={q.status} /></label>
              </div>
              <button className="button" type="submit">Save question state</button>
            </form>
          )}
        </section>

        <section className="questionThreadEntry questionThreadChallenge">
          <span className="questionThreadEntryIndex">04 · Challenge</span>
          <h3 className="sectionTitle">Gap hypothesis workflow</h3>
          <p className="muted">Gap Canvas produces a candidate hypothesis from current evidence and keeps falsification work visible. It never certifies a literature gap.</p>
          {!readOnly ? <form action={createQuestionGapAction.bind(null, q.id, q.question_text)}><button className="button" type="submit">Open Gap Canvas from this question</button></form> : null}
          <div className="noteStack">
            {q.gap_analyses.map((gap) => <Link className="questionCard" href={`/gap-canvas?id=${gap.id}`} key={gap.id}><strong>{gap.status}</strong><span>{gap.gap_candidates ?? "No candidate text"}</span></Link>)}
          </div>
        </section>

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">02 · Collect</span>
          <div className="sectionHeadingRow"><h3 className="sectionTitle">Linked papers</h3><span className="pill">{q.papers.length}</span></div>
          {q.papers.map((paper) => <Link className="questionCard" href={`/library/${paper.id}`} key={paper.id}><strong>{paper.title}</strong><small>{paper.publication_year ?? "—"} · {paper.relation}</small></Link>)}
          {!readOnly ? <Link className="secondaryButton linkedPaperCta" href="/library">Select papers in Library →</Link> : null}
        </section>

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">02A · Read next</span>
          <h3 className="sectionTitle">What to read next</h3>
          <p className="muted">Recommendations combine question relevance, corpus-local citation paths, and unread novelty. Citation count is not treated as a quality proxy.</p>
          <div className="noteStack">
            {recommendations.length ? recommendations.map((paper) => (
              <article className="questionCard" key={paper.id}>
                <Link className="textLink" href={`/library/${paper.id}`}><strong>{paper.title}</strong></Link>
                <small>{paper.publication_year ?? "—"} · score {paper.score.toFixed(3)}</small>
                <div className="rankRow"><span className="pill">Query #{paper.query_rank ?? "—"}</span><span className="pill">Backward seeds {paper.backward_seed_count}</span><span className="pill">Forward seeds {paper.forward_seed_count}</span><span className="pill">Reading {paper.reading_status ?? "unqueued"}</span></div>
                <details><summary>Why this recommendation?</summary><div className="rankRow">{Object.entries(paper.score_components).map(([name, value]) => <span className="pill" key={name}>{name}: {value.toFixed(3)}</span>)}</div><p className="muted">{paper.reasons.join(" · ")}</p></details>
                {!readOnly ? <form action={linkEntityAction.bind(null, q.id, "papers")}><input type="hidden" name="entity_id" value={paper.id} /><button className="button buttonSecondary" type="submit">Add to question</button></form> : null}
              </article>
            )) : <span className="muted">No unlinked recommendation is available yet.</span>}
          </div>
        </section>

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">03 · Compare</span>
          <h3 className="sectionTitle">Saved searches & comparisons</h3>
          <div className="noteStack">
            {q.saved_searches.map((item) => <div className="noteCard" key={item.id}><strong>{item.name}</strong><p>{item.query_text}</p></div>)}
            {q.comparison_sets.map((item) => <Link className="questionCard" href={`/compare?id=${item.id}`} key={item.id}>{item.name}</Link>)}
          </div>
          {!readOnly ? (
            <div className="linkEntityForms">
              <form action={linkEntityAction.bind(null, q.id, "saved-searches")} className="inlineForm">
                <label className="srOnly" htmlFor="saved-search-link">Saved search</label>
                <select className="select" id="saved-search-link" name="entity_id" required defaultValue=""><option value="" disabled>Choose saved search…</option>{savedSearches.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select>
                <button className="button" type="submit">Link search</button>
              </form>
              <form action={linkEntityAction.bind(null, q.id, "comparison-sets")} className="inlineForm">
                <label className="srOnly" htmlFor="comparison-link">Comparison set</label>
                <select className="select" id="comparison-link" name="entity_id" required defaultValue=""><option value="" disabled>Choose comparison…</option>{comparisonSets.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select>
                <button className="button" type="submit">Link comparison</button>
              </form>
            </div>
          ) : null}
        </section>

        <section className="questionThreadEntry questionThreadNotes">
          <span className="questionThreadEntryIndex">05 · Journal</span>
          <h3 className="sectionTitle">Question notes</h3>
          {!readOnly ? <form action={addQuestionNoteAction.bind(null, q.id)} className="inlineForm"><input className="input" name="note" placeholder="Working note, concern, next search…" /><button className="button" type="submit">Add note</button></form> : null}
          <div className="noteStack">{q.notes.length ? q.notes.map((note) => <div className="noteCard" key={note.id}>{note.note_markdown}</div>) : <span className="muted">No notes yet.</span>}</div>
        </section>
        </div>
      </article>
    </>
  );
}
