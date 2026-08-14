import Link from "next/link";

import { LibraryResults } from "@/components/LibraryResults";
import { LocalizedText } from "@/components/LocalizedText";
import {
  browsePapers,
  getLandscape,
  listResearchQuestions,
  listSavedSearches,
  searchPapers,
  type SearchOptions,
} from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { saveSearchAction } from "./actions";

type LibrarySearchParams = SearchOptions & {
  q?: string;
  mode?: string;
  page?: string;
  cursor?: string;
  view?: string;
  feedback?: string;
};

const PAGE_SIZE = 10;

function normalizeMode(value: string | undefined): "lexical" | "vector" | "hybrid" {
  return value === "lexical" || value === "vector" ? value : "hybrid";
}

function option<T extends string>(value: string | undefined, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function pageNumber(value: string | undefined): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function searchHref(params: LibrarySearchParams, omitKey?: keyof LibrarySearchParams) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === omitKey || key === "page" || key === "cursor" || key === "feedback" || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  const suffix = search.toString();
  return suffix ? `/library?${suffix}` : "/library";
}

function paginationHref(params: LibrarySearchParams, page: number) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === "page" || key === "cursor" || key === "feedback" || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  if (page > 1) search.set("page", String(page));
  const suffix = search.toString();
  return suffix ? `/library?${suffix}` : "/library";
}

function browsePaginationHref(params: LibrarySearchParams, cursor?: string | null) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === "page" || key === "cursor" || key === "feedback" || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  search.set("view", "browse");
  if (cursor) search.set("cursor", cursor);
  return `/library?${search.toString()}`;
}

function viewHref(params: LibrarySearchParams, view: "search" | "browse") {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (key === "page" || key === "cursor" || key === "feedback" || key === "view" || value === undefined || value === "") continue;
    search.set(key, String(value));
  }
  search.set("view", view);
  return `/library?${search.toString()}`;
}

