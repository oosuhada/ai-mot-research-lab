import Link from "next/link";

import { LocalizedText } from "@/components/LocalizedText";
import {
  getResearchSignalLift,
  type NormalizedResearchSignal,
  type ResearchCardEvidenceSignal,
  type ResearchSignalItem,
} from "@/lib/api";

function libraryHref(signal: ResearchSignalItem) {
  const params = new URLSearchParams({
    view: "search",
    mode: "vector",
    scope: signal.signal_type === "repeated_limitation" ? "abstract" : "metadata",
    q: signal.query_hint ?? signal.label,
  });
  return `/library?${params.toString()}`;
}

function SignalCard({ item, index }: { item: ResearchSignalItem; index: number }) {
  return (
    <article className="signalLiftCard">
      <div className="signalLiftCardTop">
        <span>{String(index + 1).padStart(2, "0")}</span>
        <strong>{item.evidence_depth}</strong>
      </div>
      <h4>{item.label}</h4>
      <p>{item.description}</p>
      <dl>
        <div><dt><LocalizedText en="Papers" ko="논문" /></dt><dd>{item.paper_count.toLocaleString()}</dd></div>
        <div><dt><LocalizedText en="Recent" ko="최근" /></dt><dd>{item.recent_count.toLocaleString()}</dd></div>
        <div><dt><LocalizedText en="Full text" ko="전문" /></dt><dd>{item.full_text_count.toLocaleString()}</dd></div>
        <div><dt><LocalizedText en="Signal" ko="신호" /></dt><dd>{item.growth_score.toFixed(3)}</dd></div>
      </dl>
      {item.caveat ? <small>{item.caveat}</small> : null}
      <Link className="textLink" href={libraryHref(item)}>
        <LocalizedText en="Audit evidence →" ko="근거 점검하기 →" />
      </Link>
    </article>
  );
}

function SignalSection({
  eyebrow,
  title,
  body,
  items,
}: {
  eyebrow: { en: string; ko: string };
  title: { en: string; ko: string };
  body: { en: string; ko: string };
  items: ResearchSignalItem[];
}) {
  return (
    <section className="signalLiftSection">
      <header>
        <p className="eyebrow"><LocalizedText en={eyebrow.en} ko={eyebrow.ko} /></p>
        <h3><LocalizedText en={title.en} ko={title.ko} /></h3>
        <p><LocalizedText en={body.en} ko={body.ko} /></p>
      </header>
      <div className="signalLiftGrid">
        {items.length ? items.map((item, index) => <SignalCard item={item} index={index} key={`${item.signal_type}-${item.label}`} />) : (
          <div className="emptyState"><LocalizedText en="No signal rows are available yet." ko="아직 표시할 신호가 없습니다." /></div>
        )}
      </div>
    </section>
  );
}

function CardEvidenceSection({ items }: { items: ResearchCardEvidenceSignal[] }) {
  return (
    <section className="signalLiftSection cardEvidenceSection">
      <header>
        <p className="eyebrow"><LocalizedText en="02 · card evidence layer" ko="02 · 카드 근거 계층" /></p>
        <h3><LocalizedText en="What do the first Research Cards actually say?" ko="초기 리서치 카드가 실제로 무엇을 말하나요?" /></h3>
        <p>
          <LocalizedText
            en="These are machine-extracted, source-located leads from persisted Research Cards. Treat them as review targets, not final synthesis."
            ko="저장된 리서치 카드에서 추출한 source-located 리드입니다. 최종 종합이 아니라 검토해야 할 후보로 보세요."
          />
        </p>
      </header>
      <div className="cardEvidenceList">
        {items.length ? items.map((item) => (
          <article key={`${item.field_name}-${item.paper_id}-${item.source_locator ?? "source"}`}>
            <div>
              <span>{item.label}</span>
              <strong>{item.publication_year ?? "—"}</strong>
            </div>
            <p>{item.value_text}</p>
            <Link className="textLink" href={`/library/${item.paper_id}`}>
              <LocalizedText en={`Inspect ${item.source_locator ?? "source"} →`} ko={`${item.source_locator ?? "근거 위치"} 점검하기 →`} />
            </Link>
            <small>{item.paper_title}</small>
          </article>
        )) : <div className="emptyState"><LocalizedText en="Research Card evidence will appear after the backfill worker runs." ko="Research Card backfill worker가 실행되면 카드 근거가 표시됩니다." /></div>}
      </div>
    </section>
  );
}

