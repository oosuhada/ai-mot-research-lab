import { createComparisonFromTopic } from "./actions";
import { getComparisonSet } from "@/lib/api";

const fields = [
  ["research_question", "Research question"],
  ["theoretical_lens", "Theoretical lens"],
  ["unit_of_analysis", "Unit of analysis"],
  ["context_industry_country", "Context / industry / country"],
  ["dataset_and_sample", "Dataset and sample"],
  ["methodology", "Methodology"],
  ["variables_or_constructs", "Variables or constructs"],
  ["findings", "Findings"],
  ["limitations", "Limitations"],
  ["claimed_contribution", "Claimed contribution"],
  ["future_research", "Future research"],
] as const;

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ id?: string }>;
}) {
  const params = await searchParams;
  const comparison = params.id ? await getComparisonSet(params.id) : null;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Compare Papers</p>
          <h2 className="pageTitle">Compare study design, not just summaries.</h2>
          <p className="pageIntro">
            This baseline only marks a cell supported when the available abstract contains traceable evidence.
            Missing full-text evidence remains visible instead of being filled by inference.
          </p>
        </div>
      </header>

      {!comparison ? (
        <section className="card">
          <h3 className="sectionTitle">Create a saved comparison set</h3>
          <p className="pageIntro compactIntro">
            Enter a topic to compare the top three hybrid-retrieved papers. The API also supports explicit paper IDs
            for programmatic selection.
          </p>
          <form className="searchBar searchBarWrap" action={createComparisonFromTopic}>
            <input
              className="input"
              name="query"
              required
              minLength={2}
              placeholder="e.g. AI capability and firm performance"
            />
            <button className="button" type="submit">Create comparison</button>
          </form>
        </section>
      ) : (
        <section className="card comparisonCard">
          <div className="resultSummary">
            <strong>{comparison.name}</strong>
            <span className="pill">saved set</span>
            <span className="muted">{comparison.papers.length} papers · {comparison.cells.length} evidence cells</span>
          </div>
          <div className="tableScroller">
            <table className="comparisonTable">
              <thead>
                <tr>
                  <th>Field</th>
                  {comparison.papers.map((paper) => (
                    <th key={paper.id}>
                      <span className="tablePaperYear">{paper.publication_year ?? "—"}</span>
                      {paper.title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {fields.map(([fieldName, label]) => (
                  <tr key={fieldName}>
                    <th>{label}</th>
                    {comparison.papers.map((paper) => {
                      const cell = comparison.cells.find(
                        (candidate) => candidate.paper_id === paper.id && candidate.field_name === fieldName,
                      );
                      return (
                        <td key={paper.id}>
                          <span className={`statusBadge status-${cell?.support_status ?? "insufficient_evidence"}`}>
                            {cell?.support_status ?? "insufficient_evidence"}
                          </span>
                          <p>{cell?.value_text ?? "No extracted value."}</p>
                          {cell?.evidence.map((evidence) => (
                            <a
                              className="evidenceLink"
                              key={`${cell.id}-${evidence.paper_id}`}
                              href={evidence.primary_url ?? (evidence.doi ? `https://doi.org/${evidence.doi}` : "#")}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Evidence: {evidence.source_locator ?? "paper"} ↗
                            </a>
                          ))}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
