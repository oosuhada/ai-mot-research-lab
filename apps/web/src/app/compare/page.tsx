import Link from "next/link";

import { MutationFeedback } from "@/components/MutationFeedback";
import { LocalizedText } from "@/components/LocalizedText";
import {
  getComparisonSet,
  getPaper,
  listComparisonSets,
  searchPapers,
  type PaperDetail,
} from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import { createComparisonFromIds, createComparisonFromTopic, editComparisonCellAction } from "./actions";

const fields = [
  ["research_question", "Research question", "연구 질문"], ["theoretical_lens", "Theoretical lens", "이론적 관점"],
  ["unit_of_analysis", "Unit of analysis", "분석 단위"], ["context_industry_country", "Context / industry / country", "맥락 / 산업 / 국가"],
  ["dataset_and_sample", "Dataset and sample", "데이터와 표본"], ["methodology", "Methodology", "연구방법"],
  ["variables_or_constructs", "Variables or constructs", "변수 또는 구성개념"], ["findings", "Findings", "연구 결과"],
  ["limitations", "Limitations", "한계"], ["claimed_contribution", "Claimed contribution", "주장된 기여"],
  ["future_research", "Future research", "후속 연구"],
] as const;

type CompareSearchParams = {
  id?: string;
  paper?: string;
  papers?: string;
  q?: string;
  feedback?: string;
};

const feedbackMessages = {
  created: { message: "Comparison set created." },
  "cell-saved": { message: "Comparison note saved." },
  "invalid-topic": { message: "Enter a comparison topic with at least two characters.", tone: "error" },
  "not-enough-evidence": { message: "At least two retrieved papers are required to create a comparison.", tone: "error" },
  "invalid-selection": { message: "Select between 2 and 6 papers before creating a comparison.", tone: "error" },
  "invalid-cell": { message: "Enter a comparison note before saving the cell.", tone: "error" },
  error: { message: "The comparison change could not be saved. Your current selection is still available.", tone: "error" },
} as const;

function parsePaperIds(params: CompareSearchParams) {
  return [...new Set((params.papers ?? params.paper ?? "").split(",").map((value) => value.trim()).filter(Boolean))].slice(0, 6);
}

function pickerHref(ids: string[], query: string) {
  const search = new URLSearchParams();
  if (ids.length) search.set("papers", ids.join(","));
  if (query) search.set("q", query);
  return `/compare?${search.toString()}`;
}

