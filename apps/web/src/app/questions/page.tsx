import Link from "next/link";

import { listResearchQuestions } from "@/lib/api";

import { createQuestionAction } from "./actions";

export default async function QuestionsPage() {
  const questions = await listResearchQuestions();
  return <>
    <header className="pageHeader"><div><p className="eyebrow">Research Questions</p><h2 className="pageTitle">Make the question the center of the research workflow.</h2><p className="pageIntro">Connect searches, papers, comparisons, gap hypotheses, and notes without turning low corpus coverage into a claimed field gap.</p></div></header>
    <section className="grid">
      <article className="card span5"><h3 className="sectionTitle">New research question</h3><form action={createQuestionAction} className="formStack">
        <input className="input" name="title" placeholder="Short working title" />
        <textarea className="textarea" name="question_text" required placeholder="How does ... affect ... under ... conditions?" />
        <textarea className="textarea" name="motivation" placeholder="Motivation / why this matters" />
        <textarea className="textarea" name="importance_notes" placeholder="Why is this important for AI × MOT?" />
        <textarea className="textarea" name="uncertainty_notes" placeholder="What is still uncertain?" />
        <button className="button" type="submit">Create workspace</button>
      </form></article>
      <article className="card span7"><h3 className="sectionTitle">Active questions</h3><div className="resultStack">
        {questions.length ? questions.map((q) => <Link className="questionCard" href={`/questions/${q.id}`} key={q.id}><strong>{q.title}</strong><span>{q.question_text}</span><small>{q.evidence_status} · {q.papers.length} linked papers · {q.gap_analyses.length} gap analyses</small></Link>) : <div className="emptyState">No research questions yet.</div>}
      </div></article>
    </section>
  </>;
}
