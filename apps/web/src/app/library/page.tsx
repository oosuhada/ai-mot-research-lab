import Link from "next/link";

import { LibraryResults } from "@/components/LibraryResults";
import {
  getLandscape,
  listResearchQuestions,
  listSavedSearches,
  searchPapers,
  type SearchOptions,
} from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { saveSearchAction } from "./actions";

type LibrarySearchParams = SearchOptions & { q?: string; mode?: string };

function normalizeMode(value: string | undefined): "lexical" | "vector" | "hybrid" {
  return value === "lexical" || value === "vector" ? value : "hybrid";
}

function option<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function searchHref(params: LibrarySearchParams, omitKey?: keyof LibrarySearchParams) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === omitKey || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `/library?${suffix}` : "/library";
}

export default async function LibraryPage({ searchParams }: { searchParams: Promise<LibrarySearchParams> }) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  const mode = normalizeMode(params.mode);
  const scope = option(params.scope, ["metadata", "abstract", "full_text", "all"] as const, "all");
  const sort = option(params.sort, ["relevance", "newest", "citation_count", "reading_priority"] as const, "relevance");
  const semanticProvider = option(params.semantic_provider, ["auto", "local_hash", "fastembed"] as const, "auto");
  const rerank = option(params.rerank, ["none", "fastembed"] as const, "none");
  const options: SearchOptions = {
    scope,
    sort,
    semantic_provider: semanticProvider,
    rerank,
    year_from: params.year_from,
    year_to: params.year_to,
    axis: params.axis,
    methodology: params.methodology,
    work_type: params.work_type,
    venue: params.venue,
    author: params.author,
    is_oa: params.is_oa,
    reading_status: params.reading_status,
    tag: params.tag,
  };
  const [result, savedSearches, landscape, questions] = await Promise.all([
    query ? searchPapers(query, mode, options) : Promise.resolve(null),
    listSavedSearches(),
    getLandscape(),
    listResearchQuestions(),
  ]);
  const readOnly = isWorkspaceReadOnly();
  const advancedOpen = Boolean(
    params.year_from || params.year_to || params.axis || params.methodology || params.venue ||
    params.author || params.tag || params.reading_status || params.work_type,
  );
  const inspectorOpen = semanticProvider !== "auto" || rerank !== "none";
  const activeFilters = [
    ["year_from", params.year_from, "From"],
    ["year_to", params.year_to, "To"],
    ["axis", params.axis, "Area"],
    ["methodology", params.methodology, "Method"],
    ["work_type", params.work_type, "Type"],
    ["venue", params.venue, "Venue"],
    ["author", params.author, "Author"],
    ["tag", params.tag, "Tag"],
    ["reading_status", params.reading_status, "Reading"],
    ["is_oa", params.is_oa, "Access"],
  ].filter((entry): entry is [keyof LibrarySearchParams, string, string] => Boolean(entry[1]));
  const corpusCount = landscape?.total_papers ?? 0;
  const retrievalLabel = mode === "hybrid" ? "Balanced" : mode === "lexical" ? "Exact keywords" : "Similar meaning";

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Paper Library</p>
          <h2 className="pageTitle">Find the papers that change your research question.</h2>
          <p className="pageIntro">
            Search {corpusCount.toLocaleString()} live research records, then carry selected evidence directly into comparison or chat.
          </p>
        </div>
      </header>

      <section className="libraryShell">
        <form className="searchDeck" action="/library" method="get">
          <div className="searchDeckPrimary">
            <label className="srOnly" htmlFor="paper-search">Search papers</label>
            <input className="input searchDeckInput" id="paper-search" name="q" defaultValue={query} placeholder="Search a concept, theory, method, industry, or outcome…" />
            <button className="button" type="submit">Search →</button>
          </div>

          <div className="quickFilters">
            <label className="compactFieldLabel"><span>Search style</span><select className="select" name="mode" defaultValue={mode}><option value="hybrid">Balanced</option><option value="lexical">Exact keywords</option><option value="vector">Similar meaning</option></select></label>
            <label className="compactFieldLabel"><span>Evidence scope</span><select className="select" name="scope" defaultValue={scope}><option value="all">All available evidence</option><option value="metadata">Metadata only</option><option value="abstract">Abstracts</option><option value="full_text">Available full text</option></select></label>
            <label className="compactFieldLabel"><span>Sort</span><select className="select" name="sort" defaultValue={sort}><option value="relevance">Most relevant</option><option value="newest">Newest</option><option value="citation_count">Most cited</option><option value="reading_priority">My reading priority</option></select></label>
            <label className="compactFieldLabel"><span>Access</span><select className="select" name="is_oa" defaultValue={params.is_oa ?? ""}><option value="">Any access</option><option value="true">Open access</option><option value="false">Closed / unknown</option></select></label>
          </div>

          <details className="advancedFilters" open={advancedOpen}>
            <summary>Research filters</summary>
            <div className="filterForm advancedFilterGrid">
              <label className="compactFieldLabel"><span>Year from</span><input className="input" name="year_from" defaultValue={params.year_from} inputMode="numeric" /></label>
              <label className="compactFieldLabel"><span>Year to</span><input className="input" name="year_to" defaultValue={params.year_to} inputMode="numeric" /></label>
              <label className="compactFieldLabel">
                <span>Research area</span>
                <select className="select" name="axis" defaultValue={params.axis ?? ""}>
                  <option value="">Any research area</option>
                  {(landscape?.axes ?? []).map((axis) => <option value={axis.slug} key={axis.slug}>{axis.display_name}</option>)}
                </select>
              </label>
              <label className="compactFieldLabel"><span>Methodology</span><input className="input" name="methodology" defaultValue={params.methodology} placeholder="e.g. case study" /></label>
              <label className="compactFieldLabel"><span>Work type</span><input className="input" name="work_type" defaultValue={params.work_type} placeholder="e.g. article" /></label>
              <label className="compactFieldLabel"><span>Venue</span><input className="input" name="venue" defaultValue={params.venue} /></label>
              <label className="compactFieldLabel"><span>Author</span><input className="input" name="author" defaultValue={params.author} /></label>
              <label className="compactFieldLabel"><span>Tag</span><input className="input" name="tag" defaultValue={params.tag} /></label>
              <label className="compactFieldLabel"><span>Reading state</span><select className="select" name="reading_status" defaultValue={params.reading_status ?? ""}><option value="">Any reading state</option><option value="unread">Unread</option><option value="skimming">Skimming</option><option value="reading">Reading</option><option value="read">Read</option><option value="archived">Archived</option></select></label>
            </div>
          </details>

          <details className="retrievalInspector" open={inspectorOpen}>
            <summary>Retrieval inspector</summary>
            <p>Optional engineering controls for evaluating the local retrieval stack. Most research tasks should keep the defaults.</p>
            <div className="retrievalInspectorGrid">
              <label className="compactFieldLabel"><span>Meaning model</span><select className="select" name="semantic_provider" defaultValue={semanticProvider}><option value="auto">Automatic</option><option value="local_hash">Deterministic local baseline</option><option value="fastembed">Local MiniLM embeddings</option></select></label>
              <label className="compactFieldLabel"><span>Second-pass ordering</span><select className="select" name="rerank" defaultValue={rerank}><option value="none">Off · recommended</option><option value="fastembed">Experimental cross-encoder</option></select></label>
            </div>
          </details>

          {activeFilters.length ? (
            <div className="activeFilterRow" aria-label="Active filters">
              {activeFilters.map(([key, value, label]) => (
                <Link className="activeFilterChip" href={searchHref({ ...params, q: query, mode }, key)} key={key}>
                  {label}: {value} <span aria-hidden="true">×</span>
                </Link>
              ))}
              <Link className="clearFiltersLink" href={`/library?q=${encodeURIComponent(query)}&mode=${mode}`}>Clear filters</Link>
            </div>
          ) : null}
        </form>

        {!query ? (
          <div className="emptyState libraryEmpty">
            <strong>Start with a research idea.</strong>
            <span>Search the live {corpusCount.toLocaleString()}-paper corpus. Internal retrieval diagnostics stay out of the way until you need them.</span>
            <div className="heroActions lightActions">
              <Link className="secondaryButton" href="/questions">Browse research questions</Link>
              {!readOnly ? <Link className="secondaryButton" href="/imports">Import papers</Link> : null}
            </div>
          </div>
        ) : result ? (
          <div className="resultStack">
            <div className="resultSummary resultSummaryBar libraryResultSummary">
              <div className="resultSummaryCopy">
                <strong>{result.total} ranked papers</strong>
                <span className="muted"> for “{query}”</span>
                <div className="rankRow">
                  <span className="pill">{retrievalLabel}</span>
                  <span className="pill">{scope === "all" ? "All evidence" : scope.replaceAll("_", " ")}</span>
                  <span className="pill">{sort.replaceAll("_", " ")}</span>
                </div>
              </div>

              {!readOnly ? (
                <form action={saveSearchAction} className="saveSearchInline">
                  <input className="input" name="name" aria-label="Saved search name" placeholder="Name this search" required />
                  <input type="hidden" name="q" value={query} />
                  {Object.entries({ mode, scope, sort, ...options }).map(([key, value]) => value ? <input type="hidden" name={key} value={String(value)} key={key} /> : null)}
                  <button className="button buttonSecondary" type="submit">Save search</button>
                </form>
              ) : <span className="readOnlyInline">Public demo · saving disabled</span>}
            </div>

            <LibraryResults items={result.items} query={query} questions={questions} readOnly={readOnly} />
          </div>
        ) : (
          <div className="emptyState libraryEmpty">The API could not return results. Confirm the database and API are running.</div>
        )}
      </section>

      {savedSearches.length ? (
        <section className="savedSearchSection">
          <div className="sectionHeadingRow"><div><p className="cardKicker">Reusable scopes</p><h3 className="sectionTitle">Saved searches</h3></div></div>
          <div className="tagCloud">
            {savedSearches.map((saved) => {
              const search = new URLSearchParams({ q: saved.query_text });
              for (const [key, value] of Object.entries(saved.filters)) {
                if (value !== null && value !== "") search.set(key, String(value));
              }
              return <Link className="pill savedSearchPill" href={`/library?${search.toString()}`} key={saved.id}>{saved.name}</Link>;
            })}
          </div>
        </section>
      ) : null}
    </>
  );
}
