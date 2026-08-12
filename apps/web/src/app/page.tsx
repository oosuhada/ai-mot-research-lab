import Link from "next/link";

import { getLandscape, listResearchQuestions } from "@/lib/api";

const fallbackAxes = [
  "AI adoption and business value",
  "Technology and innovation management",
  "AI-enabled organizational change",
  "Industrial AI and smart operations",
  "AI governance and responsible deployment",
  "Agentic systems and enterprise workflows",
];

export default async function HomePage() {
  const landscape = await getLandscape();
  const questions = await listResearchQuestions();
  const axes = landscape?.axes ?? fallbackAxes.map((display_name, index) => ({
    slug: `axis-${index}`,
    display_name,
    paper_count: 0,
  }));
  const maxCount = Math.max(...axes.map((axis) => axis.paper_count), 1);
  const methodologies = landscape?.methodologies ?? [];
  const oaRatio = landscape?.total_papers ? Math.round((landscape.oa_papers / landscape.total_papers) * 100) : 0;

  return (
    <>
      <section className="heroPanel">
        <div className="heroCopy">
          <p className="eyebrow">AI × MOT Research Workbench</p>
          <h2 className="pageTitle">Turn a vague research interest into an evidence-backed question.</h2>
          <p className="pageIntro">
            Search the corpus, collect papers, compare study designs, pressure-test candidate gaps,
            and keep every conclusion attached to inspectable evidence.
          </p>
          <form className="heroSearch" action="/library" method="get">
            <input
              className="input"
              name="q"
              placeholder="Try: AI capability and innovation performance"
              aria-label="Start a literature search"
            />
            <input type="hidden" name="mode" value="hybrid" />
            <button className="button" type="submit">Search the corpus →</button>
          </form>
          <div className="heroActions">
            <Link className="secondaryButton" href="/questions">Create a research question</Link>
            <Link className="secondaryButton" href="/imports">Import my papers</Link>
          </div>
        </div>

        <aside className="heroSignal">
          <span className="heroSignalLabel">Current workspace</span>
          <strong>{landscape?.total_papers ?? 0}</strong>
          <span>papers indexed</span>
          <div className="heroSignalDivider" />
          <div className="heroSignalRow"><span>Open-access signal</span><b>{oaRatio}%</b></div>
          <div className="heroSignalRow"><span>Research questions</span><b>{questions.length}</b></div>
          <div className="heroSignalRow">
            <span>Last ingestion</span>
            <b>{landscape?.last_ingestion_at ? new Date(landscape.last_ingestion_at).toLocaleDateString("en-CA") : "—"}</b>
          </div>
        </aside>
      </section>

      <section className="workflowRail" aria-label="Research workflow">
        <Link href="/library" className="workflowStep"><span>01</span><strong>Discover</strong><small>Search & filter evidence</small></Link>
        <Link href="/questions" className="workflowStep"><span>02</span><strong>Frame</strong><small>Define the research question</small></Link>
        <Link href="/compare" className="workflowStep"><span>03</span><strong>Compare</strong><small>Inspect study design</small></Link>
        <Link href="/gap-canvas" className="workflowStep"><span>04</span><strong>Challenge</strong><small>Falsify candidate gaps</small></Link>
        <Link href="/chat" className="workflowStep"><span>05</span><strong>Synthesize</strong><small>Ask with citations</small></Link>
      </section>

      <section className="grid" aria-label="Corpus overview">
        <article className="card span4">
          <span className="metricLabel">Corpus</span>
          <div className="metricValue">{landscape?.total_papers ?? 0}</div>
          <p className="metricHelp">Canonical research records in the live workspace.</p>
        </article>

        <article className="card span4">
          <span className="metricLabel">Research coverage</span>
          <div className="metricValue">6</div>
          <p className="metricHelp">AI × MOT axes tracked with explicit taxonomy rules.</p>
        </article>

        <article className="card span4">
          <span className="metricLabel">Open-access signal</span>
          <div className="metricValue">{oaRatio}%</div>
          <p className="metricHelp">OA status is metadata, not automatic permission to redistribute a PDF.</p>
        </article>

        <article className="card span8 emphasisCard">
          <div className="sectionHeadingRow">
            <div><p className="cardKicker">Coverage map</p><h3 className="sectionTitle">Corpus by research axis</h3></div>
            <Link className="textLink" href="/library">Explore papers →</Link>
          </div>
          <div className="axisList">
            {axes.map((axis) => (
              <div className="axisRow" key={axis.slug}>
                <div className="axisName">
                  <span>{axis.display_name}</span>
                  <div className="barTrack" aria-hidden="true">
                    <div
                      className="barFill"
                      style={{ width: `${Math.max((axis.paper_count / maxCount) * 100, 0)}%` }}
                    />
                  </div>
                </div>
                <span className="axisCount">{axis.paper_count}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card span4 decisionCard">
          <p className="cardKicker">Research discipline</p>
          <h3 className="sectionTitle">What the system will not pretend to know</h3>
          <div className="decisionRule"><span>01</span><p>A sparse cluster is not automatically a literature gap.</p></div>
          <div className="decisionRule"><span>02</span><p>System inference is never presented as a paper claim.</p></div>
          <div className="decisionRule"><span>03</span><p>Unsupported fields remain <code>insufficient_evidence</code>.</p></div>
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Methodology heuristics</h3>
          <p className="metricHelp">System heuristic only, not author-reported methodology.</p>
          <div className="axisList" style={{ marginTop: 14 }}>
            {methodologies.slice(0, 8).map((method) => (
              <div className="axisRow" key={method.slug}>
                <span>{method.display_name}</span><span className="axisCount">{method.paper_count}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Research signals</h3>
          <div className="detailList">
            <div><dt>Top authors</dt><dd>{landscape?.top_authors.slice(0, 4).map((item) => `${item.name} (${item.paper_count})`).join(", ") || "—"}</dd></div>
            <div><dt>Top venues</dt><dd>{landscape?.top_venues.slice(0, 4).map((item) => `${item.name} (${item.paper_count})`).join(", ") || "—"}</dd></div>
            <div><dt>Active questions</dt><dd>{questions.length ? questions.slice(0, 3).map((item) => item.title).join(" · ") : "Create your first research question"}</dd></div>
          </div>
        </article>

        <article className="card span12">
          <div className="sectionHeadingRow">
            <h3 className="sectionTitle">Publication-year coverage</h3>
            <span className="muted">Current local corpus, not a field-level trend claim</span>
          </div>
          <div className="yearStrip">
            {(landscape?.years ?? []).map((year) => <span className="pill" key={year.year}>{year.year}: {year.paper_count}</span>)}
          </div>
        </article>
      </section>
    </>
  );
}
