import Link from "next/link";
import { notFound } from "next/navigation";

import { MutationFeedback } from "@/components/MutationFeedback";
import { LocalizedText } from "@/components/LocalizedText";
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
          <p className="eyebrow"><LocalizedText en="Living Research Journal · Question Thread" ko="살아있는 연구 저널 · 질문 스레드" /></p>
          <h2 className="paperDetailTitle">{q.title}</h2>
          <p className="pageIntro">{q.question_text}</p>
          <div className="headerActionRow">
            <Link className="secondaryButton" href={`/chat?scope=research_question&ids=${q.id}`}><LocalizedText en="Ask this question with evidence →" ko="이 질문을 근거와 함께 묻기 →" /></Link>
            <Link className="secondaryButton" href="/library"><LocalizedText en="Select supporting papers →" ko="근거 논문 선택 →" /></Link>
          </div>
        </div>
        <Link className="button buttonSecondary" href="/questions">← Questions</Link>
      </header>

      <article className="questionThreadDocument">
        <aside className="questionThreadRail" aria-label="Research question workflow thread">
          <div><span>01</span><strong><LocalizedText en="Frame" ko="정의" /></strong><small><LocalizedText en="question + uncertainty" ko="질문 + 불확실성" /></small></div>
          <div><span>02</span><strong><LocalizedText en="Collect" ko="수집" /></strong><small><LocalizedText en={`${q.papers.length} linked papers`} ko={`연결된 논문 ${q.papers.length}편`} /></small></div>
          <div><span>03</span><strong><LocalizedText en="Compare" ko="비교" /></strong><small><LocalizedText en={`${q.comparison_sets.length} evidence sets`} ko={`근거 세트 ${q.comparison_sets.length}개`} /></small></div>
          <div><span>04</span><strong><LocalizedText en="Challenge" ko="반증" /></strong><small><LocalizedText en={`${q.gap_analyses.length} gap analyses`} ko={`공백 분석 ${q.gap_analyses.length}개`} /></small></div>
          <div><span>05</span><strong><LocalizedText en="Synthesize" ko="종합" /></strong><small><LocalizedText en="with provenance" ko="출처 이력 포함" /></small></div>
        </aside>

        <div className="questionThreadBody">
        <section className="questionThreadEntry questionThreadEntryPrimary">
          <span className="questionThreadEntryIndex">01 · Frame</span>
          <div className="sectionHeadingRow"><h3 className="sectionTitle"><LocalizedText en="Question state" ko="질문 상태" /></h3>{readOnly ? <span className="readOnlyInline"><LocalizedText en="Read-only demo" ko="읽기 전용 데모" /></span> : null}</div>
          {readOnly ? (
            <dl className="questionStateSummary">
              <div><dt><LocalizedText en="Why this matters" ko="왜 중요한가" /></dt><dd>{q.importance_notes || <LocalizedText en="Not documented yet." ko="아직 기록되지 않았습니다." />}</dd></div>
              <div><dt><LocalizedText en="Motivation" ko="연구 동기" /></dt><dd>{q.motivation || <LocalizedText en="Not documented yet." ko="아직 기록되지 않았습니다." />}</dd></div>
              <div><dt><LocalizedText en="Scope" ko="범위" /></dt><dd>{q.scope_notes || <LocalizedText en="Not documented yet." ko="아직 기록되지 않았습니다." />}</dd></div>
              <div><dt><LocalizedText en="Uncertainty" ko="불확실성" /></dt><dd>{q.uncertainty_notes || <LocalizedText en="Not documented yet." ko="아직 기록되지 않았습니다." />}</dd></div>
              <div><dt><LocalizedText en="Evidence state" ko="근거 상태" /></dt><dd><span className={`statusBadge status-${q.evidence_status}`}>{q.evidence_status}</span></dd></div>
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
              <button className="button" type="submit"><LocalizedText en="Save question state" ko="질문 상태 저장" /></button>
            </form>
          )}
        </section>

        <section className="questionThreadEntry questionThreadChallenge">
          <span className="questionThreadEntryIndex">04 · Challenge</span>
          <h3 className="sectionTitle"><LocalizedText en="Gap hypothesis workflow" ko="연구 공백 가설 흐름" /></h3>
          <p className="muted"><LocalizedText en="Gap Canvas produces a candidate hypothesis from current evidence and keeps falsification work visible. It never certifies a literature gap." ko="연구 공백 캔버스는 현재 근거에서 후보 가설을 만들고 반증 작업을 계속 표시합니다. 문헌 공백을 확정하지 않습니다." /></p>
          {!readOnly ? <form action={createQuestionGapAction.bind(null, q.id, q.question_text)}><button className="button" type="submit"><LocalizedText en="Open Gap Canvas from this question" ko="이 질문으로 연구 공백 캔버스 열기" /></button></form> : null}
          <div className="noteStack">
            {q.gap_analyses.map((gap) => <Link className="questionCard" href={`/gap-canvas?id=${gap.id}`} key={gap.id}><strong>{gap.status}</strong><span>{gap.gap_candidates ?? "No candidate text"}</span></Link>)}
          </div>
        </section>

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">02 · Collect</span>
          <div className="sectionHeadingRow"><h3 className="sectionTitle"><LocalizedText en="Linked papers" ko="연결된 논문" /></h3><span className="pill">{q.papers.length}</span></div>
          {q.papers.map((paper) => <Link className="questionCard" href={`/library/${paper.id}`} key={paper.id}><strong>{paper.title}</strong><small>{paper.publication_year ?? "—"} · {paper.relation}</small></Link>)}
          {!readOnly ? <Link className="secondaryButton linkedPaperCta" href="/library"><LocalizedText en="Select papers in Library →" ko="라이브러리에서 논문 선택 →" /></Link> : null}
        </section>

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">02A · Read next</span>
          <h3 className="sectionTitle"><LocalizedText en="What to read next" ko="다음에 읽을 논문" /></h3>
          <p className="muted"><LocalizedText en="Recommendations combine question relevance, corpus-local citation paths, and unread novelty. Citation count is not treated as a quality proxy." ko="질문 관련성, 로컬 코퍼스 인용 경로, 아직 읽지 않은 신규성을 결합해 추천합니다. 인용 수를 품질의 대리 지표로 사용하지 않습니다." /></p>
          <div className="noteStack">
            {recommendations.length ? recommendations.map((paper) => (
              <article className="questionCard" key={paper.id}>
                <Link className="textLink" href={`/library/${paper.id}`}><strong>{paper.title}</strong></Link>
                <small>{paper.publication_year ?? "—"} · score {paper.score.toFixed(3)}</small>
                <div className="rankRow"><span className="pill">Query #{paper.query_rank ?? "—"}</span><span className="pill">Backward seeds {paper.backward_seed_count}</span><span className="pill">Forward seeds {paper.forward_seed_count}</span><span className="pill">Reading {paper.reading_status ?? "unqueued"}</span></div>
                <details><summary><LocalizedText en="Why this recommendation?" ko="왜 이 논문을 추천하나요?" /></summary><div className="rankRow">{Object.entries(paper.score_components).map(([name, value]) => <span className="pill" key={name}>{name}: {value.toFixed(3)}</span>)}</div><p className="muted">{paper.reasons.join(" · ")}</p></details>
                {!readOnly ? <form action={linkEntityAction.bind(null, q.id, "papers")}><input type="hidden" name="entity_id" value={paper.id} /><button className="button buttonSecondary" type="submit"><LocalizedText en="Add to question" ko="질문에 추가" /></button></form> : null}
              </article>
            )) : <span className="muted">No unlinked recommendation is available yet.</span>}
          </div>
        </section>

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">03 · Compare</span>
          <h3 className="sectionTitle"><LocalizedText en="Saved searches & comparisons" ko="저장된 검색과 비교" /></h3>
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
          <h3 className="sectionTitle"><LocalizedText en="Question notes" ko="질문 노트" /></h3>
          {!readOnly ? <form action={addQuestionNoteAction.bind(null, q.id)} className="inlineForm"><input className="input" name="note" placeholder="Working note, concern, next search… / 작업 노트, 우려, 다음 검색" /><button className="button" type="submit"><LocalizedText en="Add note" ko="노트 추가" /></button></form> : null}
          <div className="noteStack">{q.notes.length ? q.notes.map((note) => <div className="noteCard" key={note.id}>{note.note_markdown}</div>) : <span className="muted"><LocalizedText en="No notes yet." ko="아직 노트가 없습니다." /></span>}</div>
        </section>
        </div>
      </article>
    </>
  );
}
