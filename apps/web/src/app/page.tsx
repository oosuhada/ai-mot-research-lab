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
          <span className="metricLabel">Evidence policy</span>
          <div className="metricValue">Trace</div>
          <p className="metricHelp">Supported claims require paper or chunk links; otherwise they stay uncertain.</p>
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
      </section>
    </>
  );
}

