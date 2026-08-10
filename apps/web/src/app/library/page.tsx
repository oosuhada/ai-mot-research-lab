import { searchPapers } from "@/lib/api";

type LibrarySearchParams = {
  q?: string;
  mode?: string;
};

function normalizeMode(value: string | undefined): "lexical" | "vector" | "hybrid" {
  if (value === "lexical" || value === "vector") {
    return value;
  }
  return "hybrid";
}

function evidenceUrl(primaryUrl: string | null, doi: string | null): string | null {
  if (primaryUrl) {
    return primaryUrl;
  }
  if (doi) {
    return `https://doi.org/${doi}`;
  }
  return null;
}

export default async function LibraryPage({
  searchParams,
}: {
  searchParams: Promise<LibrarySearchParams>;
}) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  const mode = normalizeMode(params.mode);
  const result = query ? await searchPapers(query, mode) : null;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Paper Library</p>
          <h2 className="pageTitle">Search the corpus with two retrieval lenses.</h2>
          <p className="pageIntro">
            Lexical and semantic ranks stay visible so the hybrid result never hides why a paper surfaced.
            DOI and source links remain attached to the evidence trail.
          </p>
        </div>
      </header>

      <section className="card">
        <form className="searchBar searchBarWrap" action="/library" method="get">
          <input
            className="input"
            name="q"
            defaultValue={query}
            placeholder="e.g. AI adoption firm performance"
            aria-label="Search papers"
          />
          <select className="select" name="mode" defaultValue={mode} aria-label="Retrieval mode">
            <option value="hybrid">Hybrid</option>
            <option value="lexical">Lexical</option>
            <option value="vector">Vector</option>
          </select>
          <button className="button" type="submit">
            Search
          </button>
        </form>

        {!query ? (
          <div className="emptyState" style={{ marginTop: 18 }}>
            Search the local corpus. Hybrid mode combines PostgreSQL full-text retrieval and pgvector
            semantic retrieval with reciprocal rank fusion.
          </div>
        ) : result ? (
          <div className="resultStack">
            <div className="resultSummary">
              <strong>{result.total} ranked papers</strong>
              <span className="pill">mode: {result.mode}</span>
              <span className="muted">Query: “{result.query}”</span>
            </div>
            {result.items.map((paper) => {
              const sourceUrl = evidenceUrl(paper.primary_url, paper.doi);
              return (
                <article className="paperResult" key={paper.id}>
                  <div className="paperMeta">
                    <span>{paper.publication_year ?? "Year unknown"}</span>
                    <span>{paper.work_type ?? "work"}</span>
                    <span>{paper.is_oa ? `OA${paper.oa_status ? ` · ${paper.oa_status}` : ""}` : "Closed/unknown OA"}</span>
                  </div>
                  <h3>{paper.title}</h3>
                  {paper.abstract ? <p>{paper.abstract.slice(0, 420)}{paper.abstract.length > 420 ? "…" : ""}</p> : null}
                  <div className="rankRow">
                    <span className="pill">Lexical #{paper.lexical_rank ?? "—"}</span>
                    <span className="pill">Vector #{paper.semantic_rank ?? "—"}</span>
                    <span className="pill">RRF {paper.fused_score.toFixed(4)}</span>
                    {paper.doi ? <span className="muted">DOI {paper.doi}</span> : null}
                  </div>
                  {sourceUrl ? (
                    <a className="textLink" href={sourceUrl} target="_blank" rel="noreferrer">
                      Open paper source ↗
                    </a>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <div className="emptyState" style={{ marginTop: 18 }}>
            The API could not return results. Confirm the local database and API service are running.
          </div>
        )}
      </section>
    </>
  );
}
