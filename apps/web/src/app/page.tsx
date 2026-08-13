import Link from "next/link";

import { getLandscape, listResearchQuestions } from "@/lib/api";
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
  const landscape = await getLandscape();
  const questions = await listResearchQuestions();
  const readOnly = isWorkspaceReadOnly();
  const axes = landscape?.axes ?? fallbackAxes.map((display_name, index) => ({
    slug: `axis-${index}`,
    display_name,
    paper_count: 0,
  }));
  const maxCount = Math.max(...axes.map((axis) => axis.paper_count), 1);
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
            <Link className="secondaryButton" href="/questions">{readOnly ? "Explore sample research questions" : "Create a research question"}</Link>
            {!readOnly ? <Link className="secondaryButton" href="/imports">Import my papers</Link> : <Link className="secondaryButton" href="/compare">Inspect an evidence comparison</Link>}
          </div>
        </div>

        <aside className="heroSignal">
          <span className="heroSignalLabel">{readOnly ? "Public demo · read-only" : "Current workspace"}</span>
          <strong>{landscape?.total_papers ?? 0}</strong>
          <span>papers indexed</span>
          <div className="heroSignalDivider" />
          <div className="heroSignalRow"><span>Research questions</span><b>{questions.length}</b></div>
          <div className="heroSignalRow"><span>Gap handling</span><b>Hypothesis first</b></div>
          <div className="heroSignalRow"><span>Unsupported fields</span><b>Stay explicit</b></div>
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
        <article className="corpusHealth span12">
          <div className="sectionHeadingRow corpusHealthHeading">
            <div><p className="cardKicker">Corpus health</p><h3 className="sectionTitle">Know the dataset before reading the trend.</h3></div>
            <span className="muted">Coverage diagnostics describe this corpus, not the whole field.</span>
          </div>
          <div className="corpusHealthGrid">
            <div><span>Coverage period</span><strong>{coverageStart && coverageEnd ? `${coverageStart}–${coverageEnd}` : "—"}</strong><small>Publication-year metadata</small></div>
            <div><span>Primary source</span><strong>OpenAlex</strong><small>Plus explicit user imports when present</small></div>
            <div><span>Last updated</span><strong>{landscape?.last_ingestion_at ? new Date(landscape.last_ingestion_at).toLocaleDateString("en-CA") : "—"}</strong><small>Last completed ingestion</small></div>
            <div><span>Missing abstracts</span><strong>{missingAbstracts}</strong><small>{abstractRatio}% abstract coverage</small></div>
            <div><span>Full-text evidence</span><strong>{fullTextRatio}%</strong><small>{landscape?.full_text_papers ?? 0} records with chunks</small></div>
            <div className={dominantYearRatio >= 40 ? "corpusHealthWarning" : ""}><span>Year imbalance</span><strong>{dominantYear.year ? `${dominantYear.year} · ${dominantYearRatio}%` : "—"}</strong><small>{dominantYearRatio >= 40 ? "Sampling concentration requires caution" : "No single year dominates the corpus"}</small></div>
          </div>
          <div className="corpusHealthFoot"><span>OA metadata: {oaRatio}%</span><span>Research axes: 6</span><span>Methodology labels: system-inferred, not author-reported</span></div>
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
            {years.map((year) => <span className="pill" key={year.year}>{year.year}: {year.paper_count}</span>)}
          </div>
        </article>
      </section>
    </>
  );
}