export default async function ComparePage({ searchParams }: { searchParams: Promise<CompareSearchParams> }) {
  const params = await searchParams;
  const comparison = params.id ? await getComparisonSet(params.id) : null;
  const readOnly = isWorkspaceReadOnly();
  const existingComparisons = await listComparisonSets();

  if (comparison) {
    return (
      <>
        {!readOnly ? <MutationFeedback feedback={params.feedback} messages={feedbackMessages} /> : null}
        <header className="pageHeader">
          <div>
            <p className="eyebrow"><LocalizedText en="Compare Papers" ko="논문 비교" /></p>
            <h2 className="pageTitle"><LocalizedText en="Compare study design with evidence and origin visible." ko="근거와 출처를 확인하며 연구 설계를 비교하세요." /></h2>
            <p className="pageIntro"><LocalizedText en="Evidence-backed cells stay distinct from system inference. Unsupported fields remain explicit rather than being filled with plausible text." ko="근거가 있는 셀과 시스템 추론을 구분합니다. 근거가 없는 항목은 그럴듯한 문장으로 채우지 않고 명시적으로 남겨둡니다." /></p>
          </div>
        </header>

        <section className="comparisonNotebook">
          <div className="comparisonNotebookHeader">
            <div><strong>{comparison.name}</strong><span className="pill">{comparison.papers.length} papers</span></div>
            <div className="comparisonSummaryActions">
              <Link className="textLink" href={`/chat?scope=comparison_set&ids=${comparison.id}`}>Ask about this comparison →</Link>
              <a className="textLink" href={`/api/exports/comparison/${comparison.id}?format=markdown`}>Export Markdown ↗</a>
              <a className="textLink" href={`/api/exports/comparison/${comparison.id}?format=csv`}>Export CSV ↗</a>
            </div>
          </div>
          <div className="comparisonPaperLegend" aria-label="Compared papers">
            {comparison.papers.map((paper, index) => (
              <Link href={`/library/${paper.id}`} key={paper.id}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{paper.title}</strong>
                <small>{paper.publication_year ?? "Year unknown"}</small>
              </Link>
            ))}
          </div>
          <div className="comparisonFieldBands">
            {fields.map(([fieldName, label, koreanLabel], fieldIndex) => (
              <section className="comparisonFieldBand" key={fieldName} aria-labelledby={`comparison-field-${fieldName}`}>
                <header>
                  <span>{String(fieldIndex + 1).padStart(2, "0")}</span>
                  <h3 id={`comparison-field-${fieldName}`}><LocalizedText en={label} ko={koreanLabel} /></h3>
                </header>
                <div className="comparisonFieldEntries">
                  {comparison.papers.map((paper, paperIndex) => {
                    const cell = comparison.cells.find((candidate) => candidate.paper_id === paper.id && candidate.field_name === fieldName);
                    return (
                      <article className="comparisonFieldEntry" key={paper.id}>
                        <div className="comparisonEntrySource"><span>{String(paperIndex + 1).padStart(2, "0")}</span><strong>{paper.publication_year ?? "—"}</strong></div>
                        {cell ? (
                          <>
                            <div className="comparisonEntryState">
                              <span className={`statusBadge status-${cell.support_status}`}>{cell.support_status}</span>
                              <span>{cell.origin.replaceAll("_", " ")}</span>
                              <span>{cell.claim_kind.replaceAll("_", " ")}</span>
                            </div>
                            <p>{cell.value_text}</p>
                            <div className="comparisonEvidenceFootnotes">
                              {cell.evidence.map((evidence, index) => (
                                <a className="evidenceLink" key={`${cell.id}-${index}`} href={evidence.primary_url ?? (evidence.doi ? `https://doi.org/${evidence.doi}` : "#")} target="_blank" rel="noreferrer">
                                  [{index + 1}] {evidence.source_locator ?? "paper"} ↗
                                </a>
                              ))}
                            </div>
                            {!readOnly ? (
                              <details className="comparisonEdit">
                                <summary>Add / revise user note</summary>
                                <form action={editComparisonCellAction.bind(null, comparison.id, cell.id)} className="formStack">
                                  <textarea className="textarea" name="value_text" defaultValue={cell.value_text ?? ""} />
                                  <input className="input" name="evidence_chunk_id" placeholder="Optional evidence chunk ID" />
                                  <button className="button" type="submit">Save cell</button>
                                </form>
                              </details>
                            ) : null}
                          </>
                        ) : <span className="comparisonNoEvidence"><LocalizedText en="No cell · do not infer." ko="기록 없음 · 추론하지 않음" /></span>}
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}
          </div>
        </section>
      </>
    );
  }

  const selectedIds = parsePaperIds(params);
  const selectedPapers = (await Promise.all(selectedIds.map((id) => getPaper(id)))).filter((paper): paper is PaperDetail => Boolean(paper));
  const pickerQuery = params.q?.trim() ?? "";
  const pickerResults = pickerQuery ? await searchPapers(pickerQuery, "hybrid") : null;

  return (
    <>
      {!readOnly ? <MutationFeedback feedback={params.feedback} messages={feedbackMessages} /> : null}
      <header className="pageHeader">
        <div>
          <p className="eyebrow"><LocalizedText en="Compare Papers" ko="논문 비교" /></p>
          <h2 className="pageTitle"><LocalizedText en="Choose papers by title, not by database ID." ko="데이터베이스 ID가 아니라 논문 제목으로 선택하세요." /></h2>
          <p className="pageIntro"><LocalizedText en="Select 2–6 papers from Library or search here. The comparison keeps claim origin and evidence support visible at cell level." ko="라이브러리에서 2~6편을 선택하거나 여기에서 검색하세요. 비교표는 각 셀의 주장 출처와 근거 상태를 표시합니다." /></p>
        </div>
      </header>

      {existingComparisons.length ? (
        <section className="existingComparisonStrip">
          <div><span className="cardKicker"><LocalizedText en="Ready to inspect" ko="검토 가능" /></span><strong><LocalizedText en="Saved comparison sets" ko="저장된 비교 세트" /></strong></div>
          <div className="existingComparisonLinks">
            {existingComparisons.slice(0, 6).map((item) => <Link className="pill" href={`/compare?id=${item.id}`} key={item.id}>{item.name} · {item.paper_count}</Link>)}
          </div>
        </section>
      ) : null}

      <section className="compareBuilder">
        <article className="comparePickerPanel">
          <div className="sectionHeadingRow">
            <div><span className="cardKicker"><LocalizedText en="Paper picker" ko="논문 선택" /></span><h3 className="sectionTitle"><LocalizedText en="Build a comparison set" ko="비교 세트 만들기" /></h3></div>
            <span className="pill">{selectedPapers.length}/6 <LocalizedText en="selected" ko="선택" /></span>
          </div>

          <form className="compareSearchForm" action="/compare" method="get">
            {selectedIds.length ? <input type="hidden" name="papers" value={selectedIds.join(",")} /> : null}
            <label className="srOnly" htmlFor="compare-paper-search">Find papers to compare</label>
            <input className="input" id="compare-paper-search" name="q" defaultValue={pickerQuery} placeholder="Search paper titles, concepts, or methods…" />
            <button className="button buttonSecondary" type="submit"><LocalizedText en="Find papers" ko="논문 찾기" /></button>
          </form>

          {selectedPapers.length ? (
            <div className="selectedPaperList">
              {selectedPapers.map((paper, index) => {
                const nextIds = selectedIds.filter((id) => id !== paper.id);
                return (
                  <div className="selectedPaperRow" key={paper.id}>
                    <span className="selectedPaperIndex">{String(index + 1).padStart(2, "0")}</span>
                    <div><strong>{paper.title}</strong><span>{paper.publication_year ?? "Year unknown"} · {paper.citation_count} citations</span></div>
                    <Link className="textLink" href={pickerHref(nextIds, pickerQuery)}>Remove</Link>
                  </div>
                );
              })}
            </div>
          ) : <div className="pickerEmpty"><LocalizedText en="No papers selected yet. Select from Library or search below." ko="선택된 논문이 없습니다. 라이브러리에서 선택하거나 아래에서 검색하세요." /></div>}

          {selectedIds.length ? (
            <div className="compareSelectionActions">
              <Link className="secondaryButton" href={`/chat?scope=papers&ids=${encodeURIComponent(selectedIds.join(","))}`}>Ask selected papers with evidence →</Link>
            </div>
          ) : null}

          {pickerResults ? (
            <div className="compareSearchResults">
              {pickerResults.items.slice(0, 8).map((paper) => {
                const selected = selectedIds.includes(paper.id);
                const nextIds = selected ? selectedIds.filter((id) => id !== paper.id) : [...selectedIds, paper.id].slice(0, 6);
                return (
                  <div className={`compareSearchResult${selected ? " compareSearchResultSelected" : ""}`} key={paper.id}>
                    <div><strong>{paper.title}</strong><span>{paper.publication_year ?? "Year unknown"} · {paper.citation_count} citations</span></div>
                    <Link className="paperSelectButton" href={pickerHref(nextIds, pickerQuery)}>{selected ? "✓ Added" : "+ Add"}</Link>
                  </div>
                );
              })}
            </div>
          ) : null}

          {!readOnly ? (
            <form className="createComparisonBar" action={createComparisonFromIds}>
              <input type="hidden" name="paper_ids" value={selectedIds.join(",")} />
              <label className="compactFieldLabel"><span><LocalizedText en="Comparison name" ko="비교 이름" /></span><input className="input" name="name" placeholder="e.g. AI capability mechanisms" /></label>
              <button className="button" type="submit" disabled={selectedIds.length < 2}><LocalizedText en="Create comparison" ko="비교 만들기" /></button>
            </form>
          ) : <div className="readOnlyPanel"><strong>Public Demo · Read-only</strong><span>Use an existing comparison above to inspect the evidence matrix. Creating new sets is disabled on the portfolio deployment.</span></div>}
        </article>

        <aside className="compareTopicPanel">
          <span className="cardKicker"><LocalizedText en="Fast path" ko="빠른 시작" /></span>
          <h3 className="sectionTitle"><LocalizedText en="Let retrieval propose a starting set" ko="검색 시스템이 시작 세트를 제안하도록 하기" /></h3>
          <p className="metricHelp"><LocalizedText en="Useful for exploration. You should still inspect why each paper was retrieved before treating the set as representative." ko="초기 탐색에 유용합니다. 이 세트를 대표 표본으로 보기 전에 각 논문이 검색된 이유를 확인하세요." /></p>
          {!readOnly ? (
            <form className="formStack" action={createComparisonFromTopic}>
              <label className="compactFieldLabel"><span>Research topic</span><input className="input" name="query" required minLength={2} placeholder="AI capability and firm performance" /></label>
              <button className="button buttonSecondary" type="submit">Compare top 3 candidates</button>
            </form>
          ) : <Link className="secondaryButton" href="/library">Select papers in Library →</Link>}
        </aside>
      </section>
    </>
  );
}
