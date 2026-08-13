"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { linkSelectedPapersAction } from "@/app/library/actions";
import type { ResearchQuestion, SearchItem } from "@/lib/api";

type LibraryResultsProps = {
  items: SearchItem[];
  query: string;
  questions: ResearchQuestion[];
  readOnly: boolean;
};

export function LibraryResults({ items, query, questions, readOnly }: LibraryResultsProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [visibleCount, setVisibleCount] = useState(Math.min(10, items.length));

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
      <div className="paperResultList">
        {items.slice(0, visibleCount).map((paper) => {
          const selected = selectedSet.has(paper.id);
          return (
            <article className={`paperResult${selected ? " paperResultSelected" : ""}`} key={paper.id}>
              <div className="paperResultTopline">
                <div className="paperMeta">
                  <span>{paper.publication_year ?? "Year unknown"}</span>
                  <span>{paper.work_type ?? "Research work"}</span>
                  <span>{paper.citation_count} citations</span>
                  <span>{paper.is_oa ? "Open access" : "Access unknown / closed"}</span>
                </div>
                <button
                  className={`paperSelectButton${selected ? " paperSelectButtonActive" : ""}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => togglePaper(paper.id)}
                >
                  {selected ? "✓ Selected" : "+ Select"}
                </button>
              </div>

              <h3><Link href={`/library/${paper.id}`}>{paper.title}</Link></h3>
              {paper.matched_excerpt ? (
                <p className="paperExcerpt">{paper.matched_excerpt}</p>
              ) : paper.abstract ? (
                <p className="paperExcerpt">{paper.abstract}</p>
              ) : (
                <p className="paperExcerpt paperExcerptMissing">No abstract is available for this record.</p>
              )}

              <div className="resultActions">
                <Link className="textLink" href={`/library/${paper.id}`}>Open research record →</Link>
                <button
                  className="textButtonInline"
                  type="button"
                  onClick={() => togglePaper(paper.id)}
                >
                  {selected ? "Remove from selection" : "Add to research selection"}
                </button>
              </div>

              <details className="retrievalWhy">
                <summary>Why this result?</summary>
                <div className="retrievalDiagnostics">
                  <span>Keyword rank {paper.lexical_rank ? `#${paper.lexical_rank}` : "—"}</span>
                  <span>Meaning rank {paper.semantic_rank ? `#${paper.semantic_rank}` : "—"}</span>
                  <span>Combined score {paper.fused_score.toFixed(4)}</span>
                  {paper.rerank_score !== null ? <span>Rerank {paper.rerank_score.toFixed(4)}</span> : null}
                  <span>Matched in {paper.matched_source.replaceAll("_", " ")}</span>
                  {paper.matched_locator ? <span>{paper.matched_locator}</span> : null}
                </div>
              </details>
            </article>
          );
        })}
      </div>

      {visibleCount < items.length ? (
        <button
          className="loadMoreButton"
          type="button"
          onClick={() => setVisibleCount((current) => Math.min(current + 10, items.length))}
        >
          Load {Math.min(10, items.length - visibleCount)} more results
        </button>
      ) : null}

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
              <label htmlFor="selection-question">Add to research question</label>
              <select className="select" id="selection-question" name="question_id" required defaultValue="">
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
          <span className="selectionContext">Selection from “{query}”</span>
        </aside>
      ) : null}
    </>
  );
}
