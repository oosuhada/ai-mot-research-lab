import Link from "next/link";

import { MutationFeedback } from "@/components/MutationFeedback";
import { LocalizedText } from "@/components/LocalizedText";
import { listResearchQuestions } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { createQuestionAction } from "./actions";

const startingPoints = [
  ["AI capability → innovation performance", "AI 역량 → 혁신 성과", "AI capability innovation performance dynamic capabilities"],
  ["Human–AI decision rights", "인간–AI 의사결정 권한", "human AI collaboration decision making organizational design"],
  ["Agentic workflows in firms", "기업의 에이전틱 워크플로", "AI agents enterprise workflows human oversight"],
] as const;

export default async function QuestionsPage({ searchParams }: { searchParams: Promise<{ feedback?: string }> }) {
  const params = await searchParams;
  const questions = await listResearchQuestions();
  const readOnly = isWorkspaceReadOnly();

  return (
    <>
      {!readOnly ? (
        <MutationFeedback
          feedback={params.feedback}
          messages={{
            "invalid-question": { message: "Enter a research question before creating the workspace.", tone: "error" },
            error: { message: "The research question could not be created. Your workspace was not changed.", tone: "error" },
          }}
        />
      ) : null}
      <header className="pageHeader">
        <div>
          <p className="eyebrow"><LocalizedText en="Research Questions" ko="연구 질문" /></p>
          <h2 className="pageTitle"><LocalizedText en="The question is the unit of work." ko="연구 작업의 중심 단위는 질문입니다." /></h2>
          <p className="pageIntro">
            <LocalizedText en="Frame the question first, then attach searches, papers, comparisons, candidate gaps, and uncertainty to it." ko="질문을 먼저 정의한 뒤 검색, 논문, 비교, 연구 공백 후보, 불확실성을 하나의 흐름으로 연결하세요." />
          </p>
        </div>
      </header>

      <section className="questionWorkbench">
        <article className="questionComposer">
          <div className="questionComposerHeader">
            <span className="cardKicker"><LocalizedText en={readOnly ? "Public demo" : "New workspace"} ko={readOnly ? "공개 데모" : "새 워크스페이스"} /></span>
            <h3><LocalizedText en={readOnly ? "See how a research question organizes the work." : "What do you actually want to explain?"} ko={readOnly ? "연구 질문이 작업 전체를 어떻게 구성하는지 살펴보세요." : "실제로 무엇을 설명하고 싶나요?"} /></h3>
            <p><LocalizedText en={readOnly ? "This portfolio deployment is read-only. Open an existing question to inspect its papers, comparisons, gap candidates, and uncertainty without changing shared data." : "Keep it specific enough to test, but broad enough to search before locking the design."} ko={readOnly ? "이 포트폴리오 배포 환경은 읽기 전용입니다. 기존 질문을 열어 공유 데이터를 변경하지 않고 논문, 비교, 공백 후보, 불확실성을 살펴보세요." : "검증할 수 있을 만큼 구체적이면서도 연구 설계를 확정하기 전에 충분히 탐색할 수 있는 질문을 만드세요."} /></p>
          </div>
          {!readOnly ? <form action={createQuestionAction} className="formStack questionForm">
            <label className="fieldLabel"><LocalizedText en="Working title" ko="작업 제목" /><input className="input" name="title" placeholder="e.g. AI capability and innovation performance" /></label>
            <label className="fieldLabel"><LocalizedText en="Research question" ko="연구 질문" /><textarea className="textarea questionTextarea" name="question_text" required placeholder="How does AI capability affect innovation performance, and under which organizational conditions?" /></label>
            <div className="questionFormGrid">
              <label className="fieldLabel"><LocalizedText en="Why it matters" ko="왜 중요한가" /><textarea className="textarea compactTextarea" name="motivation" placeholder="Managerial or theoretical motivation" /></label>
              <label className="fieldLabel"><LocalizedText en="What is uncertain" ko="무엇이 불확실한가" /><textarea className="textarea compactTextarea" name="uncertainty_notes" placeholder="Boundary conditions, causal direction, missing context…" /></label>
            </div>
            <input type="hidden" name="importance_notes" value="" />
            <button className="button questionCreateButton" type="submit"><LocalizedText en="Create research workspace →" ko="연구 워크스페이스 만들기 →" /></button>
          </form> : <div className="readOnlyPanel questionReadOnlyPanel"><strong><LocalizedText en="Public Demo · Read-only" ko="공개 데모 · 읽기 전용" /></strong><span><LocalizedText en="Creation and editing are disabled. You can still follow the full evidence trail." ko="생성과 편집은 비활성화되어 있지만 전체 근거 흐름은 확인할 수 있습니다." /></span>{questions[0] ? <Link className="button" href={`/questions/${questions[0].id}`}><LocalizedText en="Open sample workspace →" ko="샘플 워크스페이스 열기 →" /></Link> : <Link className="button" href="/library"><LocalizedText en="Explore the corpus →" ko="코퍼스 살펴보기 →" /></Link>}</div>}
        </article>

        <aside className="questionSidePanel">
          <div>
            <span className="cardKicker"><LocalizedText en="Your pipeline" ko="연구 파이프라인" /></span>
            <div className="questionCount">{questions.length}</div>
            <p className="metricHelp"><LocalizedText en="research questions currently in the workspace" ko="현재 워크스페이스의 연구 질문" /></p>
          </div>
          <div className="questionSideDivider" />
          <div>
            <h4><LocalizedText en="Not ready to frame it yet?" ko="아직 질문을 정의하기 어렵나요?" /></h4>
            <p className="metricHelp"><LocalizedText en="Start from a literature cluster and come back with a sharper question." ko="문헌 클러스터에서 시작해 더 선명한 질문으로 돌아오세요." /></p>
            <div className="starterStack">
              {startingPoints.map(([label, koreanLabel, query]) => (
                <Link href={`/library?q=${encodeURIComponent(query)}&mode=hybrid`} className="starterLink" key={label}>
                  <span><LocalizedText en={label} ko={koreanLabel} /></span><b>↗</b>
                </Link>
              ))}
            </div>
          </div>
        </aside>
      </section>

      <section className="questionListSection">
        <div className="sectionHeadingRow">
          <div><span className="cardKicker"><LocalizedText en="Research pipeline" ko="연구 파이프라인" /></span><h3 className="sectionTitle"><LocalizedText en="Active questions" ko="활성 연구 질문" /></h3></div>
          <Link href="/library" className="textLink"><LocalizedText en="Search before framing →" ko="질문 정의 전 검색하기 →" /></Link>
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
                  <span><LocalizedText en={`${question.papers.length} papers`} ko={`논문 ${question.papers.length}편`} /></span>
                  <span><LocalizedText en={`${question.gap_analyses.length} gap canvases`} ko={`연구 공백 캔버스 ${question.gap_analyses.length}개`} /></span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="emptyState questionEmptyState">
            <strong><LocalizedText en="No research question yet." ko="아직 연구 질문이 없습니다." /></strong>
            <span><LocalizedText en="Create one above, or search a cluster first and come back when the uncertainty becomes clearer." ko="위에서 질문을 만들거나 먼저 문헌 클러스터를 검색한 뒤 불확실성이 더 명확해졌을 때 돌아오세요." /></span>
          </div>
        )}
      </section>
    </>
  );
}
