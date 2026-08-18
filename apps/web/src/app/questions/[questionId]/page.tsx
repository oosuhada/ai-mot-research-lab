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

import {
  addQuestionNoteAction,
  createDirectionAction,
  createDirectionFromGapAction,
  createQuestionGapAction,
  linkEntityAction,
  saveResearchDesignAction,
  updateDirectionAction,
  updateLinkedPaperAction,
  updateQuestionAction,
} from "./actions";

const directionDimensions = [
  ["novelty", "Novelty", "신규성"],
  ["theory_fit", "Theory fit", "이론 적합성"],
  ["data_feasibility", "Data feasibility", "데이터 확보 가능성"],
  ["method_feasibility", "Method feasibility", "방법 실현가능성"],
  ["scope_fit", "Scope fit", "연구 범위 적합성"],
  ["personal_interest", "Personal interest", "개인 관심도"],
] as const;

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
            "paper-workflow-saved": { message: "Literature tier and relationship saved." },
            "paper-workflow-error": { message: "The paper workflow state could not be saved.", tone: "error" },
            "direction-created": { message: "Candidate research direction added for testing." },
            "direction-saved": { message: "Research direction evaluation saved." },
            "direction-error": { message: "The research direction could not be saved.", tone: "error" },
            "design-saved": { message: "Research design saved." },
            "design-error": { message: "The research design could not be saved.", tone: "error" },
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
            <Link className="secondaryButton" href={`/questions/${q.id}/proposal`}><LocalizedText en="Open proposal builder →" ko="연구계획서 빌더 →" /></Link>
          </div>
        </div>
        <Link className="button buttonSecondary" href="/questions">← Questions</Link>
      </header>

      <article className="questionThreadDocument">
        <aside className="questionThreadRail" aria-label="Research question workflow thread">
          <div><span>01</span><strong><LocalizedText en="Frame" ko="정의" /></strong><small><LocalizedText en="question + uncertainty" ko="질문 + 불확실성" /></small></div>
          <div><span>02</span><strong><LocalizedText en="Collect" ko="수집" /></strong><small><LocalizedText en={`${q.papers.length} linked papers`} ko={`연결된 논문 ${q.papers.length}편`} /></small></div>
          <div><span>03</span><strong><LocalizedText en="Review" ko="읽기" /></strong><small><LocalizedText en={`${q.workflow?.reviewed_cards ?? 0} reviewed cards`} ko={`검토 완료 카드 ${q.workflow?.reviewed_cards ?? 0}개`} /></small></div>
          <div><span>04</span><strong><LocalizedText en="Synthesize" ko="종합" /></strong><small><LocalizedText en={`${q.comparison_sets.length} evidence sets`} ko={`근거 세트 ${q.comparison_sets.length}개`} /></small></div>
          <div><span>05</span><strong><LocalizedText en="Challenge" ko="반증" /></strong><small><LocalizedText en={`${q.gap_analyses.length} gap analyses`} ko={`공백 분석 ${q.gap_analyses.length}개`} /></small></div>
          <div><span>06</span><strong><LocalizedText en="Choose" ko="주제선정" /></strong><small><LocalizedText en={`${q.directions.length} directions`} ko={`연구방향 ${q.directions.length}개`} /></small></div>
          <div><span>07</span><strong><LocalizedText en="Design" ko="연구설계" /></strong><small><LocalizedText en={`${q.design?.readiness_pct ?? 0}% design`} ko={`설계 ${q.design?.readiness_pct ?? 0}%`} /></small></div>
        </aside>

        <div className="questionThreadBody">
        <section className="questionThreadEntry researchWorkflowOverview">
          <span className="questionThreadEntryIndex"><LocalizedText en="Research progress" ko="연구 진행" /></span>
          <div className="researchWorkflowHero">
            <div>
              <p className="eyebrow"><LocalizedText en="From literature to proposal" ko="문헌에서 연구계획서까지" /></p>
              <h3 className="sectionTitle"><LocalizedText en="What should move next?" ko="다음에 무엇을 진행해야 하나요?" /></h3>
              <p className="muted"><LocalizedText en="Corpus size stays in the dashboard; this score tracks whether this specific research thread is becoming decision-ready." ko="코퍼스 규모는 대시보드에서 계속 관리하고, 여기서는 이 연구 스레드가 실제 의사결정을 내릴 수 있는 상태로 발전하고 있는지를 추적합니다." /></p>
            </div>
            <div className="proposalReadinessGauge" aria-label={`Proposal readiness ${q.workflow?.proposal_readiness_pct ?? 0}%`}>
              <strong>{q.workflow?.proposal_readiness_pct ?? 0}%</strong>
              <span><LocalizedText en="proposal readiness" ko="연구계획서 준비도" /></span>
            </div>
          </div>
          <div className="researchWorkflowMetrics">
            <div><strong>{q.workflow?.linked_papers ?? q.papers.length}</strong><span><LocalizedText en="linked" ko="연결 논문" /></span></div>
            <div><strong>{q.workflow?.reading_papers ?? 0}</strong><span><LocalizedText en="reading set" ko="읽기 세트" /></span></div>
            <div><strong>{q.workflow?.core_papers ?? 0}</strong><span><LocalizedText en="core evidence" ko="핵심 근거" /></span></div>
            <div><strong>{q.workflow?.reviewed_cards ?? 0}</strong><span><LocalizedText en="reviewed cards" ko="검토 카드" /></span></div>
            <div><strong>{q.workflow?.research_directions ?? 0}</strong><span><LocalizedText en="directions" ko="연구방향" /></span></div>
            <div><strong>{q.design?.readiness_pct ?? 0}%</strong><span><LocalizedText en="design" ko="연구설계" /></span></div>
          </div>
          <div className="nextActionStack">
            {(q.workflow?.next_actions ?? []).map((item, index) => <div className="nextActionRow" key={item}><span>{String(index + 1).padStart(2, "0")}</span><p>{item}</p></div>)}
          </div>
        </section>

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

        <section className="questionThreadEntry">
          <span className="questionThreadEntryIndex">02 · Collect</span>
          <div className="sectionHeadingRow"><div><h3 className="sectionTitle"><LocalizedText en="Literature funnel" ko="문헌 퍼널" /></h3><p className="muted"><LocalizedText en="Move papers deliberately from candidate → reading → core/foundation. The 100K corpus is the universe; this is the literature that actually shapes your study." ko="10만 편 코퍼스는 전체 탐색 공간이고, 여기서는 실제 연구를 형성하는 논문만 후보 → 읽기 → 핵심/기초 문헌으로 의도적으로 좁힙니다." /></p></div><span className="pill">{q.papers.length}</span></div>
          <div className="literatureTierSummary">
            <span><strong>{q.workflow?.candidate_papers ?? 0}</strong> candidate</span>
            <span><strong>{q.workflow?.reading_papers ?? 0}</strong> reading</span>
            <span><strong>{q.workflow?.core_papers ?? 0}</strong> core</span>
            <span><strong>{q.workflow?.foundation_papers ?? 0}</strong> foundation</span>
          </div>
          <div className="literatureWorkspaceList">
            {q.papers.map((paper) => (
              <article className={`literatureWorkspaceCard literatureTier-${paper.literature_tier}`} key={paper.id}>
                <div className="literatureWorkspaceHeader">
                  <div>
                    <Link className="textLink" href={`/library/${paper.id}`}><strong>{paper.title}</strong></Link>
                    <small>{paper.publication_year ?? "—"} · {paper.relation}</small>
                  </div>
                  <div className="rankRow"><span className="pill">{paper.literature_tier}</span><span className={`statusBadge status-${paper.research_card_status === "reviewed" ? "supported" : "insufficient_evidence"}`}>card · {paper.research_card_status ?? "not started"}</span></div>
                </div>
                {paper.relationship_note ? <p className="muted">{paper.relationship_note}</p> : null}
                {!readOnly ? (
                  <form action={updateLinkedPaperAction.bind(null, q.id, paper.id)} className="literatureWorkflowForm">
                    <label className="compactFieldLabel"><span><LocalizedText en="Literature tier" ko="문헌 단계" /></span><select className="select" name="literature_tier" defaultValue={paper.literature_tier}><option value="candidate">Candidate</option><option value="reading">Reading set</option><option value="core">Core evidence</option><option value="foundation">Theory foundation</option><option value="excluded">Exclude from this question</option></select></label>
                    <label className="compactFieldLabel"><span><LocalizedText en="Role in this question" ko="이 질문에서 역할" /></span><select className="select" name="relation" defaultValue={paper.relation}><option value="relevant">Relevant</option><option value="supports">Supports current explanation</option><option value="contradicts">Potential contradiction</option><option value="context">Context / boundary</option><option value="method">Method precedent</option><option value="foundation">Theory foundation</option></select></label>
                    <label className="fieldLabel literatureRelationshipNote"><LocalizedText en="Why it matters to this RQ" ko="이 연구질문에 왜 중요한가" /><input className="input" name="relationship_note" defaultValue={paper.relationship_note ?? ""} placeholder="Mechanism, boundary condition, method precedent, contradiction…" /></label>
                    <button className="button buttonSecondary" type="submit"><LocalizedText en="Save paper role" ko="논문 역할 저장" /></button>
                  </form>
                ) : null}
              </article>
            ))}
          </div>
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

        <section className="questionThreadEntry researchSynthesisEntry">
          <span className="questionThreadEntryIndex">04 · Synthesize</span>
          <div className="sectionHeadingRow">
            <div>
              <h3 className="sectionTitle"><LocalizedText en="Reviewed evidence synthesis" ko="검토된 근거 종합" /></h3>
              <p className="muted"><LocalizedText en="Only Research Cards you explicitly marked reviewed enter these signals. This is a map of what you have actually checked, not an automatic literature consensus." ko="사용자가 명시적으로 검토 완료한 리서치 카드만 아래 신호에 포함됩니다. 자동 문헌 합의가 아니라 실제로 확인한 내용의 지도입니다." /></p>
            </div>
            <span className="pill">{q.synthesis?.reviewed_card_count ?? 0} / {q.synthesis?.card_count ?? 0} reviewed</span>
          </div>
          <div className="synthesisSignalGrid">
            <article>
              <h4><LocalizedText en="Theory signals" ko="이론 신호" /></h4>
              <div className="tagCloud">{q.synthesis?.theory_signals.length ? q.synthesis.theory_signals.map((item) => <span className="pill" key={item.label}>{item.label} · {item.count}</span>) : <span className="muted"><LocalizedText en="Review cards to build a theory map." ko="리서치 카드를 검토하면 이론 지도가 만들어집니다." /></span>}</div>
            </article>
            <article>
              <h4><LocalizedText en="Method signals" ko="방법론 신호" /></h4>
              <div className="tagCloud">{q.synthesis?.methodology_signals.length ? q.synthesis.methodology_signals.map((item) => <span className="pill" key={item.label}>{item.label} · {item.count}</span>) : <span className="muted"><LocalizedText en="No reviewed method signal yet." ko="아직 검토된 방법론 신호가 없습니다." /></span>}</div>
            </article>
            <article>
              <h4><LocalizedText en="Context signals" ko="연구 맥락 신호" /></h4>
              <div className="tagCloud">{q.synthesis?.context_signals.length ? q.synthesis.context_signals.map((item) => <span className="pill" key={item.label}>{item.label} · {item.count}</span>) : <span className="muted"><LocalizedText en="No reviewed context signal yet." ko="아직 검토된 연구 맥락 신호가 없습니다." /></span>}</div>
            </article>
          </div>
          <div className="synthesisLeadColumns">
            <article>
              <h4><LocalizedText en="Limitation leads to inspect" ko="확인할 한계 단서" /></h4>
              <div className="noteStack">{q.synthesis?.limitation_leads.length ? q.synthesis.limitation_leads.map((item) => <Link className="noteCard" href={`/library/${item.paper_id}`} key={`${item.paper_id}-${item.text}`}><strong>{item.paper_title}</strong><p>{item.text}</p></Link>) : <span className="muted"><LocalizedText en="No reviewed limitation evidence yet." ko="아직 검토된 한계 근거가 없습니다." /></span>}</div>
            </article>
            <article>
              <h4><LocalizedText en="Future-research leads to inspect" ko="확인할 후속연구 단서" /></h4>
              <div className="noteStack">{q.synthesis?.future_research_leads.length ? q.synthesis.future_research_leads.map((item) => <Link className="noteCard" href={`/library/${item.paper_id}`} key={`${item.paper_id}-${item.text}`}><strong>{item.paper_title}</strong><p>{item.text}</p></Link>) : <span className="muted"><LocalizedText en="No reviewed future-research evidence yet." ko="아직 검토된 후속연구 근거가 없습니다." /></span>}</div>
            </article>
          </div>
        </section>

        <section className="questionThreadEntry questionThreadChallenge">
          <span className="questionThreadEntryIndex">05 · Challenge</span>
          <h3 className="sectionTitle"><LocalizedText en="Challenge the apparent gap" ko="보이는 공백을 반증하기" /></h3>
          <p className="muted"><LocalizedText en="Gap Canvas remains a falsification instrument: broaden synonyms, years, theories, venues, and citation neighbors before promoting a sparse signal into a research direction." ko="Gap Canvas는 계속 반증 도구로 사용합니다. 검색이 적다는 이유만으로 연구공백으로 확정하지 않고, 동의어·연도·이론·저널·인용 이웃을 확장한 뒤 연구방향 후보로 승격합니다." /></p>
          {!readOnly ? <form action={createQuestionGapAction.bind(null, q.id, q.question_text)}><button className="button" type="submit"><LocalizedText en="Run a new falsification pass →" ko="새 반증 탐색 실행 →" /></button></form> : null}
          <div className="noteStack">
            {q.gap_analyses.map((gap) => (
              <article className="questionCard" key={gap.id}>
                <Link className="textLink" href={`/gap-canvas?id=${gap.id}`}><strong>{gap.status}</strong></Link>
                <span>{gap.gap_candidates ?? "No candidate text"}</span>
                {!readOnly && gap.gap_candidates ? <form action={createDirectionFromGapAction.bind(null, q.id, gap.gap_candidates)}><button className="button buttonSecondary" type="submit"><LocalizedText en="Promote to direction for testing" ko="검증할 연구방향으로 승격" /></button></form> : null}
              </article>
            ))}
          </div>
        </section>

        <section className="questionThreadEntry researchDirectionsEntry">
          <span className="questionThreadEntryIndex">06 · Choose</span>
          <div className="sectionHeadingRow"><div><h3 className="sectionTitle"><LocalizedText en="Candidate research directions" ko="후보 연구방향" /></h3><p className="muted"><LocalizedText en="A viable thesis topic is not just a sparse literature area. Score novelty together with theory fit, data access, method feasibility, scope, and your own sustained interest." ko="좋은 논문 주제는 문헌이 적은 영역이 아닙니다. 신규성과 함께 이론 적합성, 데이터 확보 가능성, 방법 실현가능성, 범위, 지속적인 개인 관심도를 함께 평가합니다." /></p></div><span className="pill">{q.directions.length}</span></div>
          <div className="researchDirectionList">
            {q.directions.map((direction) => (
              <article className={`researchDirectionCard direction-${direction.status}`} key={direction.id}>
                <div className="researchDirectionHeader"><div><span className={`statusBadge status-${direction.evidence_status}`}>{direction.status}</span><h4>{direction.title}</h4></div><div className="directionScore"><strong>{direction.score ?? "—"}</strong><span>/ 100</span></div></div>
                <p>{direction.rationale || <LocalizedText en="No rationale recorded yet." ko="아직 연구방향의 근거가 기록되지 않았습니다." />}</p>
                <div className="directionDimensionGrid">{directionDimensions.map(([key, en, ko]) => <div key={key}><span><LocalizedText en={en} ko={ko} /></span><strong>{direction.dimensions[key] ?? "—"}/5</strong></div>)}</div>
                <div className="directionEvidenceGrid"><div><strong><LocalizedText en="Evidence for" ko="지지 근거" /></strong><p>{direction.evidence_for || "—"}</p></div><div><strong><LocalizedText en="Evidence against / invalidation" ko="반대 근거 / 무효화 가능성" /></strong><p>{direction.evidence_against || "—"}</p></div><div><strong><LocalizedText en="Next test" ko="다음 검증" /></strong><p>{direction.next_test || "—"}</p></div></div>
                {!readOnly ? (
                  <details className="directionEditDetails"><summary><LocalizedText en="Edit evaluation" ko="평가 수정" /></summary>
                    <form action={updateDirectionAction.bind(null, q.id, direction.id)} className="formStack researchDirectionForm">
                      <label className="fieldLabel"><LocalizedText en="Direction" ko="연구방향" /><input className="input" name="title" defaultValue={direction.title} required /></label>
                      <label className="fieldLabel"><LocalizedText en="Why this direction?" ko="왜 이 연구방향인가" /><textarea className="textarea" name="rationale" defaultValue={direction.rationale ?? ""} /></label>
                      <div className="directionScoreForm">{directionDimensions.map(([key, en, ko]) => <label className="compactFieldLabel" key={key}><span><LocalizedText en={en} ko={ko} /></span><select className="select" name={key} defaultValue={String(direction.dimensions[key] ?? 3)}>{[1,2,3,4,5].map((score) => <option value={score} key={score}>{score}</option>)}</select></label>)}</div>
                      <label className="fieldLabel"><LocalizedText en="Evidence for" ko="지지 근거" /><textarea className="textarea" name="evidence_for" defaultValue={direction.evidence_for ?? ""} /></label>
                      <label className="fieldLabel"><LocalizedText en="Evidence against" ko="반대 근거" /><textarea className="textarea" name="evidence_against" defaultValue={direction.evidence_against ?? ""} /></label>
                      <label className="fieldLabel"><LocalizedText en="Next falsification / validation step" ko="다음 반증 / 검증 단계" /><textarea className="textarea" name="next_test" defaultValue={direction.next_test ?? ""} /></label>
                      <label className="fieldLabel"><LocalizedText en="Theory fit note" ko="이론 적합성 메모" /><textarea className="textarea" name="theory_note" defaultValue={direction.theory_note ?? ""} /></label>
                      <label className="fieldLabel"><LocalizedText en="Data feasibility note" ko="데이터 가능성 메모" /><textarea className="textarea" name="data_note" defaultValue={direction.data_note ?? ""} /></label>
                      <label className="fieldLabel"><LocalizedText en="Method feasibility note" ko="방법론 가능성 메모" /><textarea className="textarea" name="method_note" defaultValue={direction.method_note ?? ""} /></label>
                      <div className="inlineForm"><label className="compactFieldLabel"><span>Status</span><select className="select" name="status" defaultValue={direction.status}><option value="candidate">Candidate</option><option value="testing">Testing</option><option value="selected">Selected</option><option value="rejected">Rejected</option></select></label><label className="compactFieldLabel"><span>Evidence</span><select className="select" name="evidence_status" defaultValue={direction.evidence_status}><option value="insufficient_evidence">Insufficient</option><option value="mixed">Mixed</option><option value="supported">Supported</option></select></label></div>
                      <button className="button" type="submit"><LocalizedText en="Save direction" ko="연구방향 저장" /></button>
                    </form>
                  </details>
                ) : null}
              </article>
            ))}
          </div>
          {!readOnly ? (
            <details className="newDirectionComposer" open={!q.directions.length}>
              <summary><LocalizedText en="Add a research direction" ko="연구방향 추가" /></summary>
              <form action={createDirectionAction.bind(null, q.id)} className="formStack researchDirectionForm">
                <label className="fieldLabel"><LocalizedText en="Candidate direction" ko="후보 연구방향" /><input className="input" name="title" required placeholder="e.g. Test organizational readiness as a mechanism in Korean manufacturing SMEs" /></label>
                <label className="fieldLabel"><LocalizedText en="Rationale" ko="선정 근거" /><textarea className="textarea" name="rationale" placeholder="What reviewed evidence makes this worth testing?" /></label>
                <div className="directionScoreForm">{directionDimensions.map(([key, en, ko]) => <label className="compactFieldLabel" key={key}><span><LocalizedText en={en} ko={ko} /></span><select className="select" name={key} defaultValue="3">{[1,2,3,4,5].map((score) => <option value={score} key={score}>{score}</option>)}</select></label>)}</div>
                <label className="fieldLabel"><LocalizedText en="Evidence currently for it" ko="현재 지지 근거" /><textarea className="textarea" name="evidence_for" /></label>
                <label className="fieldLabel"><LocalizedText en="Evidence that could invalidate it" ko="무효화할 수 있는 근거" /><textarea className="textarea" name="evidence_against" /></label>
                <label className="fieldLabel"><LocalizedText en="Next test" ko="다음 검증" /><textarea className="textarea" name="next_test" /></label>
                <input type="hidden" name="status" value="candidate" /><input type="hidden" name="evidence_status" value="insufficient_evidence" />
                <button className="button" type="submit"><LocalizedText en="Add candidate direction" ko="후보 연구방향 추가" /></button>
              </form>
            </details>
          ) : null}
        </section>

        <section className="questionThreadEntry researchDesignEntry">
          <span className="questionThreadEntryIndex">07 · Design</span>
          <div className="sectionHeadingRow"><div><h3 className="sectionTitle"><LocalizedText en="Research Design" ko="연구설계" /></h3><p className="muted"><LocalizedText en="Turn the selected direction into a testable study: theory → constructs → variables → unit/context → data → method → analysis → contribution." ko="선택한 연구방향을 실제 검증 가능한 연구로 바꿉니다: 이론 → 구성개념 → 변수 → 분석단위/맥락 → 데이터 → 방법 → 분석 → 기여." /></p></div><span className="pill">{q.design?.readiness_pct ?? 0}%</span></div>
          {!readOnly ? (
            <form action={saveResearchDesignAction.bind(null, q.id)} className="researchDesignForm">
              <label className="fieldLabel"><LocalizedText en="Selected direction" ko="선택한 연구방향" /><select className="select" name="selected_direction_id" defaultValue={q.design?.selected_direction_id ?? ""}><option value="">Not selected yet</option>{q.directions.filter((item) => item.status !== "rejected").map((direction) => <option value={direction.id} key={direction.id}>{direction.title}</option>)}</select></label>
              <label className="fieldLabel"><LocalizedText en="Theoretical framework" ko="이론적 프레임워크" /><textarea className="textarea" name="theoretical_framework" defaultValue={q.design?.theoretical_framework ?? ""} placeholder="Dynamic capabilities, TOE, RBV… and why it explains the mechanism" /></label>
              <label className="fieldLabel"><LocalizedText en="Focal constructs" ko="핵심 구성개념" /><textarea className="textarea" name="focal_constructs" defaultValue={q.design?.focal_constructs ?? ""} /></label>
              <div className="researchDesignTwoCol"><label className="fieldLabel"><LocalizedText en="Independent variables" ko="독립변수" /><textarea className="textarea compactTextarea" name="independent_variables" defaultValue={q.design?.independent_variables ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Dependent variables" ko="종속변수" /><textarea className="textarea compactTextarea" name="dependent_variables" defaultValue={q.design?.dependent_variables ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Mediators" ko="매개변수" /><textarea className="textarea compactTextarea" name="mediators" defaultValue={q.design?.mediators ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Moderators" ko="조절변수" /><textarea className="textarea compactTextarea" name="moderators" defaultValue={q.design?.moderators ?? ""} /></label></div>
              <div className="researchDesignTwoCol"><label className="fieldLabel"><LocalizedText en="Unit of analysis" ko="분석 단위" /><input className="input" name="unit_of_analysis" defaultValue={q.design?.unit_of_analysis ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Context / population" ko="맥락 / 모집단" /><input className="input" name="context_population" defaultValue={q.design?.context_population ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Data sources" ko="데이터 소스" /><textarea className="textarea compactTextarea" name="data_sources" defaultValue={q.design?.data_sources ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Sampling plan" ko="표본 계획" /><textarea className="textarea compactTextarea" name="sampling_plan" defaultValue={q.design?.sampling_plan ?? ""} /></label></div>
              <div className="researchDesignTwoCol"><label className="fieldLabel"><LocalizedText en="Methodology" ko="연구방법" /><textarea className="textarea compactTextarea" name="methodology" defaultValue={q.design?.methodology ?? ""} /></label><label className="fieldLabel"><LocalizedText en="Analysis plan" ko="분석 계획" /><textarea className="textarea compactTextarea" name="analysis_plan" defaultValue={q.design?.analysis_plan ?? ""} /></label></div>
              <label className="fieldLabel"><LocalizedText en="Hypotheses / propositions" ko="가설 / 명제" /><textarea className="textarea" name="hypotheses" defaultValue={q.design?.hypotheses ?? ""} /></label>
              <label className="fieldLabel"><LocalizedText en="Feasibility notes" ko="실현가능성 메모" /><textarea className="textarea" name="feasibility_notes" defaultValue={q.design?.feasibility_notes ?? ""} /></label>
              <label className="fieldLabel"><LocalizedText en="Ethics / access constraints" ko="윤리 / 접근 제약" /><textarea className="textarea" name="ethics_constraints" defaultValue={q.design?.ethics_constraints ?? ""} /></label>
              <label className="fieldLabel"><LocalizedText en="Expected contribution" ko="예상 연구기여" /><textarea className="textarea" name="expected_contribution" defaultValue={q.design?.expected_contribution ?? ""} /></label>
              <div className="researchDesignSaveRow"><label className="compactFieldLabel"><span>Status</span><select className="select" name="status" defaultValue={q.design?.status ?? "draft"}><option value="draft">Draft</option><option value="developing">Developing</option><option value="ready">Ready for proposal</option></select></label><button className="button" type="submit"><LocalizedText en="Save Research Design" ko="연구설계 저장" /></button></div>
            </form>
          ) : (
            <dl className="questionStateSummary researchDesignSummary">
              <div><dt><LocalizedText en="Theory" ko="이론" /></dt><dd>{q.design?.theoretical_framework || "—"}</dd></div><div><dt><LocalizedText en="Constructs" ko="구성개념" /></dt><dd>{q.design?.focal_constructs || "—"}</dd></div><div><dt><LocalizedText en="Unit / context" ko="분석단위 / 맥락" /></dt><dd>{[q.design?.unit_of_analysis, q.design?.context_population].filter(Boolean).join(" · ") || "—"}</dd></div><div><dt><LocalizedText en="Data" ko="데이터" /></dt><dd>{q.design?.data_sources || "—"}</dd></div><div><dt><LocalizedText en="Method / analysis" ko="방법 / 분석" /></dt><dd>{[q.design?.methodology, q.design?.analysis_plan].filter(Boolean).join(" · ") || "—"}</dd></div><div><dt><LocalizedText en="Hypotheses" ko="가설" /></dt><dd>{q.design?.hypotheses || "—"}</dd></div><div><dt><LocalizedText en="Contribution" ko="기여" /></dt><dd>{q.design?.expected_contribution || "—"}</dd></div>
            </dl>
          )}
          {q.design?.missing_fields.length ? <p className="metricHelp"><LocalizedText en={`Still missing: ${q.design.missing_fields.join(", ")}`} ko={`아직 필요한 항목: ${q.design.missing_fields.join(", ")}`} /></p> : null}
          <Link className="button proposalBuilderCta" href={`/questions/${q.id}/proposal`}><LocalizedText en="Assemble proposal outline →" ko="연구계획서 개요 조립 →" /></Link>
        </section>

        <section className="questionThreadEntry questionThreadNotes">
          <span className="questionThreadEntryIndex">08 · Journal</span>
          <h3 className="sectionTitle"><LocalizedText en="Question notes" ko="질문 노트" /></h3>
          {!readOnly ? <form action={addQuestionNoteAction.bind(null, q.id)} className="inlineForm"><input className="input" name="note" placeholder="Working note, concern, next search… / 작업 노트, 우려, 다음 검색" /><button className="button" type="submit"><LocalizedText en="Add note" ko="노트 추가" /></button></form> : null}
          <div className="noteStack">{q.notes.length ? q.notes.map((note) => <div className="noteCard" key={note.id}>{note.note_markdown}</div>) : <span className="muted"><LocalizedText en="No notes yet." ko="아직 노트가 없습니다." /></span>}</div>
        </section>
        </div>
      </article>
    </>
  );
}
