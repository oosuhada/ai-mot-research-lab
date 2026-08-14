import Link from "next/link";

import { getLandscape, getResearchOpportunities } from "@/lib/api";

export default async function ResearchOpportunitiesPage() {
  const [report, landscape] = await Promise.all([getResearchOpportunities(12), getLandscape()]);
  const items = report?.items ?? [];

  return (
    <>
      <header className="intelligenceHero opportunityHero">
        <div>
          <p className="eyebrow">Coverage-gap candidates · 연구 기회</p>
          <h2>Where might the next useful MOT study begin?</h2>
          <p>Automated candidates built from sparse connections, method imbalance, and adjacent evidence—not claims that a field is empty.</p>
        </div>
        <div className="candidateSeal"><strong>Candidate</strong><span>not a confirmed research gap</span></div>
      </header>

      <section className="opportunityCaveat" aria-label="Interpretation limits">
        <strong>Read before using these recommendations</strong>
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
              <div><dt>Local coverage</dt><dd>{item.coverage_count}</dd></div>
              <div><dt>Adjacent records</dt><dd>{item.adjacent_count}</dd></div>
              <div><dt>Candidate method</dt><dd>{item.recommended_method ?? "Broader scoping review"}</dd></div>
            </dl>
            <Link href={`/library?view=browse&axis=${item.axis_slug ?? ""}`}>Audit the underlying territory →</Link>
          </article>
        ))}
      </section>

      <section className="subaxisLedger">
        <header><p className="eyebrow">Taxonomy audit</p><h3>AI adoption and business value, decomposed.</h3><p>Counts are heuristic sub-area assignments and may overlap.</p></header>
        <div>{landscape?.subaxes.map((subaxis) => <Link href={`/library?view=browse&axis=${subaxis.slug}`} key={subaxis.slug}><span>{subaxis.display_name}</span><strong>{subaxis.paper_count}</strong></Link>)}</div>
      </section>
    </>
  );
}
