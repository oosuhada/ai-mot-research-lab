import Link from "next/link";

import { LocalizedText } from "@/components/LocalizedText";
import { getFullTextQueue, getWhatsNew } from "@/lib/api";

export default async function WhatsNewPage() {
  const [brief, queue] = await Promise.all([getWhatsNew(7, 30), getFullTextQueue(8)]);
  const items = brief?.items ?? [];

  return (
    <>
      <header className="intelligenceHero">
        <div>
          <p className="eyebrow"><LocalizedText en="Daily discovery · new MOT papers" ko="일일 탐지 · 새로운 MOT 논문" /></p>
          <h2><LocalizedText en="What’s new in AI × Management of Technology?" ko="AI × 기술경영 분야의 새로운 연구는 무엇일까요?" /></h2>
          <p><LocalizedText en="Papers published in the latest window, with database detection time shown separately—ranked as discovery signals, not conclusions." ko="최근 기간에 출판된 논문을 보여주며 DB 탐지 시점은 별도로 표시합니다. 순위는 탐색 신호이지 결론이 아닙니다." /></p>
        </div>
        <div className="intelligenceStamp"><span><LocalizedText en="Publication window" ko="출판 기간" /></span><strong>{brief?.window_days ?? 7} <LocalizedText en="days" ko="일" /></strong><small><LocalizedText en="daily publication scan" ko="일일 출판 논문 탐지" /></small></div>
      </header>

      <section className="intelligenceLayout">
        <div className="dailyBriefList">
          <div className="intelligenceSectionTitle"><span>01</span><h3><LocalizedText en="Daily research brief" ko="일일 연구 브리프" /></h3><small><LocalizedText en={`${items.length} surfaced records`} ko={`${items.length}개 탐지 레코드`} /></small></div>
          {items.length ? items.map((item, index) => (
            <article className="dailyBriefCard" key={item.paper_id}>
              <div className="dailyBriefIndex">{String(index + 1).padStart(2, "0")}</div>
              <div>
                <p className="dailyBriefMeta"><LocalizedText en="Published" ko="출판" /> {item.publication_date ?? "—"} · <LocalizedText en="detected" ko="탐지" /> {item.detected_at.slice(0, 10)} · {item.venue_name ?? <LocalizedText en="venue unknown" ko="학술지 정보 없음" />}</p>
                <h3><Link href={`/library/${item.paper_id}`}>{item.title}</Link></h3>
                <p>{item.why_it_matters}</p>
                <div className="tagCloud">
                  <span className="pill">{item.evidence_depth.replace("_", " ")} <LocalizedText en="evidence" ko="근거" /></span>
                  <span className="pill"><LocalizedText en="relevance" ko="관련성" /> {Math.round(item.relevance_score * 100)}%</span>
                  <span className="pill"><LocalizedText en="novelty" ko="신규성" /> {Math.round(item.novelty_score * 100)}%</span>
                  {item.topics.slice(0, 3).map((topic) => <span className="pill" key={topic}>{topic}</span>)}
                </div>
              </div>
            </article>
          )) : <div className="emptyIntelligenceState"><strong><LocalizedText en="No papers published in this window yet." ko="이 기간에 새로 출판된 논문이 아직 없습니다." /></strong><p><LocalizedText en="The brief follows publication date, not the date an older record entered the database." ko="이 브리프는 오래된 논문의 DB 유입일이 아니라 실제 출판일을 기준으로 합니다." /></p></div>}
        </div>

        <aside className="lazyQueuePanel">
          <div className="intelligenceSectionTitle"><span>02</span><h3><LocalizedText en="Full-text lazy queue" ko="논문 전문 순차 보강 대기열" /></h3></div>
          <p><LocalizedText en="Open or authorized documents are prioritized without treating a PDF URL as redistribution permission." ko="공개되었거나 권한이 확인된 문서를 우선 처리하며, PDF URL이 있다는 이유만으로 재배포 권한이 있다고 간주하지 않습니다." /></p>
          <dl>
            <div><dt><LocalizedText en="Pending" ko="대기" /></dt><dd>{queue?.pending ?? 0}</dd></div>
            <div><dt><LocalizedText en="Processing" ko="처리 중" /></dt><dd>{queue?.processing ?? 0}</dd></div>
            <div><dt><LocalizedText en="Completed" ko="완료" /></dt><dd>{queue?.completed ?? 0}</dd></div>
            <div><dt><LocalizedText en="Restricted" ko="접근 제한" /></dt><dd>{queue?.restricted ?? 0}</dd></div>
          </dl>
          <ol className="lazyQueueList">
            {queue?.items.map((item) => (
              <li key={item.paper_id}>
                <Link href={`/library/${item.paper_id}`}>{item.title}</Link>
                <span><LocalizedText en="priority" ko="우선순위" /> {item.priority} · {item.rights_status}</span>
              </li>
            ))}
          </ol>
        </aside>
      </section>
    </>
  );
}
