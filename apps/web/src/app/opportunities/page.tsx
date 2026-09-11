import Link from "next/link";

import { MutationFeedback } from "@/components/MutationFeedback";
import { LocalizedText } from "@/components/LocalizedText";
import { getResearchOpportunities, type ResearchOpportunity } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { createQuestionFromOpportunityAction } from "./actions";

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

export default async function ResearchOpportunitiesPage({ searchParams }: { searchParams: Promise<{ feedback?: string }> }) {
  const params = await searchParams;
  const report = await getResearchOpportunities(12);
  const items = report?.items ?? [];
  const readOnly = isWorkspaceReadOnly();

  return (
    <>
      {!readOnly ? (
        <MutationFeedback
          feedback={params.feedback}
          messages={{
            "invalid-opportunity": { message: "Choose an opportunity before creating a research workspace.", tone: "error" },
            "question-error": { message: "The opportunity could not be converted into a research question.", tone: "error" },
          }}
        />
      ) : null}
      <header className="intelligenceHero opportunityHero">
        <div>
          <p className="eyebrow"><LocalizedText en="Signal-grounded candidates · research opportunities" ko="신호 기반 후보 · 연구 기회" /></p>
          <h2><LocalizedText en="Turn trends into a research-writing workspace." ko="연구 동향을 논문 작성 워크스페이스로 바꾸세요." /></h2>
          <p><LocalizedText en="Use repeated limitations, data/method shifts, and source-located evidence to decide what to read, what to falsify, and what question to write." ko="반복 한계, 데이터·방법 변화, 근거 위치를 바탕으로 무엇을 읽고, 무엇을 반증하고, 어떤 질문으로 논문을 쓸지 정하세요." /></p>
        </div>
        <div className="candidateSeal"><strong><LocalizedText en="Question-ready" ko="질문화 가능" /></strong><span><LocalizedText en="create workspace with evidence" ko="근거 포함 워크스페이스 생성" /></span></div>
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
            <div className="opportunityActions">
              {!readOnly ? (
                <form action={createQuestionFromOpportunityAction}>
                  <input type="hidden" name="slug" value={item.slug} />
                  <button className="button" type="submit"><LocalizedText en="Create research workspace →" ko="연구 워크스페이스 만들기 →" /></button>
                </form>
              ) : (
                <span className="readOnlyPill"><LocalizedText en="Open in personal workspace to create" ko="개인 워크스페이스에서 생성 가능" /></span>
              )}
              <Link href={opportunityHref(item)}><LocalizedText en="Audit evidence →" ko="근거 점검하기 →" /></Link>
            </div>
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