function normalizedHref(signal: NormalizedResearchSignal) {
  const params = new URLSearchParams({
    view: "search",
    mode: "vector",
    scope: "abstract",
    q: signal.label,
  });
  return `/library?${params.toString()}`;
}

function NormalizedSignalSection({ items }: { items: NormalizedResearchSignal[] }) {
  return (
    <section className="normalizedSignalSection">
      <header>
        <p className="eyebrow"><LocalizedText en="Normalized signal map" ko="정규화 신호 지도" /></p>
        <h3><LocalizedText en="Which evidence patterns repeat across cards?" ko="카드 사이에서 어떤 근거 패턴이 반복되나요?" /></h3>
        <p>
          <LocalizedText
            en="These rows come from stored Research Cards, not only topic proxies. Use them to move from examples toward repeated limitation, data, method, and evaluation patterns."
            ko="이 항목은 topic proxy만이 아니라 저장된 리서치 카드에서 나온 정규화 신호입니다. 예시 문장에서 반복 한계·데이터·방법·평가 패턴으로 넘어가기 위한 계층입니다."
          />
        </p>
      </header>
      <div className="normalizedSignalGrid">
        {items.length ? items.map((item) => (
          <article className="normalizedSignalCard" key={`${item.signal_type}-${item.normalized_label}`}>
            <div>
              <span>{item.signal_type.replace("_", " ")}</span>
              <strong>{item.label}</strong>
            </div>
            <dl>
              <div><dt><LocalizedText en="Papers" ko="논문" /></dt><dd>{item.paper_count.toLocaleString()}</dd></div>
              <div><dt><LocalizedText en="Extracts" ko="추출" /></dt><dd>{item.extract_count.toLocaleString()}</dd></div>
              <div><dt><LocalizedText en="Recent" ko="최근" /></dt><dd>{item.recent_count.toLocaleString()}</dd></div>
              <div><dt><LocalizedText en="Reviewed" ko="검토" /></dt><dd>{item.reviewed_count.toLocaleString()}</dd></div>
            </dl>
            {item.example_evidence_text ? <p>{item.example_evidence_text}</p> : null}
            <footer>
              <small>{item.example_source_locator ?? <LocalizedText en="source locator pending" ko="근거 위치 대기" />}</small>
              <Link className="textLink" href={item.example_paper_id ? `/library/${item.example_paper_id}` : normalizedHref(item)}>
                <LocalizedText en="Inspect example →" ko="예시 점검하기 →" />
              </Link>
            </footer>
          </article>
        )) : (
          <div className="emptyState"><LocalizedText en="Normalized signal extracts are still being generated." ko="정규화 신호 추출이 아직 생성 중입니다." /></div>
        )}
      </div>
    </section>
  );
}

