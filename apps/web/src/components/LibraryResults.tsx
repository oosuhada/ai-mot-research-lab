"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { linkSelectedPapersAction } from "@/app/library/actions";
import { useResearchContext } from "@/components/ResearchContext";
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
                      <span>{paper.venue_name ?? paper.work_type ?? "Venue unknown"}</span>
                      <span>{paper.is_oa ? "open access" : "access unknown"}</span>
                    </p>
                    <h3><Link href={`/library/${paper.id}`}>{paper.title}</Link></h3>
                  </div>

                  {paper.matched_excerpt ? (
                    <blockquote className="scholarlyAnnotation">{paper.matched_excerpt}</blockquote>
                  ) : paper.abstract ? (
                    <p className="scholarlyAbstract">{paper.abstract}</p>
                  ) : (
                    <p className="scholarlyAbstract scholarlyAbstractMissing">No abstract is available for this record.</p>
                  )}

                  <div className="scholarlyEntryActions">
                    <Link className="textLink" href={`/library/${paper.id}`}>Read research record →</Link>
                    <button className="textButtonInline" type="button" onClick={() => togglePaper(paper.id)}>
                      {selected ? "Remove from selection" : "Add to research selection"}
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
                    {selected ? "✓ Selected" : "+ Select"}
                  </button>
                  <dl>
                    <div><dt>Citations</dt><dd>{paper.citation_count}</dd></div>
                    {resultMode === "search" ? <div><dt>Hybrid score</dt><dd>{paper.fused_score.toFixed(4)}</dd></div> : null}
                    {resultMode === "search" ? <div><dt>Locator</dt><dd>{paper.matched_locator ?? paper.matched_source.replaceAll("_", " ")}</dd></div> : <div><dt>Order</dt><dd>local import</dd></div>}
                  </dl>
                  {resultMode === "search" ? (
                    <details className="retrievalWhy">
                      <summary>Retrieval note</summary>
                      <div className="retrievalDiagnostics">
                        <span>Keyword rank {paper.lexical_rank ? `#${paper.lexical_rank}` : "—"}</span>
                        <span>Meaning rank {paper.semantic_rank ? `#${paper.semantic_rank}` : "—"}</span>
                        {paper.rerank_score !== null ? <span>Rerank {paper.rerank_score.toFixed(4)}</span> : null}
                        <span>Matched in {paper.matched_source.replaceAll("_", " ")}</span>
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
            <strong>{selectedIds.length} paper{selectedIds.length === 1 ? "" : "s"} selected</strong>
            <span>{selectedIds.length >= 6 ? "Selection limit reached" : "Choose up to 6 papers"}</span>
          </div>
          <div className="selectionTrayActions">
            {selectedIds.length >= 2 ? (
              <Link className="selectionAction" href={`/compare?papers=${encodedPaperIds}`}>Compare</Link>
            ) : (
              <span className="selectionAction selectionActionDisabled">Compare · select 2+</span>
            )}
            <Link className="selectionAction" href={`/chat?scope=papers&ids=${encodedPaperIds}`}>Ask with evidence</Link>
            <button className="selectionClear" type="button" onClick={() => setSelectedIds([])}>Clear</button>
          </div>

          {!readOnly && questions.length ? (
            <form action={linkSelectedPapersAction} className="selectionQuestionForm">
              <input type="hidden" name="paper_ids" value={paperIds} />
              <input type="hidden" name="return_to" value={returnTo} />
              <label htmlFor="selection-question">Add to research question</label>
              <select
                className="select"
                id="selection-question"
                name="question_id"
                required
                value={activeQuestionId ?? ""}
                onChange={(event) => setActiveQuestionId(event.target.value || null)}
              >
                <option value="" disabled>Choose a question…</option>
                {questions.map((question) => (
                  <option value={question.id} key={question.id}>{question.title}</option>
                ))}
              </select>
              <button className="selectionAction" type="submit">Add</button>
            </form>
          ) : null}

          {readOnly ? (
            <p className="selectionReadOnlyNote">
              Public demo: selection, comparison browsing, and evidence chat are available; saving changes is disabled.
            </p>
          ) : null}
          <span className="selectionContext">
            {resultMode === "search" ? `Selection from “${query}”` : "Selection from Browse All Papers"}
          </span>
        </aside>
      ) : null}
    </>
  );
}
