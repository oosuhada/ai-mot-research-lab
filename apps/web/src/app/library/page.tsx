import Link from "next/link";

import { listSavedSearches, searchPapers, type SearchOptions } from "@/lib/api";

import { saveSearchAction } from "./actions";

type LibrarySearchParams = SearchOptions & { q?: string; mode?: string };

function normalizeMode(value: string | undefined): "lexical" | "vector" | "hybrid" {
  return value === "lexical" || value === "vector" ? value : "hybrid";
}

function option<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

export default async function LibraryPage({ searchParams }: { searchParams: Promise<LibrarySearchParams> }) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  const mode = normalizeMode(params.mode);
  const scope = option(params.scope, ["metadata", "abstract", "full_text", "all"] as const, "all");
  const sort = option(
    params.sort,
    ["relevance", "newest", "citation_count", "reading_priority"] as const,
    "relevance",
  );
  const semanticProvider = option(
    params.semantic_provider,
    ["auto", "local_hash", "fastembed"] as const,
    "auto",
  );
  const rerank = option(params.rerank, ["none", "fastembed"] as const, "none");
  const options: SearchOptions = { ...params, scope, sort, semantic_provider: semanticProvider, rerank };
  const result = query ? await searchPapers(query, mode, options) : null;
  const savedSearches = await listSavedSearches();
  const advancedOpen = Boolean(
    params.year_from || params.year_to || params.axis || params.methodology || params.venue ||
    params.author || params.tag || params.reading_status,
  );

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Paper Library</p>
          <h2 className="pageTitle">Find the papers that change your research question.</h2>
          <p className="pageIntro">
            Start broad, then narrow by evidence scope, year, method, author, venue, and your own reading state.
          </p>
        </div>
      </header>

      <section className="libraryShell">
        <form className="searchDeck" action="/library" method="get">
          <div className="searchDeckPrimary">
            <input
              className="input searchDeckInput"
              name="q"
              defaultValue={query}
              placeholder="Search a concept, theory, method, industry, or outcome…"
              aria-label="Search papers"
            />
            <button className="button" type="submit">Search →</button>
          </div>

          <div className="quickFilters">
            <select className="select" name="mode" defaultValue={mode}>
              <option value="hybrid">Hybrid retrieval</option><option value="lexical">Lexical only</option><option value="vector">Semantic only</option>
            </select>
            <select className="select" name="scope" defaultValue={scope}>
              <option value="all">All evidence</option><option value="metadata">Metadata</option><option value="abstract">Abstract</option><option value="full_text">Private full text</option>
            </select>
            <select className="select" name="sort" defaultValue={sort}>
              <option value="relevance">Sort: relevance</option><option value="newest">Sort: newest</option><option value="citation_count">Sort: citations</option><option value="reading_priority">Sort: my priority</option>
            </select>
            <select className="select" name="is_oa" defaultValue={params.is_oa ?? ""}>
              <option value="">Any access</option><option value="true">Open access</option><option value="false">Closed/unknown</option>
            </select>
          </div>

          <details className="advancedFilters" open={advancedOpen}>
            <summary>Advanced filters & retrieval controls</summary>
            <div className="filterForm advancedFilterGrid">
              <select className="select" name="semantic_provider" defaultValue={semanticProvider}>
                <option value="auto">Semantic: auto</option><option value="local_hash">Semantic: local_hash baseline</option><option value="fastembed">Semantic: MiniLM neural local</option>
              </select>
              <select className="select" name="rerank" defaultValue={rerank}>
                <option value="none">Reranker: none</option><option value="fastembed">Reranker: experimental cross-encoder</option>
              </select>
              <input className="input" name="year_from" defaultValue={params.year_from} placeholder="Year from" inputMode="numeric" />
              <input className="input" name="year_to" defaultValue={params.year_to} placeholder="Year to" inputMode="numeric" />
              <input className="input" name="axis" defaultValue={params.axis} placeholder="Research axis slug" />
              <input className="input" name="methodology" defaultValue={params.methodology} placeholder="Methodology" />
              <input className="input" name="venue" defaultValue={params.venue} placeholder="Venue" />
              <input className="input" name="author" defaultValue={params.author} placeholder="Author" />
              <input className="input" name="tag" defaultValue={params.tag} placeholder="Tag" />
              <select className="select" name="reading_status" defaultValue={params.reading_status ?? ""}>
                <option value="">Any reading state</option><option value="unread">Unread</option><option value="skimming">Skimming</option><option value="reading">Reading</option><option value="read">Read</option><option value="archived">Archived</option>
              </select>
            </div>
          </details>
        </form>

        {!query ? (
          <div className="emptyState libraryEmpty">
            <strong>Start with a research idea.</strong>
            <span>Search the 529-paper corpus, or import your own DOI/BibTeX/RIS/PDF collection.</span>
            <div className="heroActions lightActions">
              <Link className="secondaryButton" href="/questions">Open research questions</Link>
              <Link className="secondaryButton" href="/imports">Import papers</Link>
            </div>
          </div>
        ) : result ? (
          <div className="resultStack">
            <div className="resultSummary resultSummaryBar">
              <div><strong>{result.total} ranked papers</strong><span className="muted"> for “{query}”</span></div>
              <div className="rankRow">
                <span className="pill">{result.mode}</span><span className="pill">{result.scope}</span>
                <span className="pill">{result.sort}</span><span className="pill">semantic: {result.semantic_provider}</span>
              </div>
            </div>
            {result.items.map((paper) => (
              <article className="paperResult" key={paper.id}>
                <div className="paperMeta">
                  <span>{paper.publication_year ?? "Year unknown"}</span><span>{paper.work_type ?? "work"}</span>
                  <span>{paper.is_oa ? "Open access" : "OA unknown/closed"}</span><span>{paper.citation_count} citations</span>
                </div>
                <h3><Link href={`/library/${paper.id}`}>{paper.title}</Link></h3>
                {paper.matched_excerpt ? <p>{paper.matched_excerpt}{paper.matched_excerpt.length >= 600 ? "…" : ""}</p> : paper.abstract ? <p>{paper.abstract.slice(0, 420)}…</p> : null}
                <div className="rankRow rankRowSubtle">
                  <span>Lexical #{paper.lexical_rank ?? "—"}</span><span>Semantic #{paper.semantic_rank ?? "—"}</span>
                  <span>RRF {paper.fused_score.toFixed(4)}</span>{paper.rerank_score !== null ? <span>Rerank {paper.rerank_score.toFixed(4)}</span> : null}
                  <span>{paper.matched_source}</span>{paper.matched_locator ? <span>{paper.matched_locator}</span> : null}
                  {paper.reading_priority ? <span>Priority {paper.reading_priority}</span> : null}
                </div>
                <div className="resultActions">
                  <Link className="textLink" href={`/library/${paper.id}`}>Open research record →</Link>
                  <Link className="textLink" href={`/compare?paper=${paper.id}`}>Add to Compare →</Link>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="emptyState libraryEmpty">The API could not return results. Confirm the database and API are running.</div>
        )}
      </section>

      <section className="grid" style={{ marginTop: 16 }}>
        <article className="card span6">
          <h3 className="sectionTitle">Save this search</h3>
          <form action={saveSearchAction} className="formStack">
            <input className="input" name="name" placeholder="Saved search name" required />
            <input type="hidden" name="q" value={query} />
            {Object.entries({ mode, scope, sort, ...params }).map(([key, value]) =>
              key !== "q" && value ? <input type="hidden" name={key} value={String(value)} key={key} /> : null,
            )}
            <button className="button" type="submit" disabled={!query}>Save current query + filters</button>
          </form>
        </article>
        <article className="card span6">
          <h3 className="sectionTitle">Saved searches</h3>
          <div className="tagCloud">
            {savedSearches.length ? savedSearches.map((saved) => {
              const search = new URLSearchParams({ q: saved.query_text });
              for (const [key, value] of Object.entries(saved.filters)) {
                if (value !== null && value !== "") search.set(key, String(value));
              }
              return <Link className="pill" href={`/library?${search.toString()}`} key={saved.id}>{saved.name}</Link>;
            }) : <span className="muted">No saved searches yet.</span>}
          </div>
        </article>
      </section>
    </>
  );
}
