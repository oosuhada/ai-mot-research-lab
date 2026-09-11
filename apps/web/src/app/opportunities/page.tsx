import Link from "next/link";

import { LocalizedText } from "@/components/LocalizedText";
import { getResearchOpportunities, type ResearchOpportunity } from "@/lib/api";

function signalText(item: ResearchOpportunity, key: string): string | null {
  const value = item.signals[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function signalNumber(item: ResearchOpportunity, key: string): number | null {
  const value = item.signals[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function opportunityHref(item: ResearchOpportunity): string {
  const source = signalText(item, "source");
  if (source === "research_signal_extracts") {
    const query = [signalText(item, "limitation"), signalText(item, "partner_label")]
      .filter(Boolean)
      .join(" ");
    const params = new URLSearchParams({
      view: "search",
      mode: "vector",
      scope: "abstract",
      q: query || item.title,
    });
    return `/library?${params.toString()}`;
  }
  return `/library?view=browse&axis=${item.axis_slug ?? ""}`;
}

export default async function ResearchOpportunitiesPage() {
  const report = await getResearchOpportunities(12);
  const items = report?.items ?? [];

  return (
    <>
      <header className="intelligenceHero opportunityHero">
        <div>
          <p className="eyebrow"><LocalizedText en="Signal-grounded candidates · research opportunities" ko="신호 기반 후보 · 연구 기회" /></p>
          <h2><LocalizedText en="Where might the next useful MOT study begin?" ko="다음으로 의미 있는 MOT 연구는 어디에서 시작할 수 있을까요?" /></h2>
          <p><LocalizedText en="Automated candidates now prioritize Research Card signal intersections: repeated limitations crossed with methods, datasets, evaluation criteria, or future-research leads." ko="자동 후보는 이제 리서치 카드 신호 교차를 우선합니다. 반복 한계가 방법, 데이터, 평가기준, 후속 연구 리드와 만나는 지점을 보여줍니다." /></p>
        </div>
        <div className="candidateSeal"><strong><LocalizedText en="Candidate" ko="후보" /></strong><span><LocalizedText en="not a confirmed research gap" ko="확정된 연구 공백이 아님" /></span></div>
      </header>

      <section className="opportunityCaveat" aria-label="Interpretation limits">
        <strong><LocalizedText en="Read before using these recommendations" ko="추천을 사용하기 전에 확인하세요" /></strong>
        <ul>{report?.corpus_limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul>
      </section>

      <section className="opportunityGrid">
        {items.map((item, index) => (
          <article className="opportunityCard" key={item.slug}>
            <div className="opportunityNumber">{String(index + 1).padStart(2, "0")}</div>
            <p className="opportunityStatus">{item.evidence_status.replace("_", " ")}</p>
            <h3>{item.title}</h3>
            <p className="opportunityHypothesis">{item.hypothesis}</p>
            <p>{item.rationale}</p>
            {signalText(item, "source") === "research_signal_extracts" ? (
              <div className="opportunitySignalLedger">
                <span><LocalizedText en="Signal intersection" ko="신호 교차" /></span>
                <strong>{signalText(item, "limitation")}</strong>
                <em>{signalText(item, "partner_type")} · {signalText(item, "partner_label")}</em>
                <small>{signalText(item, "limitation_locator") ?? signalText(item, "partner_locator") ?? "source-located card evidence"}</small>
              </div>
            ) : null}
            <dl>
              <div><dt><LocalizedText en="Intersecting papers" ko="교차 논문" /></dt><dd>{item.coverage_count}</dd></div>
              <div><dt><LocalizedText en="Recent papers" ko="최근 논문" /></dt><dd>{signalNumber(item, "recent_intersection_papers") ?? item.adjacent_count}</dd></div>
              <div><dt><LocalizedText en="Candidate method" ko="후보 연구방법" /></dt><dd>{item.recommended_method ?? <LocalizedText en="Broader scoping review" ko="확장 범위 문헌고찰" />}</dd></div>
            </dl>
            <Link href={opportunityHref(item)}><LocalizedText en="Audit the underlying evidence →" ko="기반 근거 점검하기 →" /></Link>
          </article>
        ))}
      </section>

      <section className="subaxisLedger">
        <header><p className="eyebrow"><LocalizedText en="Signal audit" ko="신호 점검" /></p><h3><LocalizedText en="Start from the signal map before choosing a topic." ko="주제를 고르기 전에 신호 지도를 먼저 보세요." /></h3><p><LocalizedText en="Opportunities are now generated from normalized Research Card evidence. Use Signal Lift to inspect the larger limitation, method, data, and evaluation map." ko="연구 기회는 이제 정규화된 리서치 카드 근거에서 생성됩니다. Signal Lift에서 더 큰 한계·방법·데이터·평가기준 지도를 점검하세요." /></p></header>
        <div><Link href="/signal-lift"><span><LocalizedText en="Open Research Signal Lift" ko="연구 신호 리프트 열기" /></span><strong>→</strong></Link></div>
      </section>
    </>
  );
}
