"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { linkSelectedPapersAction } from "@/app/library/actions";
import { useResearchContext } from "@/components/ResearchContext";
import { useLocalePreference } from "@/components/LocalePreference";
import type { ResearchQuestion, SearchItem } from "@/lib/api";

type LibraryResultsProps = {
  items: SearchItem[];
  query: string;
  resultMode: "search" | "browse";
  questions: ResearchQuestion[];
  readOnly: boolean;
  returnTo: string;
};

export function LibraryResults({ items, query, resultMode, questions, readOnly, returnTo }: LibraryResultsProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const { activeQuestionId, setActiveQuestionId } = useResearchContext();
  const { locale } = useLocalePreference();
  const korean = locale === "ko";

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const paperIds = selectedIds.join(",");
  const encodedPaperIds = encodeURIComponent(paperIds);

  function togglePaper(id: string) {
    setSelectedIds((current) => {
      if (current.includes(id)) return current.filter((candidate) => candidate !== id);
      if (current.length >= 6) return current;
      return [...current, id];
    });
  }

  return (
    <>
      <ol className="scholarlyIndex" aria-label={resultMode === "search" ? "Ranked scholarly index" : "Scholarly corpus index"}>
        {items.map((paper, itemIndex) => {
          const selected = selectedSet.has(paper.id);
          return (
            <li className={`scholarlyIndexEntry${selected ? " scholarlyIndexEntrySelected" : ""}`} key={paper.id}>
              <article>
                <div className="scholarlyFolio" aria-hidden="true">{String(itemIndex + 1).padStart(2, "0")}</div>
                <div className="scholarlyEntryMain">
                  <div className="scholarlyEntryHeader">
                    <p className="scholarlyCitationLine">
                      <span>{paper.publication_year ?? "n.d."}</span>
                      <span>{paper.venue_name ?? paper.work_type ?? (korean ? "학술지 정보 없음" : "Venue unknown")}</span>
                      <span>{paper.is_oa ? (korean ? "오픈 액세스" : "open access") : (korean ? "접근 정보 없음" : "access unknown")}</span>
                    </p>
                    <h3><Link href={`/library/${paper.id}`}>{paper.title}</Link></h3>
                  </div>

                  {paper.matched_excerpt ? (
                    <blockquote className="scholarlyAnnotation">{paper.matched_excerpt}</blockquote>
                  ) : paper.abstract ? (
                    <p className="scholarlyAbstract">{paper.abstract}</p>
                  ) : (
                    <p className="scholarlyAbstract scholarlyAbstractMissing">{korean ? "이 레코드에는 초록이 없습니다." : "No abstract is available for this record."}</p>
                  )}

                  <div className="scholarlyEntryActions">
                    <Link className="textLink" href={`/library/${paper.id}`}>{korean ? "연구 레코드 읽기 →" : "Read research record →"}</Link>
                    <button className="textButtonInline" type="button" onClick={() => togglePaper(paper.id)}>
                      {selected ? (korean ? "선택에서 제거" : "Remove from selection") : (korean ? "연구 선택에 추가" : "Add to research selection")}
                    </button>
                  </div>
                </div>

                <aside className="scholarlyMarginalia">
                  <button
                    className={`paperSelectButton${selected ? " paperSelectButtonActive" : ""}`}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => togglePaper(paper.id)}
                  >
                    {selected ? (korean ? "✓ 선택됨" : "✓ Selected") : (korean ? "+ 선택" : "+ Select")}
                  </button>
                  <dl>
                    <div><dt>{korean ? "인용" : "Citations"}</dt><dd>{paper.citation_count}</dd></div>
                    {resultMode === "search" ? <div><dt>{korean ? "하이브리드 점수" : "Hybrid score"}</dt><dd>{paper.fused_score.toFixed(4)}</dd></div> : null}
                    {resultMode === "search" ? <div><dt>{korean ? "근거 위치" : "Locator"}</dt><dd>{paper.matched_locator ?? paper.matched_source.replaceAll("_", " ")}</dd></div> : <div><dt>{korean ? "정렬" : "Order"}</dt><dd>{korean ? "최근 로컬 수집" : "local import"}</dd></div>}
                  </dl>
                  {resultMode === "search" ? (
                    <details className="retrievalWhy">
                      <summary>{korean ? "검색 근거" : "Retrieval note"}</summary>
                      <div className="retrievalDiagnostics">
                        <span>{korean ? "키워드 순위" : "Keyword rank"} {paper.lexical_rank ? `#${paper.lexical_rank}` : "—"}</span>
                        <span>{korean ? "의미 순위" : "Meaning rank"} {paper.semantic_rank ? `#${paper.semantic_rank}` : "—"}</span>
                        {paper.rerank_score !== null ? <span>Rerank {paper.rerank_score.toFixed(4)}</span> : null}
                        <span>{korean ? "일치 영역" : "Matched in"} {paper.matched_source.replaceAll("_", " ")}</span>
                      </div>
                    </details>
                  ) : null}
                </aside>
              </article>
            </li>
          );
        })}
      </ol>

      {selectedIds.length ? (
        <aside className="selectionTray" aria-label="Selected papers">
          <div className="selectionTraySummary">
            <strong>{korean ? `논문 ${selectedIds.length}편 선택됨` : `${selectedIds.length} paper${selectedIds.length === 1 ? "" : "s"} selected`}</strong>
            <span>{selectedIds.length >= 6 ? (korean ? "선택 한도에 도달했습니다" : "Selection limit reached") : (korean ? "최대 6편까지 선택하세요" : "Choose up to 6 papers")}</span>
          </div>
          <div className="selectionTrayActions">
            {selectedIds.length >= 2 ? (
              <Link className="selectionAction" href={`/compare?papers=${encodedPaperIds}`}>{korean ? "비교" : "Compare"}</Link>
            ) : (
              <span className="selectionAction selectionActionDisabled">{korean ? "비교 · 2편 이상 선택" : "Compare · select 2+"}</span>
            )}
            <Link className="selectionAction" href={`/chat?scope=papers&ids=${encodedPaperIds}`}>{korean ? "근거로 질문하기" : "Ask with evidence"}</Link>
            <button className="selectionClear" type="button" onClick={() => setSelectedIds([])}>{korean ? "지우기" : "Clear"}</button>
          </div>

          {!readOnly && questions.length ? (
            <form action={linkSelectedPapersAction} className="selectionQuestionForm">
              <input type="hidden" name="paper_ids" value={paperIds} />
              <input type="hidden" name="return_to" value={returnTo} />
              <label htmlFor="selection-question">{korean ? "연구 질문에 추가" : "Add to research question"}</label>
              <select
                className="select"
                id="selection-question"
                name="question_id"
                required
                value={activeQuestionId ?? ""}
                onChange={(event) => setActiveQuestionId(event.target.value || null)}
              >
                <option value="" disabled>{korean ? "질문 선택…" : "Choose a question…"}</option>
                {questions.map((question) => (
                  <option value={question.id} key={question.id}>{question.title}</option>
                ))}
              </select>
              <button className="selectionAction" type="submit">{korean ? "추가" : "Add"}</button>
            </form>
          ) : null}

          {readOnly ? (
            <p className="selectionReadOnlyNote">
              {korean ? "공개 데모에서는 선택, 비교 탐색, 근거 채팅을 사용할 수 있지만 변경사항 저장은 비활성화됩니다." : "Public demo: selection, comparison browsing, and evidence chat are available; saving changes is disabled."}
            </p>
          ) : null}
          <span className="selectionContext">
            {resultMode === "search" ? (korean ? `“${query}” 검색에서 선택` : `Selection from “${query}”`) : (korean ? "전체 논문 탐색에서 선택" : "Selection from Browse All Papers")}
          </span>
        </aside>
      ) : null}
    </>
  );
}