export default async function LibraryPage({ searchParams }: { searchParams: Promise<LibrarySearchParams> }) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  const mode = normalizeMode(params.mode);
  const view = params.view === "browse" ? "browse" : "search";
  const page = pageNumber(params.page);
  const offset = (page - 1) * PAGE_SIZE;
  const returnTo = view === "browse"
    ? browsePaginationHref({ ...params, q: query, mode, view }, params.cursor)
    : paginationHref({ ...params, q: query, mode, view }, page);
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
  const [searchResult, browseResult, savedSearches, landscape, questions] = await Promise.all([
    view === "search" && query ? searchPapers(query, mode, options, { limit: PAGE_SIZE, offset }) : Promise.resolve(null),
    view === "browse" ? browsePapers(options, { limit: PAGE_SIZE, cursor: params.cursor }) : Promise.resolve(null),
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
          <p className="eyebrow"><LocalizedText en="Paper Library" ko="논문 라이브러리" /></p>
          <h2 className="pageTitle"><LocalizedText en="Find the papers that change your research question." ko="연구 질문을 바꾸는 논문을 찾아보세요." /></h2>
          <p className="pageIntro">
            <LocalizedText en={`Search ${corpusCount.toLocaleString()} live research records, then carry selected evidence directly into comparison or chat.`} ko={`${corpusCount.toLocaleString()}개의 연구 레코드를 검색하고 선택한 근거를 논문 비교나 채팅으로 바로 가져가세요.`} />
          </p>
        </div>
      </header>

      <section className="libraryShell">
        <nav className="libraryModeSwitch" aria-label="Library mode">
          <Link
            className={`libraryModeOption${view === "search" ? " libraryModeOptionActive" : ""}`}
            href={viewHref({ ...params, q: query, mode }, "search")}
            aria-current={view === "search" ? "page" : undefined}
          >
            <strong><LocalizedText en="Search Results" ko="검색 결과" /></strong>
            <span><LocalizedText en="Ranked retrieval · stable top-100 candidate pool" ko="순위 검색 · 고정된 상위 100개 후보군" /></span>
          </Link>
          <Link
            className={`libraryModeOption${view === "browse" ? " libraryModeOptionActive" : ""}`}
            href={viewHref({ ...params, q: query, mode }, "browse")}
            aria-current={view === "browse" ? "page" : undefined}
          >
            <strong><LocalizedText en="Browse All Papers" ko="전체 논문 탐색" /></strong>
            <span><LocalizedText en="Entire filtered corpus · cursor pagination" ko="필터링된 전체 코퍼스 · 커서 페이지 이동" /></span>
          </Link>
        </nav>

        {!readOnly && params.feedback ? (
          <div className={`mutationFeedback${params.feedback === "error" ? " mutationFeedbackError" : ""}`} role="status">
            {params.feedback === "saved"
              ? "Search saved to your workspace."
              : params.feedback === "linked"
                ? "Selected papers added to the current research question."
                : "The workspace change could not be saved. Your search state has been preserved."}
          </div>
        ) : null}
        <form className="searchDeck" action="/library" method="get">
          <div className="searchDeckPrimary">
            <label className="srOnly" htmlFor="paper-search"><LocalizedText en="Search papers" ko="논문 검색" /></label>
            <input className="input searchDeckInput" id="paper-search" name="q" defaultValue={query} placeholder="Search a concept, theory, method, industry, or outcome…" />
            <button className="button" type="submit" name="view" value="search"><LocalizedText en="Search →" ko="검색 →" /></button>
          </div>

          <div className="quickFilters">
            {view === "search" ? <label className="compactFieldLabel"><span><LocalizedText en="Search style" ko="검색 방식" /></span><select className="select" name="mode" defaultValue={mode}><option value="hybrid">Balanced · 균형</option><option value="lexical">Exact keywords · 정확 키워드</option><option value="vector">Similar meaning · 유사 의미</option></select></label> : <input type="hidden" name="mode" value={mode} />}
            {view === "search" ? <label className="compactFieldLabel"><span><LocalizedText en="Evidence scope" ko="근거 범위" /></span><select className="select" name="scope" defaultValue={scope}><option value="all">All evidence · 전체 근거</option><option value="metadata">Metadata · 서지정보</option><option value="abstract">Abstracts · 초록</option><option value="full_text">Full text · 논문 전문</option></select></label> : null}
            {view === "search" ? <label className="compactFieldLabel"><span><LocalizedText en="Sort" ko="정렬" /></span><select className="select" name="sort" defaultValue={sort}><option value="relevance">Most relevant · 관련성</option><option value="newest">Newest · 최신</option><option value="citation_count">Most cited · 최다 인용</option><option value="reading_priority">Reading priority · 읽기 우선순위</option></select></label> : <label className="compactFieldLabel"><span><LocalizedText en="Browse order" ko="탐색 순서" /></span><span className="fixedFilterValue"><LocalizedText en="Newest local import" ko="최근 로컬 수집순" /></span></label>}
            <label className="compactFieldLabel"><span><LocalizedText en="Access" ko="접근 권한" /></span><select className="select" name="is_oa" defaultValue={params.is_oa ?? ""}><option value="">Any · 전체</option><option value="true">Open access · 공개</option><option value="false">Closed / unknown · 비공개/미상</option></select></label>
          </div>

          <details className="advancedFilters" open={advancedOpen}>
            <summary><LocalizedText en="Research filters" ko="연구 필터" /></summary>
            <div className="filterForm advancedFilterGrid">
              <label className="compactFieldLabel"><span><LocalizedText en="Year from" ko="시작 연도" /></span><input className="input" name="year_from" defaultValue={params.year_from} inputMode="numeric" /></label>
              <label className="compactFieldLabel"><span><LocalizedText en="Year to" ko="종료 연도" /></span><input className="input" name="year_to" defaultValue={params.year_to} inputMode="numeric" /></label>
              <label className="compactFieldLabel">
                <span><LocalizedText en="Research area" ko="연구 영역" /></span>
                <select className="select" name="axis" defaultValue={params.axis ?? ""}>
                  <option value="">Any research area</option>
                  {(landscape?.axes ?? []).map((axis) => <option value={axis.slug} key={axis.slug}>{axis.display_name}</option>)}
                </select>
              </label>
              <label className="compactFieldLabel"><span><LocalizedText en="Methodology" ko="연구방법" /></span><input className="input" name="methodology" defaultValue={params.methodology} placeholder="e.g. case study" /></label>
              <label className="compactFieldLabel"><span><LocalizedText en="Work type" ko="자료 유형" /></span><input className="input" name="work_type" defaultValue={params.work_type} placeholder="e.g. article" /></label>
              <label className="compactFieldLabel"><span><LocalizedText en="Venue" ko="학술지" /></span><input className="input" name="venue" defaultValue={params.venue} /></label>
              <label className="compactFieldLabel"><span><LocalizedText en="Author" ko="저자" /></span><input className="input" name="author" defaultValue={params.author} /></label>
              <label className="compactFieldLabel"><span><LocalizedText en="Tag" ko="태그" /></span><input className="input" name="tag" defaultValue={params.tag} /></label>
              <label className="compactFieldLabel"><span><LocalizedText en="Reading state" ko="읽기 상태" /></span><select className="select" name="reading_status" defaultValue={params.reading_status ?? ""}><option value="">Any · 전체</option><option value="unread">Unread · 읽지 않음</option><option value="skimming">Skimming · 훑어보는 중</option><option value="reading">Reading · 읽는 중</option><option value="read">Read · 읽음</option><option value="archived">Archived · 보관됨</option></select></label>
            </div>
          </details>

          {view === "search" ? <details className="retrievalInspector" open={inspectorOpen}>
            <summary><LocalizedText en="Retrieval inspector" ko="검색 시스템 점검" /></summary>
            <p><LocalizedText en="Optional engineering controls for evaluating the local retrieval stack. Most research tasks should keep the defaults." ko="로컬 검색 시스템을 평가하기 위한 선택적 기술 설정입니다. 대부분의 연구 작업에서는 기본값을 유지하세요." /></p>
            <div className="retrievalInspectorGrid">
              <label className="compactFieldLabel"><span>Meaning model</span><select className="select" name="semantic_provider" defaultValue={semanticProvider}><option value="auto">Automatic</option><option value="local_hash">Deterministic local baseline</option><option value="fastembed">Local MiniLM embeddings</option></select></label>
              <label className="compactFieldLabel"><span>Second-pass ordering</span><select className="select" name="rerank" defaultValue={rerank}><option value="none">Off · recommended</option><option value="fastembed">Experimental cross-encoder</option></select></label>
            </div>
          </details> : null}

          {view === "browse" ? <button className="button buttonSecondary browseApplyButton" type="submit" name="view" value="browse"><LocalizedText en="Apply browse filters" ko="탐색 필터 적용" /></button> : null}

          {activeFilters.length ? (
            <div className="activeFilterRow" aria-label="Active filters">
              {activeFilters.map(([key, value, label]) => (
                <Link className="activeFilterChip" href={searchHref({ ...params, q: query, mode }, key)} key={key}>
                  {label}: {value} <span aria-hidden="true">×</span>
                </Link>
              ))}
              <Link className="clearFiltersLink" href={view === "browse" ? `/library?view=browse&q=${encodeURIComponent(query)}&mode=${mode}` : `/library?view=search&q=${encodeURIComponent(query)}&mode=${mode}`}><LocalizedText en="Clear all" ko="모두 지우기" /></Link>
            </div>
          ) : null}
        </form>

        {view === "search" && !query ? (
          <div className="emptyState libraryEmpty">
            <strong><LocalizedText en="Start with a research idea." ko="연구 아이디어에서 시작하세요." /></strong>
            <span><LocalizedText en={`Search the live ${corpusCount.toLocaleString()}-paper corpus, or switch to Browse All Papers to move through every record without changing the retrieval candidate pool.`} ko={`${corpusCount.toLocaleString()}편의 실시간 코퍼스를 검색하거나 전체 논문 탐색으로 전환해 검색 후보군을 바꾸지 않고 모든 레코드를 살펴보세요.`} /></span>
            <div className="heroActions lightActions">
              <Link className="secondaryButton" href={viewHref({ ...params, q: query, mode }, "browse")}><LocalizedText en="Browse all papers" ko="전체 논문 탐색" /></Link>
              <Link className="secondaryButton" href="/questions"><LocalizedText en="Browse research questions" ko="연구 질문 살펴보기" /></Link>
              {!readOnly ? <Link className="secondaryButton" href="/imports"><LocalizedText en="Import papers" ko="논문 가져오기" /></Link> : null}
            </div>
          </div>
        ) : view === "search" && searchResult ? (
          <div className="resultStack">
            <div className="resultSummary resultSummaryBar libraryResultSummary">
              <div className="resultSummaryCopy">
                <strong>
                  {searchResult.items.length
                    ? `Showing ${searchResult.offset + 1}–${searchResult.offset + searchResult.items.length} of ${searchResult.total}${searchResult.total_is_capped ? "+" : ""} ranked candidates`
                    : "No ranked candidates"}
                </strong>
                <span className="muted"> for “{query}”{searchResult.total_is_capped ? ` · candidate pool capped at ${searchResult.candidate_cap}` : ""}</span>
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
                  <input type="hidden" name="return_to" value={returnTo} />
                  {Object.entries({ mode, scope, sort, ...options }).map(([key, value]) => value ? <input type="hidden" name={key} value={String(value)} key={key} /> : null)}
                  <button className="button buttonSecondary" type="submit"><LocalizedText en="Save search" ko="검색 저장" /></button>
                </form>
              ) : <span className="readOnlyInline">Public demo · saving disabled</span>}
            </div>

            <LibraryResults items={searchResult.items} query={query} resultMode="search" questions={questions} readOnly={readOnly} returnTo={returnTo} />

            {(page > 1 || searchResult.has_more) ? (
              <nav className="libraryPagination" aria-label="Library result pages">
                {page > 1 ? <Link className="paginationLink" href={paginationHref({ ...params, q: query, mode }, page - 1)}><LocalizedText en="← Previous" ko="← 이전" /></Link> : <span className="paginationLink paginationLinkDisabled"><LocalizedText en="← Previous" ko="← 이전" /></span>}
                <span className="paginationStatus"><LocalizedText en={`Page ${page}`} ko={`${page}페이지`} /></span>
                {searchResult.has_more ? <Link className="paginationLink" href={paginationHref({ ...params, q: query, mode }, page + 1)}><LocalizedText en="Next →" ko="다음 →" /></Link> : <span className="paginationLink paginationLinkDisabled"><LocalizedText en="Next →" ko="다음 →" /></span>}
              </nav>
            ) : null}
          </div>
        ) : view === "browse" && browseResult ? (
          <div className="resultStack">
            <div className="resultSummary resultSummaryBar libraryResultSummary">
              <div className="resultSummaryCopy">
                <strong>
                  {browseResult.items.length
                    ? `Showing papers ${browseResult.offset + 1}–${browseResult.offset + browseResult.items.length} of ${browseResult.total}`
                    : `No papers match the current filters out of ${browseResult.total}`}
                </strong>
                <span className="muted"> · exact corpus count · ordered by local import time with paper ID tie-breaker</span>
                <div className="rankRow">
                  <span className="pill"><LocalizedText en="Browse All Papers" ko="전체 논문 탐색" /></span>
                  <span className="pill"><LocalizedText en="Cursor pagination" ko="커서 페이지 이동" /></span>
                </div>
              </div>
            </div>

            <LibraryResults items={browseResult.items} query={query} resultMode="browse" questions={questions} readOnly={readOnly} returnTo={returnTo} />

            {(browseResult.has_previous || browseResult.has_more) ? (
              <nav className="libraryPagination" aria-label="Browse all paper pages">
                {browseResult.previous_cursor ? <Link className="paginationLink" href={browsePaginationHref({ ...params, q: query, mode, view: "browse" }, browseResult.previous_cursor)}><LocalizedText en="← Previous" ko="← 이전" /></Link> : <span className="paginationLink paginationLinkDisabled"><LocalizedText en="← Previous" ko="← 이전" /></span>}
                <span className="paginationStatus">Papers {browseResult.offset + 1}–{browseResult.offset + browseResult.items.length}</span>
                {browseResult.next_cursor ? <Link className="paginationLink" href={browsePaginationHref({ ...params, q: query, mode, view: "browse" }, browseResult.next_cursor)}><LocalizedText en="Next →" ko="다음 →" /></Link> : <span className="paginationLink paginationLinkDisabled"><LocalizedText en="Next →" ko="다음 →" /></span>}
              </nav>
            ) : null}
          </div>
        ) : (
          <div className="emptyState libraryEmpty"><LocalizedText en="The API could not return results. Confirm the database and API are running." ko="API에서 결과를 가져오지 못했습니다. 데이터베이스와 API 실행 상태를 확인하세요." /></div>
        )}
      </section>

      {savedSearches.length ? (
        <section className="savedSearchSection">
          <div className="sectionHeadingRow"><div><p className="cardKicker"><LocalizedText en="Reusable scopes" ko="재사용 가능한 범위" /></p><h3 className="sectionTitle"><LocalizedText en="Saved searches" ko="저장된 검색" /></h3></div></div>
          <div className="tagCloud">
            {savedSearches.map((saved) => {
              const search = new URLSearchParams({ q: saved.query_text });
              for (const [key, value] of Object.entries(saved.filters)) {
                if (value !== null && value !== "") search.set(key, String(value));
              }
              search.set("view", "search");
              return <Link className="pill savedSearchPill" href={`/library?${search.toString()}`} key={saved.id}>{saved.name}</Link>;
            })}
          </div>
        </section>
      ) : null}
    </>
  );
}
