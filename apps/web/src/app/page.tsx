import Link from "next/link";

import { CitationAtlas } from "@/components/CitationAtlas";
import { LocalizedHomeSearch, LocalizedTaxonomyText, LocalizedText } from "@/components/LocalizedText";
import { getCorpusCoverage, getLandscape, listResearchQuestions } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

const fallbackAxes = [
  "AI adoption and business value",
  "Technology and innovation management",
  "AI-enabled organizational change",
  "Industrial AI and smart operations",
  "AI governance and responsible deployment",
  "Agentic systems and enterprise workflows",
];

export default async function HomePage() {
  const [landscape, questions, coverage] = await Promise.all([
    getLandscape(),
    listResearchQuestions(),
    getCorpusCoverage(),
  ]);
  const readOnly = isWorkspaceReadOnly();
  const axes = landscape?.axes ?? fallbackAxes.map((display_name, index) => ({
    slug: `axis-${index}`,
    display_name,
    paper_count: 0,
    abstract_paper_count: 0,
    full_text_paper_count: 0,
    oa_paper_count: 0,
    parent_slug: null,
    years: [],
    top_methodologies: [],
  }));
  const methodologies = landscape?.methodologies ?? [];
  const oaRatio = landscape?.total_papers ? Math.round((landscape.oa_papers / landscape.total_papers) * 100) : 0;
  const abstractRatio = landscape?.total_papers ? Math.round((landscape.abstract_papers / landscape.total_papers) * 100) : 0;
  const missingAbstracts = Math.max((landscape?.total_papers ?? 0) - (landscape?.abstract_papers ?? 0), 0);
  const fullTextRatio = landscape?.total_papers ? Math.round((landscape.full_text_papers / landscape.total_papers) * 100) : 0;
  const years = landscape?.years ?? [];
  const coverageStart = years.at(0)?.year;
  const coverageEnd = years.at(-1)?.year;
  const dominantYear = years.reduce((current, candidate) => candidate.paper_count > current.paper_count ? candidate : current, years[0] ?? { year: 0, paper_count: 0 });
  const dominantYearRatio = landscape?.total_papers && dominantYear.year ? Math.round((dominantYear.paper_count / landscape.total_papers) * 100) : 0;

  return (
    <>
      <section className="researchThreadHero">
        <div className="researchThreadLead">
          <div className="researchThreadMarker"><span><LocalizedText en="Field note" ko="연구 기록" /></span><strong>01</strong></div>
          <p className="eyebrow"><LocalizedText en="Scholarly Atlas × Living Research Journal" ko="학술 지도 × 살아있는 연구 저널" /></p>
          <h2><LocalizedText en="What has the literature actually explained about AI and management of technology?" ko="AI와 기술경영에 관해 기존 문헌은 실제로 무엇을 설명했을까요?" /></h2>
          <p>
            <LocalizedText
              en="Begin with a research question, not a dashboard metric. Move outward through evidence territories, paper records, comparison arguments, and falsification paths while keeping provenance visible."
              ko="대시보드 수치가 아니라 연구 질문에서 시작하세요. 출처를 계속 확인하면서 근거 영역, 논문 기록, 비교 논증, 반증 경로로 탐색을 확장합니다."
            />
          </p>
          <LocalizedHomeSearch />
        </div>

        <aside className="researchQuestionLedger" aria-label="Research question ledger">
          <div className="ledgerTitleRow"><span><LocalizedText en="Research question thread" ko="연구 질문 스레드" /></span><small><LocalizedText en={`${questions.length} active`} ko={`${questions.length}개 활성`} /></small></div>
          {questions.length ? questions.slice(0, 4).map((question, index) => (
            <Link className="ledgerQuestion" href={`/questions/${question.id}`} key={question.id}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{question.title}</strong>
              <small><LocalizedText en="Open journal thread →" ko="연구 저널 열기 →" /></small>
            </Link>
          )) : (
            <div className="ledgerQuestion ledgerQuestionEmpty">
              <span>01</span><strong><LocalizedText en="No saved question yet." ko="저장된 연구 질문이 없습니다." /></strong><small><LocalizedText en="Frame one before claiming a gap." ko="연구 공백을 주장하기 전에 질문을 먼저 정의하세요." /></small>
            </div>
          )}
          <Link className="ledgerFootLink" href="/questions"><LocalizedText en={readOnly ? "Explore research questions →" : "Create a research question →"} ko={readOnly ? "연구 질문 살펴보기 →" : "연구 질문 만들기 →"} /></Link>
        </aside>
      </section>

      <nav className="researchThreadRail" aria-label="Research workflow">
        <Link href="/questions"><span><LocalizedText en="Question" ko="연구 질문" /></span><small><LocalizedText en="frame the thread" ko="탐색 범위 정의" /></small></Link>
        <Link href="/library"><span><LocalizedText en="Library" ko="논문 라이브러리" /></span><small><LocalizedText en="collect evidence" ko="근거 수집" /></small></Link>
        <Link href="/compare"><span><LocalizedText en="Compare" ko="논문 비교" /></span><small><LocalizedText en="test differences" ko="차이 검증" /></small></Link>
        <Link href="/gap-canvas"><span><LocalizedText en="Gap Canvas" ko="연구 공백 캔버스" /></span><small><LocalizedText en="challenge the claim" ko="주장 검토" /></small></Link>
        <Link href="/chat"><span><LocalizedText en="Evidence Chat" ko="근거 채팅" /></span><small><LocalizedText en="inspect synthesis" ko="종합 결과 점검" /></small></Link>
      </nav>

      <CitationAtlas
        axes={axes}
        subaxes={landscape?.subaxes ?? []}
        years={years}
        totalPapers={landscape?.total_papers ?? 0}
        coverage={coverage}
      />

      <section className="evidenceDepthLedger" aria-label="Corpus evidence depth">
        <header>
          <p className="eyebrow"><LocalizedText en="Evidence depth" ko="근거 분석 깊이" /></p>
          <h3><LocalizedText en="One corpus, three levels of evidence." ko="하나의 코퍼스, 세 단계의 근거 깊이." /></h3>
          <p><LocalizedText en="Metadata, abstracts, and full text are tracked separately so shallow discovery never masquerades as deep reading." ko="서지정보, 초록, 논문 전문을 분리해서 관리하므로 얕은 탐색 결과를 전문 기반 분석처럼 보이지 않습니다." /></p>
        </header>
        <div className="evidenceDepthGrid">
          <article><span>01</span><strong>{(coverage?.total_records ?? landscape?.total_papers ?? 0).toLocaleString()}</strong><p><LocalizedText en="Research records" ko="전체 연구 레코드" /></p><small><LocalizedText en="Papers with bibliographic metadata" ko="서지정보가 있는 전체 논문" /></small></article>
          <article><span>02</span><strong>{(coverage?.abstract_ready ?? landscape?.abstract_papers ?? 0).toLocaleString()}</strong><p><LocalizedText en="Abstract-ready" ko="초록 분석 가능" /></p><small><LocalizedText en="Fast abstract-level analysis" ko="초록 기반 빠른 분석 가능" /></small></article>
          <article><span>03</span><strong>{(coverage?.full_text_ready ?? landscape?.full_text_papers ?? 0).toLocaleString()}</strong><p><LocalizedText en="Full-text evidence" ko="전문 근거" /></p><small><LocalizedText en="Deep full-text analysis" ko="전문 기반 깊은 분석 가능" /></small></article>
          <article><span><LocalizedText en="Queue" ko="대기열" /></span><strong>{(coverage?.full_text_queued ?? landscape?.full_text_queued ?? 0).toLocaleString()}</strong><p><LocalizedText en="Lazy enrichment" ko="순차 전문 보강" /></p><small><LocalizedText en="Prioritized by rights and importance" ko="권리와 중요도에 따라 순차 처리" /></small></article>
          <article><span>KO</span><strong>{(coverage?.translated_ko ?? 0).toLocaleString()}</strong><p><LocalizedText en="Korean-ready" ko="한국어 준비 완료" /></p><small><LocalizedText en="Verifiable Korean translations" ko="검증 가능한 한글 번역본" /></small></article>
        </div>
      </section>

      <section className="fieldJournal" aria-label="Corpus field notes">
        <header className="fieldJournalHeader">
          <p className="eyebrow"><LocalizedText en="Field journal · corpus diagnostics" ko="연구 기록 · 코퍼스 진단" /></p>
          <h3><LocalizedText en="Read the limits beside the evidence." ko="근거와 함께 한계도 확인하세요." /></h3>
          <p><LocalizedText en="These notes describe the local corpus. They do not claim to describe the full scholarly field." ko="이 기록은 로컬 코퍼스의 상태를 설명하며 전체 학문 분야를 대표한다고 주장하지 않습니다." /></p>
        </header>
        <div className="fieldJournalColumns">
          <article className="fieldNoteBlock">
            <span className="fieldNoteNumber">A</span>
            <h4><LocalizedText en="Coverage ledger" ko="수집 범위 기록" /></h4>
            <dl>
              <div><dt><LocalizedText en="Period" ko="수집 기간" /></dt><dd>{coverageStart && coverageEnd ? `${coverageStart}–${coverageEnd}` : "—"}</dd></div>
              <div><dt><LocalizedText en="Open-access metadata" ko="오픈 액세스 서지정보" /></dt><dd>{oaRatio}%</dd></div>
              <div><dt><LocalizedText en="Missing abstracts" ko="초록 없음" /></dt><dd>{missingAbstracts} · {abstractRatio}% <LocalizedText en="abstract coverage" ko="초록 수집률" /></dd></div>
              <div><dt><LocalizedText en="Full-text evidence" ko="전문 근거" /></dt><dd>{fullTextRatio}% · {landscape?.full_text_papers ?? 0} <LocalizedText en="records" ko="건" /></dd></div>
              <div><dt><LocalizedText en="Last ingestion" ko="최근 수집" /></dt><dd>{landscape?.last_ingestion_at ? new Date(landscape.last_ingestion_at).toLocaleDateString("en-CA") : "—"}</dd></div>
            </dl>
          </article>

          <article className="fieldNoteBlock">
            <span className="fieldNoteNumber">B</span>
            <h4><LocalizedText en="Method signals" ko="연구방법 신호" /></h4>
            <p><LocalizedText en="Heuristic labels are system inference, never author-reported methodology." ko="휴리스틱 라벨은 시스템 추론이며 저자가 직접 보고한 연구방법이 아닙니다." /></p>
            <ol className="methodLedger">
              {methodologies.slice(0, 7).map((method) => <li key={method.slug}><span><LocalizedTaxonomyText label={method.display_name} /></span><strong>{method.paper_count}</strong></li>)}
            </ol>
          </article>

          <article className="fieldNoteBlock fieldNoteRules">
            <span className="fieldNoteNumber">C</span>
            <h4><LocalizedText en="Interpretation rules" ko="해석 원칙" /></h4>
            <p><strong>01</strong> <LocalizedText en="Sparse coverage is a search signal, not proof of a literature gap." ko="낮은 수집 밀도는 추가 탐색 신호이며 연구 공백의 증명이 아닙니다." /></p>
            <p><strong>02</strong> <LocalizedText en="System inference and paper evidence remain visibly separate." ko="시스템 추론과 논문 근거를 명확히 분리합니다." /></p>
            <p><strong>03</strong><span><LocalizedText en={<>Unsupported fields stay <code>insufficient_evidence</code>.</>} ko={<>근거가 부족한 항목은 <code>insufficient_evidence</code>로 유지합니다.</>} /></span></p>
            <p><strong>04</strong> <LocalizedText en={`The ${dominantYear.year || "dominant"} year share is ${dominantYearRatio}% of this corpus; concentration must be read as sampling context.`} ko={`${dominantYear.year || "주요"}년 논문이 이 코퍼스의 ${dominantYearRatio}%입니다. 이 집중도는 표본 수집 맥락으로 해석해야 합니다.`} /></p>
          </article>
        </div>

        <footer className="fieldJournalFooter">
          <span><LocalizedText en="Top authors" ko="주요 저자" /> · {landscape?.top_authors.slice(0, 3).map((item) => `${item.name} (${item.paper_count})`).join(" · ") || "—"}</span>
          <span><LocalizedText en="Top venues" ko="주요 학술지" /> · {landscape?.top_venues.slice(0, 3).map((item) => `${item.name} (${item.paper_count})`).join(" · ") || "—"}</span>
          <Link href="/library?view=browse"><LocalizedText en="Open the scholarly index →" ko="학술 색인 열기 →" /></Link>
        </footer>
      </section>
    </>
  );
}
