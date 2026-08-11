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
  const semanticProvider = option(params.semantic_provider, ["local_hash", "fastembed"] as const, "local_hash");
  const options: SearchOptions = { ...params, scope, sort, semantic_provider: semanticProvider };
  const result = query ? await searchPapers(query, mode, options) : null;
  const savedSearches = await listSavedSearches();

  return (
    <>
      <header className="pageHeader">
        <div><p className="eyebrow">Paper Library</p><h2 className="pageTitle">Search across metadata, abstracts, and private full text.</h2>
          <p className="pageIntro">Every result exposes the retrieval lens, RRF ranks, and the evidence surface that matched. The local hash embedding remains an engineering baseline, not a production semantic model.</p></div>
      </header>
      <section className="card">
        <form className="filterForm" action="/library" method="get">
          <input className="input filterWide" name="q" defaultValue={query} placeholder="AI capability firm performance" aria-label="Search papers" />
          <select className="select" name="mode" defaultValue={mode}><option value="hybrid">Hybrid</option><option value="lexical">Lexical</option><option value="vector">Vector</option></select>
          <select className="select" name="semantic_provider" defaultValue={semanticProvider}><option value="local_hash">Semantic: local_hash baseline</option><option value="fastembed">Semantic: MiniLM neural local</option></select>
          <select className="select" name="scope" defaultValue={scope}><option value="all">All evidence</option><option value="metadata">Metadata</option><option value="abstract">Abstract</option><option value="full_text">Private full text</option></select>
          <select className="select" name="sort" defaultValue={sort}><option value="relevance">Relevance</option><option value="newest">Newest</option><option value="citation_count">Citation count</option><option value="reading_priority">Reading priority</option></select>
          <input className="input" name="year_from" defaultValue={params.year_from} placeholder="Year from" inputMode="numeric" />
          <input className="input" name="year_to" defaultValue={params.year_to} placeholder="Year to" inputMode="numeric" />
          <input className="input" name="axis" defaultValue={params.axis} placeholder="Research axis slug" />
          <input className="input" name="methodology" defaultValue={params.methodology} placeholder="Methodology" />
          <input className="input" name="venue" defaultValue={params.venue} placeholder="Venue" />
          <input className="input" name="author" defaultValue={params.author} placeholder="Author" />
          <input className="input" name="tag" defaultValue={params.tag} placeholder="Tag" />
          <select className="select" name="reading_status" defaultValue={params.reading_status ?? ""}><option value="">Any reading state</option><option value="unread">Unread</option><option value="skimming">Skimming</option><option value="reading">Reading</option><option value="read">Read</option><option value="archived">Archived</option></select>
          <select className="select" name="is_oa" defaultValue={params.is_oa ?? ""}><option value="">Any OA</option><option value="true">Open access</option><option value="false">Closed/unknown</option></select>
          <button className="button" type="submit">Search</button>
        </form>
        {!query ? <div className="emptyState" style={{ marginTop: 18 }}>Search the 529-paper local corpus or import your own records and permitted PDFs.</div> : result ? (
          <div className="resultStack"><div className="resultSummary"><strong>{result.total} ranked papers</strong><span className="pill">{result.mode}</span><span className="pill">semantic: {result.semantic_provider}</span><span className="pill">scope: {result.scope}</span><span className="pill">sort: {result.sort}</span></div>
            {result.items.map((paper) => <article className="paperResult" key={paper.id}>
              <div className="paperMeta"><span>{paper.publication_year ?? "Year unknown"}</span><span>{paper.work_type ?? "work"}</span><span>{paper.is_oa ? "OA" : "OA unknown/closed"}</span><span>{paper.citation_count} citations</span></div>
              <h3>{paper.title}</h3>
              {paper.matched_excerpt ? <p>{paper.matched_excerpt}{paper.matched_excerpt.length >= 600 ? "…" : ""}</p> : paper.abstract ? <p>{paper.abstract.slice(0, 420)}…</p> : null}
              <div className="rankRow"><span className="pill">Lexical #{paper.lexical_rank ?? "—"}</span><span className="pill">Vector #{paper.semantic_rank ?? "—"}</span><span className="pill">RRF {paper.fused_score.toFixed(4)}</span><span className="pill">{paper.matched_source}</span>{paper.matched_locator ? <span className="pill">{paper.matched_locator}</span> : null}{paper.reading_priority ? <span className="pill">Priority {paper.reading_priority}</span> : null}</div>
              <div className="resultActions"><Link className="textLink" href={`/library/${paper.id}`}>Open research record →</Link><Link className="textLink" href={`/compare?paper=${paper.id}`}>Add to Compare →</Link></div>
            </article>)}
          </div>
        ) : <div className="emptyState" style={{ marginTop: 18 }}>The API could not return results. Confirm the database and API are running.</div>}
      </section>
      <section className="grid" style={{ marginTop: 16 }}>
        <article className="card span6"><h3 className="sectionTitle">Save this search</h3><form action={saveSearchAction} className="formStack">
          <input className="input" name="name" placeholder="Saved search name" required />
          <input type="hidden" name="q" value={query} />
          {Object.entries({ mode, scope, sort, ...params }).map(([key, value]) => key !== "q" && value ? <input type="hidden" name={key} value={String(value)} key={key} /> : null)}
          <button className="button" type="submit" disabled={!query}>Save current query + filters</button>
        </form></article>
        <article className="card span6"><h3 className="sectionTitle">Saved searches</h3><div className="tagCloud">
          {savedSearches.length ? savedSearches.map((saved) => {
            const search = new URLSearchParams({ q: saved.query_text });
            for (const [key, value] of Object.entries(saved.filters)) if (value !== null && value !== "") search.set(key, String(value));
            return <Link className="pill" href={`/library?${search.toString()}`} key={saved.id}>{saved.name}</Link>;
          }) : <span className="muted">No saved searches yet.</span>}
        </div></article>
      </section>
    </>
  );
}
