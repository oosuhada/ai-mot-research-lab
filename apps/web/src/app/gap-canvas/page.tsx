import { challengeGapCanvas, createGapCanvas, editGapCanvas } from "./actions";
import EvidenceWorkspace from "./EvidenceWorkspace";
import { MutationFeedback } from "@/components/MutationFeedback";
import { LocalizedText } from "@/components/LocalizedText";
import { getGapAnalysis, getResearchQuestion, listResearchQuestions } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";
import styles from "./GapCanvas.module.css";

const editableSections = [
  ["research_clusters", "Representative research clusters", "대표 연구 클러스터"],
  ["agreements", "Agreements", "합의되는 근거"],
  ["conflicts", "Conflicts", "충돌하는 근거"],
  ["under_studied_contexts", "Under-studied contexts / coverage signals", "과소 연구 맥락 / 수집 신호"],
  ["gap_candidates", "Candidate gap hypothesis", "연구 공백 후보 가설"],
  ["falsifiability_notes", "How to falsify the candidate hypothesis", "후보 가설 반증 방법"],
  ["follow_up_questions", "Follow-up research questions", "후속 연구 질문"],
  ["theoretical_lenses", "Candidate theoretical lenses", "후보 이론적 관점"],
  ["candidate_data_methods", "Candidate data and methods", "후보 데이터와 연구방법"],
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
            <p className={styles.heroKicker}><span className={styles.heroIndex}>05</span> <LocalizedText en="Research Question · Gap Canvas" ko="연구 질문 · 연구 공백 캔버스" /></p>
            <h1 className={styles.heroTitle}>
              <span className={styles.heroTitleLine}><LocalizedText en="Map the evidence." ko="근거를 지도화하고," /></span>
              <span className={styles.heroTitleSignal}><LocalizedText en="Challenge the gap." ko="공백 가설을 반증하세요." /></span>
            </h1>
            <p className={styles.heroIntro}>
              <LocalizedText en="A claim-level research instrument for tracing papers, source-backed evidence, support states, and falsifiable candidate hypotheses without treating sparse retrieval as proof." ko="희소한 검색 결과를 증거로 단정하지 않으면서 논문, 출처 기반 근거, 지지 상태, 반증 가능한 후보 가설을 추적하는 주장 단위 연구 도구입니다." />
            </p>
            <div className={styles.heroMeta}>
              <span><LocalizedText en="evidence-first" ko="근거 우선" /></span>
              <span><LocalizedText en="claim-level provenance" ko="주장 단위 출처 이력" /></span>
              <span><LocalizedText en="candidate ≠ conclusion" ko="후보 ≠ 결론" /></span>
            </div>
          </div>
          <div className={styles.instrument} aria-label="Evidence workflow summary">
            <div className={styles.instrumentTop}>
              <span><LocalizedText en="Evidence instrument" ko="근거 분석 도구" /></span>
              <span className={styles.instrumentLive}><LocalizedText en={analysis ? "analysis loaded" : "ready"} ko={analysis ? "분석 불러옴" : "준비됨"} /></span>
            </div>
            <div className={styles.instrumentFlow}>
              <div className={styles.instrumentStep}><i /><span><LocalizedText en="Research question" ko="연구 질문" /></span><small><LocalizedText en="input" ko="입력" /></small></div>
              <div className={styles.instrumentStep}><i /><span><LocalizedText en="Evidence papers" ko="근거 논문" /></span><small>{analysis ? linkedPaperCount : <LocalizedText en="retrieve" ko="검색" />}</small></div>
              <div className={styles.instrumentStep}><i /><span><LocalizedText en="Paper-backed claims" ko="논문 기반 주장" /></span><small>{analysis ? paperClaimCount : <LocalizedText en="extract" ko="추출" />}</small></div>
              <div className={styles.instrumentStep}><i /><span><LocalizedText en="Agreement / conflict" ko="합의 / 충돌" /></span><small><LocalizedText en="review" ko="검토" /></small></div>
              <div className={styles.instrumentStep}><i /><span><LocalizedText en="Candidate hypothesis" ko="후보 가설" /></span><small><LocalizedText en="falsify" ko="반증" /></small></div>
            </div>
          </div>
        </div>
      </header>

      {!analysis ? (
        <section className={styles.launchPanel}>
          <div className={styles.launchComposer}>
            <p className="eyebrow"><LocalizedText en="New analysis" ko="새 분석" /></p>
            <h3><LocalizedText en="Ask a question worth trying to disprove." ko="반증해볼 가치가 있는 질문을 제시하세요." /></h3>
            <p>
              <LocalizedText en="Start from a research question, retrieve the local corpus, inspect source-backed claims, then challenge the candidate hypothesis with broader search and citation neighbors." ko="연구 질문에서 시작해 로컬 코퍼스를 검색하고 출처 기반 주장을 확인한 뒤, 더 넓은 검색과 인용 이웃 논문으로 후보 가설을 반증하세요." />
            </p>
            {!readOnly ? <form className={styles.launchForm} action={createGapCanvas}>
              <input
                name="topic"
                required
                minLength={3}
                placeholder="How does AI capability change innovation performance in manufacturing SMEs?"
              />
              <button type="submit"><LocalizedText en="Build evidence canvas →" ko="근거 캔버스 만들기 →" /></button>
            </form> : <div className="readOnlyPanel"><strong><LocalizedText en="Public Demo · Read-only" ko="공개 데모 · 읽기 전용" /></strong><span><LocalizedText en="Create and edit actions are disabled on the portfolio deployment. Open a saved canvas to inspect the evidence map and falsification logic." ko="포트폴리오 배포 환경에서는 생성과 편집이 비활성화됩니다. 저장된 캔버스를 열어 근거 지도와 반증 논리를 확인하세요." /></span><div className="tagCloud">{demoGapAnalyses.slice(0, 6).map((gap) => <a className="pill" href={`/gap-canvas?id=${gap.id}`} key={gap.id}>{gap.questionTitle}</a>)}</div></div>}
          </div>
          <aside className={styles.launchAside}>
            <div className={styles.launchAsideRow}><span>01</span><div><strong><LocalizedText en="Retrieve" ko="검색" /></strong><p><LocalizedText en="Build a review set without equating density with truth." ko="수집 밀도를 진실과 동일시하지 않고 검토 세트를 구성합니다." /></p></div></div>
            <div className={styles.launchAsideRow}><span>02</span><div><strong><LocalizedText en="Trace" ko="추적" /></strong><p><LocalizedText en="Move from paper → claim → source locator instead of opaque summaries." ko="불투명한 요약 대신 논문 → 주장 → 근거 위치로 이동합니다." /></p></div></div>
            <div className={styles.launchAsideRow}><span>03</span><div><strong><LocalizedText en="Challenge" ko="반증" /></strong><p><LocalizedText en="Use contradiction and citation candidates to falsify the hypothesis." ko="반대 근거와 인용 후보를 사용해 가설을 반증합니다." /></p></div></div>
          </aside>
        </section>
      ) : (
        <>
          <EvidenceWorkspace analysis={analysis} history={researchQuestion?.gap_analyses ?? []} />

          <div className={`grid ${styles.resultGrid}`}>
            <section className={`card span6 ${styles.candidatePanel}`}>
              <div className="resultSummary">
                <span className="statusBadge status-insufficient_evidence"><LocalizedText en="Candidate hypothesis" ko="후보 가설" /></span>
                <span className="pill"><LocalizedText en="Needs falsification" ko="반증 필요" /></span>
              </div>
              <h3 className="sectionTitle"><LocalizedText en="Structured candidate hypothesis" ko="구조화된 후보 가설" /></h3>
              {analysis.candidate_gap ? (
                <div className="formStack">
                  <div><span className="metricLabel"><LocalizedText en="Hypothesis" ko="가설" /></span><p>{analysis.candidate_gap.hypothesis}</p></div>
                  <div><span className="metricLabel"><LocalizedText en="Evidence currently supporting the signal" ko="현재 신호를 지지하는 근거" /></span>{analysis.candidate_gap.evidence_for.length ? analysis.candidate_gap.evidence_for.map((item) => <p key={item}>{item}</p>) : <p className="muted"><LocalizedText en="No supported evidence claim is linked yet." ko="아직 연결된 지지 근거 주장이 없습니다." /></p>}</div>
                  <div><span className="metricLabel"><LocalizedText en="Invalidation risk" ko="무효화 위험" /></span>{analysis.candidate_gap.evidence_against.map((item) => <p key={item}>{item}</p>)}</div>
                  <div><span className="metricLabel"><LocalizedText en="Falsifiability" ko="반증 가능성" /></span><p>{analysis.candidate_gap.falsifiability_note}</p></div>
                  <div><span className="metricLabel"><LocalizedText en="Next search query" ko="다음 검색어" /></span><code className="queryCode">{analysis.candidate_gap.next_search_query}</code></div>
                  <div><span className="metricLabel"><LocalizedText en="Candidate method" ko="후보 연구방법" /></span><p>{analysis.candidate_gap.candidate_method ?? <LocalizedText en="Not specified." ko="지정되지 않음" />}</p></div>
                  {!readOnly ? <form action={challengeGapCanvas.bind(null, analysis.id, analysis.research_question_id, analysis.candidate_gap.next_search_query)} className="formStack">
                    <button className="button" type="submit"><LocalizedText en="Run broader falsification pass" ko="확장 반증 검색 실행" /></button>
                    <p className="metricHelp">Creates a new analysis history entry with a broader 40-paper retrieval pass. New citation neighbors remain unscreened candidates until reviewed.</p>
                  </form> : <p className="metricHelp">Read-only demo: the broader falsification pass is visible as a workflow concept but cannot create a new shared analysis.</p>}
                </div>
              ) : <div className="emptyState"><LocalizedText en="No candidate hypothesis has been structured yet." ko="아직 구조화된 후보 가설이 없습니다." /></div>}
            </section>

            <section className={`card span6 ${styles.scopePanel}`}>
              <h3 className="sectionTitle"><LocalizedText en="Evidence-linked scope" ko="근거 연결 범위" /></h3>
              <p className="metricHelp"><LocalizedText en="These distributions describe only papers linked as evidence on this canvas, not the full literature." ko="이 분포는 전체 문헌이 아니라 이 캔버스에 근거로 연결된 논문만 설명합니다." /></p>
              <h4><LocalizedText en="Methodology heuristics" ko="연구방법 휴리스틱" /></h4>
              <div className="tagCloud">
                {analysis.methodology_distribution.length
                  ? analysis.methodology_distribution.map((item) => <span className="pill" key={item.slug}>{item.display_name}: {item.paper_count}</span>)
                  : <span className="muted">No methodology heuristic evidence.</span>}
              </div>
              <h4><LocalizedText en="Publication years" ko="출판 연도" /></h4>
              <div className="tagCloud">
                {analysis.year_distribution.length
                  ? analysis.year_distribution.map((item) => <span className="pill" key={item.year}>{item.year}: {item.paper_count}</span>)
                  : <span className="muted">No publication-year distribution.</span>}
              </div>
              <h4><LocalizedText en="Research axes" ko="연구 축" /></h4>
              <div className="tagCloud">
                {analysis.evidence_clusters.length
                  ? analysis.evidence_clusters.map((cluster) => <span className="pill" key={cluster.slug}>{cluster.display_name}: {cluster.paper_ids.length}</span>)
                  : <span className="muted">No research-axis assignments linked to this evidence set.</span>}
              </div>
            </section>

            <section className={`card span12 ${styles.policyPanel}`}>
              <h3 className="sectionTitle"><LocalizedText en="Retrieval and review policy" ko="검색 및 검토 정책" /></h3>
              <div className="policyGrid">
                <div><span className="metricLabel"><LocalizedText en="Search strategy" ko="검색 전략" /></span><p>{analysis.search_strategy}</p></div>
                <div><span className="metricLabel"><LocalizedText en="Include" ko="포함 기준" /></span><p>{analysis.inclusion_criteria}</p></div>
                <div><span className="metricLabel"><LocalizedText en="Exclude" ko="제외 기준" /></span><p>{analysis.exclusion_criteria}</p></div>
              </div>
            </section>

            <section className={`card span12 ${styles.notesPanel}`}>
              <div className="resultSummary">
                <h3 className="sectionTitle"><LocalizedText en="Research synthesis notes" ko="연구 종합 노트" /></h3>
                <span className="pill"><LocalizedText en="Secondary notebook · user-note claims" ko="보조 노트 · 사용자 노트 주장" /></span>
              </div>
              {!readOnly ? <details className={styles.notesDisclosure}>
                <summary><LocalizedText en="Open the synthesis notebook after reviewing the evidence map" ko="근거 지도를 검토한 뒤 종합 노트 열기" /></summary>
                <form action={editGapCanvas.bind(null, analysis.id)} className="editorStack">
                  <div className="grid">
                    {editableSections.map(([field, label, koreanLabel]) => (
                      <label className="editorField span6" key={field}>
                        <span><LocalizedText en={label} ko={koreanLabel} /></span>
                        <textarea
                          className="input textarea"
                          name={field}
                          defaultValue={analysis[field] ?? ""}
                          rows={4}
                        />
                      </label>
                    ))}
                  </div>
                  <button className="button" type="submit"><LocalizedText en="Save synthesis notes" ko="종합 노트 저장" /></button>
                </form>
              </details> : <div className="grid readOnlySynthesisGrid">{editableSections.map(([field, label, koreanLabel]) => <div className="readOnlySynthesisField span6" key={field}><span className="metricLabel"><LocalizedText en={label} ko={koreanLabel} /></span><p>{analysis[field] || <LocalizedText en="No note recorded." ko="기록된 노트가 없습니다." />}</p></div>)}</div>}
            </section>
          </div>
        </>
      )}
    </>
  );
}
