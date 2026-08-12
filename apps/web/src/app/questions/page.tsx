import Link from "next/link";

import { listResearchQuestions } from "@/lib/api";

import { createQuestionAction } from "./actions";

const startingPoints = [
  ["AI capability → innovation performance", "AI capability innovation performance dynamic capabilities"],
  ["Human–AI decision rights", "human AI collaboration decision making organizational design"],
  ["Agentic workflows in firms", "AI agents enterprise workflows human oversight"],
] as const;

export default async function QuestionsPage() {
  const questions = await listResearchQuestions();

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Research Questions</p>
          <h2 className="pageTitle">The question is the unit of work.</h2>
          <p className="pageIntro">
            Frame the question first, then attach searches, papers, comparisons, candidate gaps, and uncertainty to it.
          </p>
        </div>
      </header>

      <section className="questionWorkbench">
        <article className="questionComposer">
          <div className="questionComposerHeader">
            <span className="cardKicker">New workspace</span>
            <h3>What do you actually want to explain?</h3>
            <p>Keep it specific enough to test, but broad enough to search before locking the design.</p>
          </div>
          <form action={createQuestionAction} className="formStack questionForm">
            <label className="fieldLabel">Working title<input className="input" name="title" placeholder="e.g. AI capability and innovation performance" /></label>
            <label className="fieldLabel">Research question<textarea className="textarea questionTextarea" name="question_text" required placeholder="How does AI capability affect innovation performance, and under which organizational conditions?" /></label>
            <div className="questionFormGrid">
              <label className="fieldLabel">Why it matters<textarea className="textarea compactTextarea" name="motivation" placeholder="Managerial or theoretical motivation" /></label>
              <label className="fieldLabel">What is uncertain<textarea className="textarea compactTextarea" name="uncertainty_notes" placeholder="Boundary conditions, causal direction, missing context…" /></label>
            </div>
            <input type="hidden" name="importance_notes" value="" />
            <button className="button questionCreateButton" type="submit">Create research workspace →</button>
          </form>
        </article>

        <aside className="questionSidePanel">
          <div>
            <span className="cardKicker">Your pipeline</span>
            <div className="questionCount">{questions.length}</div>
            <p className="metricHelp">research questions currently in the workspace</p>
          </div>
          <div className="questionSideDivider" />
          <div>
            <h4>Not ready to frame it yet?</h4>
            <p className="metricHelp">Start from a literature cluster and come back with a sharper question.</p>
            <div className="starterStack">
              {startingPoints.map(([label, query]) => (
                <Link href={`/library?q=${encodeURIComponent(query)}&mode=hybrid`} className="starterLink" key={label}>
                  <span>{label}</span><b>↗</b>
                </Link>
              ))}
            </div>
          </div>
        </aside>
      </section>

      <section className="questionListSection">
        <div className="sectionHeadingRow">
          <div><span className="cardKicker">Research pipeline</span><h3 className="sectionTitle">Active questions</h3></div>
          <Link href="/library" className="textLink">Search before framing →</Link>
        </div>
        {questions.length ? (
          <div className="questionGrid">
            {questions.map((question, index) => (
              <Link className="questionWorkspaceCard" href={`/questions/${question.id}`} key={question.id}>
                <span className="questionNumber">Q{String(index + 1).padStart(2, "0")}</span>
                <strong>{question.title}</strong>
                <p>{question.question_text}</p>
                <div className="questionStats">
                  <span>{question.evidence_status}</span>
                  <span>{question.papers.length} papers</span>
                  <span>{question.gap_analyses.length} gap canvases</span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="emptyState questionEmptyState">
            <strong>No research question yet.</strong>
            <span>Create one above, or search a cluster first and come back when the uncertainty becomes clearer.</span>
          </div>
        )}
      </section>
    </>
  );
}
