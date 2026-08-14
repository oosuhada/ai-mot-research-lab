import Link from "next/link";

import { getFullTextQueue, getWhatsNew } from "@/lib/api";

export default async function WhatsNewPage() {
  const [brief, queue] = await Promise.all([getWhatsNew(7, 30), getFullTextQueue(8)]);
  const items = brief?.items ?? [];

  return (
    <>
      <header className="intelligenceHero">
        <div>
          <p className="eyebrow">Daily discovery · MOT 새 논문</p>
          <h2>What’s new in AI × Management of Technology?</h2>
          <p>Papers published in the latest window, with database detection time shown separately—ranked as discovery signals, not conclusions.</p>
        </div>
        <div className="intelligenceStamp"><span>Publication window</span><strong>{brief?.window_days ?? 7} days</strong><small>daily publication scan</small></div>
      </header>

      <section className="intelligenceLayout">
        <div className="dailyBriefList">
          <div className="intelligenceSectionTitle"><span>01</span><h3>Daily research brief</h3><small>{items.length} surfaced records</small></div>
          {items.length ? items.map((item, index) => (
            <article className="dailyBriefCard" key={item.paper_id}>
              <div className="dailyBriefIndex">{String(index + 1).padStart(2, "0")}</div>
              <div>
                <p className="dailyBriefMeta">Published {item.publication_date ?? "date unknown"} · detected {item.detected_at.slice(0, 10)} · {item.venue_name ?? "venue unknown"}</p>
                <h3><Link href={`/library/${item.paper_id}`}>{item.title}</Link></h3>
                <p>{item.why_it_matters}</p>
                <div className="tagCloud">
                  <span className="pill">{item.evidence_depth.replace("_", " ")} evidence</span>
                  <span className="pill">relevance {Math.round(item.relevance_score * 100)}%</span>
                  <span className="pill">novelty {Math.round(item.novelty_score * 100)}%</span>
                  {item.topics.slice(0, 3).map((topic) => <span className="pill" key={topic}>{topic}</span>)}
                </div>
              </div>
            </article>
          )) : <div className="emptyIntelligenceState"><strong>No papers published in this window yet.</strong><p>The brief now follows publication date, not the date an older record entered the database.</p></div>}
        </div>

        <aside className="lazyQueuePanel">
          <div className="intelligenceSectionTitle"><span>02</span><h3>Full-text lazy queue</h3></div>
          <p>Open or authorized documents are prioritized without treating a PDF URL as redistribution permission.</p>
          <dl>
            <div><dt>Pending</dt><dd>{queue?.pending ?? 0}</dd></div>
            <div><dt>Processing</dt><dd>{queue?.processing ?? 0}</dd></div>
            <div><dt>Completed</dt><dd>{queue?.completed ?? 0}</dd></div>
            <div><dt>Restricted</dt><dd>{queue?.restricted ?? 0}</dd></div>
          </dl>
          <ol className="lazyQueueList">
            {queue?.items.map((item) => (
              <li key={item.paper_id}>
                <Link href={`/library/${item.paper_id}`}>{item.title}</Link>
                <span>priority {item.priority} · {item.rights_status}</span>
              </li>
            ))}
          </ol>
        </aside>
      </section>
    </>
  );
}
