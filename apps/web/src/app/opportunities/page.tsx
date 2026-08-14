import Link from "next/link";

import { LocalizedTaxonomyText, LocalizedText } from "@/components/LocalizedText";
import { getLandscape, getResearchOpportunities } from "@/lib/api";

export default async function ResearchOpportunitiesPage() {
  const [report, landscape] = await Promise.all([getResearchOpportunities(12), getLandscape()]);
  const items = report?.items ?? [];

  return (
    <>
      <header className="intelligenceHero opportunityHero">
        <div>
          <p className="eyebrow"><LocalizedText en="Coverage-gap candidates · research opportunities" ko="수집 공백 후보 · 연구 기회" /></p>
          <h2><LocalizedText en="Where might the next useful MOT study begin?" ko="다음으로 의미 있는 MOT 연구는 어디에서 시작할 수 있을까요?" /></h2>
          <p><LocalizedText en="Automated candidates built from sparse connections, method imbalance, and adjacent evidence—not claims that a field is empty." ko="연결이 드문 영역, 연구방법 불균형, 인접 근거를 바탕으로 만든 자동 후보이며 특정 분야가 비어 있다는 확정 주장이 아닙니다." /></p>
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
            <dl>
              <div><dt><LocalizedText en="Local coverage" ko="로컬 수집량" /></dt><dd>{item.coverage_count}</dd></div>
              <div><dt><LocalizedText en="Adjacent records" ko="인접 레코드" /></dt><dd>{item.adjacent_count}</dd></div>
              <div><dt><LocalizedText en="Candidate method" ko="후보 연구방법" /></dt><dd>{item.recommended_method ?? <LocalizedText en="Broader scoping review" ko="확장 범위 문헌고찰" />}</dd></div>
            </dl>
            <Link href={`/library?view=browse&axis=${item.axis_slug ?? ""}`}><LocalizedText en="Audit the underlying territory →" ko="근거 연구 영역 점검하기 →" /></Link>
          </article>
        ))}
      </section>

      <section className="subaxisLedger">
        <header><p className="eyebrow"><LocalizedText en="Taxonomy audit" ko="분류체계 점검" /></p><h3><LocalizedText en="AI adoption and business value, decomposed." ko="AI 도입과 비즈니스 가치 영역을 세분화했습니다." /></h3><p><LocalizedText en="Counts are heuristic sub-area assignments and may overlap." ko="수치는 휴리스틱 기반 세부 영역 분류이며 서로 중복될 수 있습니다." /></p></header>
        <div>{landscape?.subaxes.map((subaxis) => <Link href={`/library?view=browse&axis=${subaxis.slug}`} key={subaxis.slug}><span><LocalizedTaxonomyText label={subaxis.display_name} /></span><strong>{subaxis.paper_count}</strong></Link>)}</div>
      </section>
    </>
  );
}