export default async function SignalLiftPage() {
  const report = await getResearchSignalLift(8);

  if (!report) {
    return (
      <section className="emptyState">
        <h2><LocalizedText en="Signal Lift is temporarily unavailable." ko="연구 신호 화면을 일시적으로 불러올 수 없습니다." /></h2>
        <p><LocalizedText en="The corpus remains available through Library and Evidence Chat." ko="코퍼스는 논문 라이브러리와 근거 채팅에서 계속 사용할 수 있습니다." /></p>
      </section>
    );
  }

  return (
    <>
      <header className="intelligenceHero signalLiftHero">
        <div>
          <p className="eyebrow"><LocalizedText en="Research Signal Lift" ko="연구 신호 리프트" /></p>
          <h2><LocalizedText en="Find questions, not just papers." ko="논문이 아니라 질문을 찾으세요." /></h2>
          <p>
            <LocalizedText
              en="This page turns the growing corpus into conservative research signals: repeated limitations, method/data shifts, emerging clusters, and frontier candidates."
              ko="이 화면은 커지는 코퍼스를 반복 한계, 방법·데이터 변화, 부상 클러스터, 프론티어 후보라는 보수적인 연구 신호로 변환합니다."
            />
          </p>
        </div>
        <div className="candidateSeal">
          <strong>{report.recent_window}</strong>
          <span><LocalizedText en="recent signal window" ko="최근 신호 구간" /></span>
        </div>
      </header>

      <section className="signalLiftReadiness" aria-label="Signal readiness">
        <article><span><LocalizedText en="Corpus" ko="코퍼스" /></span><strong>{report.total_records.toLocaleString()}</strong><small><LocalizedText en="records" ko="레코드" /></small></article>
        <article><span><LocalizedText en="Full text" ko="전문" /></span><strong>{report.full_text_ready.toLocaleString()}</strong><small><LocalizedText en="evidence-ready" ko="근거 사용 가능" /></small></article>
        <article><span><LocalizedText en="Research Cards" ko="리서치 카드" /></span><strong>{report.research_cards_ready.toLocaleString()}</strong><small><LocalizedText en={`${report.reviewed_research_cards.toLocaleString()} reviewed`} ko={`${report.reviewed_research_cards.toLocaleString()}개 검토 완료`} /></small></article>
        <article><span><LocalizedText en="Claims" ko="근거 주장" /></span><strong>{report.evidence_claims.toLocaleString()}</strong><small><LocalizedText en="linked claims" ko="연결된 주장" /></small></article>
      </section>

      <section className="opportunityCaveat" aria-label="Signal interpretation rules">
        <strong><LocalizedText en="Use as a research compass, not as proof" ko="증명이 아니라 연구 나침반으로 사용하세요" /></strong>
        <ul>{report.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}</ul>
      </section>

      <SignalSection
        eyebrow={{ en: "01 · repeated limitations", ko: "01 · 반복 한계" }}
        title={{ en: "Where do papers keep exposing the same weak point?", ko: "어디에서 같은 약점이 반복해서 드러나나요?" }}
        body={{ en: "These rows are text-proxy starting points. Use them to falsify apparent gaps with broader searches.", ko: "이 항목은 텍스트 프록시 기반 시작점입니다. 보이는 공백을 확정하지 말고 더 넓은 검색으로 반증하세요." }}
        items={report.repeated_limitations}
      />

      <CardEvidenceSection items={report.card_evidence_signals} />

      <NormalizedSignalSection items={report.normalized_signals} />

      <SignalSection
        eyebrow={{ en: "03 · newly testable clusters", ko: "03 · 새로 검증 가능한 클러스터" }}
        title={{ en: "Which questions are gaining local research mass?", ko: "어떤 질문이 로컬 코퍼스에서 밀도를 얻고 있나요?" }}
        body={{ en: "Growth signals point to clusters where a question may have become newly measurable or governable.", ko: "성장 신호는 어떤 질문이 새롭게 측정·검증·거버넌스 가능해졌는지를 찾기 위한 단서입니다." }}
        items={report.emerging_questions}
      />

      <SignalSection
        eyebrow={{ en: "04 · data and evaluation shifts", ko: "04 · 데이터와 평가 기준 변화" }}
        title={{ en: "Which methods or data channels are changing feasibility?", ko: "어떤 방법이나 데이터 통로가 연구 가능성을 바꾸고 있나요?" }}
        body={{ en: "Method/data signals are where tool change can become a research question instead of a writing shortcut.", ko: "방법·데이터 신호는 도구 변화가 글쓰기 지름길이 아니라 연구 질문이 되는 지점입니다." }}
        items={report.method_data_signals}
      />

      <SignalSection
        eyebrow={{ en: "05 · frontier candidates", ko: "05 · 프론티어 후보" }}
        title={{ en: "Who should be inspected as a frontier node?", ko: "누구를 프론티어 노드 후보로 점검해야 하나요?" }}
        body={{ en: "These are recent-activity candidates, not authority rankings. Inspect their cluster before following them.", ko: "권위 순위가 아니라 최근 활동 후보입니다. 따라가기 전에 그 논문 클러스터를 먼저 점검하세요." }}
        items={report.frontier_researchers}
      />

      <section className="signalLiftNext">
        <header>
          <p className="eyebrow"><LocalizedText en="Next implementation layer" ko="다음 구현 계층" /></p>
          <h3><LocalizedText en="Turn signals into Research Cards and falsification plans." ko="신호를 리서치 카드와 반증 계획으로 바꾸세요." /></h3>
        </header>
        <ol>{report.next_actions.map((action) => <li key={action}>{action}</li>)}</ol>
        <Link className="button" href="/questions"><LocalizedText en="Build a question from these signals →" ko="이 신호로 연구 질문 만들기 →" /></Link>
      </section>
    </>
  );
}
