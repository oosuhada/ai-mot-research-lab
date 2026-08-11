import Link from "next/link";
import { notFound } from "next/navigation";

import { getResearchQuestion } from "@/lib/api";

import { addQuestionNoteAction, createQuestionGapAction, linkEntityAction, updateQuestionAction } from "./actions";

export default async function QuestionDetailPage({ params }: { params: Promise<{ questionId: string }> }) {
  const { questionId } = await params;
  const q = await getResearchQuestion(questionId);
  if (!q) notFound();
  return <>
    <header className="pageHeader"><div><p className="eyebrow">Research Question Workspace</p><h2 className="paperDetailTitle">{q.title}</h2><p className="pageIntro">{q.question_text}</p></div><Link className="button buttonSecondary" href="/questions">← Questions</Link></header>
    <section className="grid">
      <article className="card span7"><h3 className="sectionTitle">Question state</h3><form action={updateQuestionAction.bind(null, q.id)} className="formStack">
        <label className="fieldLabel">Why this matters<textarea className="textarea" name="importance_notes" defaultValue={q.importance_notes ?? ""} /></label>
        <label className="fieldLabel">Motivation<textarea className="textarea" name="motivation" defaultValue={q.motivation ?? ""} /></label>
        <label className="fieldLabel">Scope notes<textarea className="textarea" name="scope_notes" defaultValue={q.scope_notes ?? ""} /></label>
        <label className="fieldLabel">What is still uncertain<textarea className="textarea" name="uncertainty_notes" defaultValue={q.uncertainty_notes ?? ""} /></label>
        <div className="inlineForm"><select className="select" name="evidence_status" defaultValue={q.evidence_status}><option value="insufficient_evidence">Insufficient evidence</option><option value="mixed">Mixed</option><option value="supported">Supported</option></select><input className="input" name="status" defaultValue={q.status} /></div>
        <button className="button" type="submit">Save question state</button>
      </form></article>
      <aside className="card span5"><h3 className="sectionTitle">Gap hypothesis workflow</h3><p className="muted">Creates a candidate hypothesis from the current local corpus. It never certifies a literature gap.</p><form action={createQuestionGapAction.bind(null, q.id, q.question_text)}><button className="button" type="submit">Open Gap Canvas from this question</button></form>{q.gap_analyses.map((gap) => <Link className="questionCard" href={`/gap-canvas?id=${gap.id}`} key={gap.id}><strong>{gap.status}</strong><span>{gap.gap_candidates ?? "No candidate text"}</span></Link>)}</aside>
      <article className="card span6"><h3 className="sectionTitle">Linked papers</h3>{q.papers.map((paper) => <Link className="questionCard" href={`/library/${paper.id}`} key={paper.id}><strong>{paper.title}</strong><small>{paper.publication_year ?? "—"} · {paper.relation}</small></Link>)}<form action={linkEntityAction.bind(null, q.id, "papers")} className="inlineForm"><input className="input" name="entity_id" placeholder="Paper UUID" /><button className="button" type="submit">Link</button></form></article>
      <article className="card span6"><h3 className="sectionTitle">Saved searches & comparisons</h3>{q.saved_searches.map((item) => <div className="noteCard" key={item.id}><strong>{item.name}</strong><p>{item.query_text}</p></div>)}{q.comparison_sets.map((item) => <Link className="questionCard" href={`/compare?id=${item.id}`} key={item.id}>{item.name}</Link>)}<form action={linkEntityAction.bind(null, q.id, "saved-searches")} className="inlineForm"><input className="input" name="entity_id" placeholder="Saved search UUID" /><button className="button" type="submit">Link search</button></form><form action={linkEntityAction.bind(null, q.id, "comparison-sets")} className="inlineForm"><input className="input" name="entity_id" placeholder="Comparison UUID" /><button className="button" type="submit">Link compare</button></form></article>
      <article className="card span12"><h3 className="sectionTitle">Question notes</h3><form action={addQuestionNoteAction.bind(null, q.id)} className="inlineForm"><input className="input" name="note" placeholder="Working note, concern, next search..." /><button className="button" type="submit">Add note</button></form><div className="noteStack">{q.notes.map((note) => <div className="noteCard" key={note.id}>{note.note_markdown}</div>)}</div></article>
    </section>
  </>;
}
