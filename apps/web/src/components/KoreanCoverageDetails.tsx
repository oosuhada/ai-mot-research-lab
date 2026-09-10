"use client";

import { useEffect, useRef, useState } from "react";

import { useLocalePreference } from "./LocalePreference";

type KoreanDetails = {
  completed: number;
  title: number;
  abstract: number;
  withFullText: number;
  withoutFullText: number;
  fullTextWithoutKorean: number;
};

export function KoreanCoverageDetails({ details }: { details: KoreanDetails }) {
  const { locale } = useLocalePreference();
  const [open, setOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const korean = locale === "ko";

  useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const rows = korean
    ? [
        ["한글 localization 완료", details.completed],
        ["제목 번역", details.title],
        ["초록 번역", details.abstract],
        ["한글 초록 + 전문 원문 확보", details.withFullText],
        ["한글 번역만 있고 전문 없음", details.withoutFullText],
        ["전문은 있으나 한글 번역 없음", details.fullTextWithoutKorean],
      ]
    : [
        ["Korean localization completed", details.completed],
        ["Title translated", details.title],
        ["Abstract translated", details.abstract],
        ["Korean abstract + full-text source", details.withFullText],
        ["Korean only, no full text", details.withoutFullText],
        ["Full text without Korean", details.fullTextWithoutKorean],
      ];

  return (
    <>
      <button
        aria-expanded={open}
        aria-haspopup="dialog"
        className="queueDetailsButton"
        onClick={() => setOpen(true)}
        type="button"
      >
        {korean ? "상세" : "Details"}
      </button>
      {open ? (
        <div className="queueDetailsBackdrop" onClick={() => setOpen(false)}>
          <section
            aria-labelledby="korean-coverage-details-title"
            aria-modal="true"
            className="queueDetailsModal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <header>
              <div>
                <span>{korean ? "한국어" : "Korean"}</span>
                <h2 id="korean-coverage-details-title">
                  {korean ? "한글 번역 상세 분류" : "Korean localization details"}
                </h2>
              </div>
              <button
                aria-label={korean ? "상세 창 닫기" : "Close Korean details"}
                className="queueDetailsClose"
                onClick={() => setOpen(false)}
                ref={closeButtonRef}
                type="button"
              >
                ×
              </button>
            </header>
            <dl>
              {rows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{Number(value).toLocaleString()}</dd>
                </div>
              ))}
            </dl>
            <p className="queueDetailsNote">
              {korean
                ? "현재 DB는 제목·초록·키워드 localization을 추적합니다. ‘전문 원문 확보’는 번역된 전문이 아니라, 같은 논문에 full-text evidence chunk가 있다는 뜻입니다."
                : "The database currently tracks title, abstract, and keyword localization. Full-text source means evidence chunks exist for the same paper; it does not claim full-text translation."}
            </p>
          </section>
        </div>
      ) : null}
    </>
  );
}
