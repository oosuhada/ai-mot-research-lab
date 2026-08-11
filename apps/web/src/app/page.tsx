import { getLandscape } from "@/lib/api";

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
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Research Landscape</p>
          <h2 className="pageTitle">Build a research map before asking for an answer.</h2>
          <p className="pageIntro">
            The corpus stays narrow: AI × technology management. Trends, comparisons, and candidate gaps
            are derived from papers whose provenance can be inspected later.
          </p>
        </div>
      </header>

      <section className="grid" aria-label="Corpus overview">
        <article className="card span4">
          <span className="metricLabel">Papers in local corpus</span>
          <div className="metricValue">{landscape?.total_papers ?? 0}</div>
          <p className="metricHelp">OpenAlex-first metadata; private full text is never committed.</p>
        </article>

        <article className="card span4">
          <span className="metricLabel">Research axes</span>
          <div className="metricValue">6</div>
          <p className="metricHelp">Versioned inclusion rules keep retrieval aligned with research intent.</p>
        </article>

        <article className="card span4">
          <span className="metricLabel">Open-access metadata signal</span>
          <div className="metricValue">{oaRatio}%</div>
          <p className="metricHelp">OA status is metadata, not automatic permission to redistribute a PDF.</p>
        </article>

        <article className="card span8">
          <h3 className="sectionTitle">Corpus by research axis</h3>
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

        <article className="card span4">
          <h3 className="sectionTitle">Interpretation rule</h3>
          <div className="callout">
            <strong>No “gap found” badge.</strong>
            A sparse cluster is only a candidate signal. Context, method, theory, and contradictory evidence
            must be inspected before it becomes a research question.
          </div>
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Methodology heuristics</h3>
          <p className="metricHelp">System heuristic only, not author-reported methodology.</p>
          <div className="axisList" style={{ marginTop: 14 }}>
            {methodologies.slice(0, 8).map((method) => (
              <div className="axisRow" key={method.slug}><span>{method.display_name}</span><span className="axisCount">{method.paper_count}</span></div>
            ))}
          </div>
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Corpus leaders</h3>
          <div className="detailList">
            <div><dt>Top authors</dt><dd>{landscape?.top_authors.slice(0, 4).map((item) => `${item.name} (${item.paper_count})`).join(", ") || "—"}</dd></div>
            <div><dt>Top venues</dt><dd>{landscape?.top_venues.slice(0, 4).map((item) => `${item.name} (${item.paper_count})`).join(", ") || "—"}</dd></div>
            <div><dt>Last ingestion</dt><dd>{landscape?.last_ingestion_at ? new Date(landscape.last_ingestion_at).toLocaleString("en-CA") : "No completed run"}</dd></div>
          </div>
        </article>

        <article className="card span12">
          <h3 className="sectionTitle">Publication-year coverage</h3>
          <div className="yearStrip">
            {(landscape?.years ?? []).map((year) => <span className="pill" key={year.year}>{year.year}: {year.paper_count}</span>)}
          </div>
          <p className="metricHelp" style={{ marginTop: 12 }}>Sparse years or axes describe current local corpus coverage; they are not evidence of a field-level research gap.</p>
        </article>
      </section>
    </>
  );
}

