import Link from "next/link";

import { CitationAtlas } from "@/components/CitationAtlas";
import { FullTextQueueDetails } from "@/components/FullTextQueueDetails";
import { KoreanCoverageDetails } from "@/components/KoreanCoverageDetails";
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

const motProblemEntries = [
  ["mot-technology-strategy-portfolio", "Technology strategy and portfolio", "기술전략·포트폴리오"],
  ["mot-rd-management-investment", "R&D management and investment", "R&D 관리·투자"],
  ["mot-foresight-roadmapping-intelligence", "Foresight, roadmapping and intelligence", "예측·로드맵·인텔리전스"],
  ["mot-organizational-learning-capabilities", "Learning, knowledge and capabilities", "조직학습·지식·역량"],
  ["mot-technology-adoption-diffusion", "Technology adoption and diffusion", "기술 채택·확산"],
  ["mot-entrepreneurship-commercialization", "Entrepreneurship and commercialization", "기술창업·사업화"],
  ["mot-ip-licensing-transfer", "IP, licensing and technology transfer", "IP·라이선싱·기술이전"],
  ["mot-open-innovation-networks-ecosystems", "Open innovation, networks and ecosystems", "개방형 혁신·네트워크·생태계"],
  ["mot-platforms-standards-business-models", "Platforms, standards and business models", "플랫폼·표준·비즈니스모델"],
  ["mot-operations-supply-chain-technology-change", "Operations and supply-chain technology change", "운영·공급망 기술 변화"],
  ["mot-innovation-policy-systems-regulation", "Innovation policy, systems and regulation", "혁신정책·시스템·규제"],
  ["mot-sustainability-responsible-transition", "Sustainability transitions and responsible innovation", "지속가능 전환·책임혁신"],
] as const;

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
          <h2><LocalizedText en="Which management-of-technology questions are worth comparing before narrowing your research direction?" ko="연구 방향을 좁히기 전에 어떤 기술경영 문제들을 같은 기준으로 비교해볼 수 있을까요?" /></h2>
          <p>
            <LocalizedText
              en="Explore MOT problems first, then narrow by technology context, unit of analysis, theory, method, or AI role. Legacy AI research areas remain available as presets rather than default boundaries."
              ko="먼저 MOT 연구 문제를 넓게 탐색한 뒤 기술·산업 맥락, 분석 단위, 이론, 방법, AI 역할로 좁혀보세요. 기존 AI 연구영역은 기본 경계가 아니라 탐색 프리셋으로 유지합니다."
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

      <section className="fieldJournal" aria-label="MOT problem explorer">
        <header className="fieldJournalHeader">
          <p className="eyebrow"><LocalizedText en="MOT problem explorer" ko="MOT 연구 문제 탐색" /></p>
          <h3><LocalizedText en="Start from a research problem, then cross-filter the context." ko="연구 문제에서 시작해 맥락을 교차 필터링하세요." /></h3>
          <p><LocalizedText en="These are operational exploration labels, not an official single taxonomy. A low local count means DB coverage is sparse, not that the scholarly field is empty." ko="아래 분류는 운영용 탐색 라벨이며 공식 단일 분류체계를 뜻하지 않습니다. 로컬 건수가 적다는 것은 DB 수집 범위가 부족하다는 뜻이지 학계에 연구가 없다는 뜻이 아닙니다." /></p>
        </header>
        <div className="tagCloud">
          {motProblemEntries.map(([slug, en, ko]) => (
            <Link className="pill" href={`/library?view=browse&mot_problem=${slug}`} key={slug}>
              <LocalizedText en={en} ko={ko} />
            </Link>
          ))}
        </div>
      </section>

      <nav className="researchThreadRail" aria-label="Research workflow">
          <Link href="/signal-lift"><span><LocalizedText en="Signals" ko="연구 신호" /></span><small><LocalizedText en="find the question" ko="질문 후보 발견" /></small></Link>
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
          <article><span><LocalizedText en="Queue" ko="대기열" /></span><strong>{(coverage?.full_text_queued ?? landscape?.full_text_queued ?? 0).toLocaleString()}</strong><p><LocalizedText en="Lazy enrichment" ko="순차 전문 보강" /></p><div className="queueCardMeta"><small><LocalizedText en="Prioritized by rights and importance" ko="권리와 중요도에 따라 순차 처리" /></small><FullTextQueueDetails details={{ claimable: coverage?.full_text_claimable ?? 0, deferred: coverage?.full_text_deferred ?? 0, processing: coverage?.full_text_processing ?? 0, completed24h: coverage?.full_text_completed_24h ?? 0, boosterEligible: coverage?.full_text_booster_eligible ?? 0, boosterCooldown: coverage?.full_text_booster_cooldown ?? 0, boosterWaiting: coverage?.full_text_booster_waiting_for_attempts ?? 0 }} /></div></article>
          <article><span>KO</span><strong>{(coverage?.translated_ko_abstract ?? coverage?.translated_ko ?? 0).toLocaleString()}</strong><p><LocalizedText en="Korean abstracts" ko="한글 초록 번역" /></p><div className="queueCardMeta"><small><LocalizedText en="Title/abstract localization, separated from full-text evidence" ko="제목·초록 번역과 전문 근거를 분리 표시" /></small><KoreanCoverageDetails details={{ completed: coverage?.translated_ko ?? 0, title: coverage?.translated_ko_title ?? 0, abstract: coverage?.translated_ko_abstract ?? coverage?.translated_ko ?? 0, withFullText: coverage?.translated_ko_with_full_text ?? 0, withoutFullText: coverage?.translated_ko_without_full_text ?? 0, fullTextWithoutKorean: coverage?.full_text_without_translated_ko ?? 0 }} /></div></article>
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
