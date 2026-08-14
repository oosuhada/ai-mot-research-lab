"use client";

import { useLocalePreference } from "./LocalePreference";

export function BilingualPaperText({
  englishTitle,
  englishAbstract,
  englishKeywords,
  koreanTitle,
  koreanAbstract,
  koreanKeywords,
}: {
  englishTitle: string;
  englishAbstract: string | null;
  englishKeywords: string[];
  koreanTitle: string | null;
  koreanAbstract: string | null;
  koreanKeywords: string[];
}) {
  const { locale, setLocale } = useLocalePreference();
  const koreanReady = Boolean(koreanAbstract);
  const showKorean = locale === "ko" && koreanReady;
  const title = showKorean ? koreanTitle ?? englishTitle : englishTitle;
  const abstract = showKorean ? koreanAbstract : englishAbstract;
  const keywords = showKorean && koreanKeywords.length ? koreanKeywords : englishKeywords;

  return (
    <div className="bilingualPaperText">
      <div className="translationToolbar">
        <div>
          <strong>{showKorean ? "한국어 번역" : "English source"}</strong>
          <span>{showKorean ? "번역본 · 원문 provenance 유지" : "Provider-supplied abstract"}</span>
        </div>
        <div className="translationToggle" aria-label="Abstract language">
          <button aria-pressed={!showKorean} onClick={() => setLocale("en")} type="button">English</button>
          <button
            aria-pressed={showKorean}
            disabled={!koreanReady}
            onClick={() => setLocale("ko")}
            title={koreanReady ? "한국어 번역 보기" : "한국어 번역이 아직 준비되지 않았습니다"}
            type="button"
          >
            {koreanReady ? "한국어" : "한국어 준비 중"}
          </button>
        </div>
      </div>
      {showKorean && koreanTitle ? <h3 className="translatedPaperTitle">{title}</h3> : null}
      <p className="paperDocumentLead">{abstract ?? "No abstract is available in the local metadata record."}</p>
      {keywords.length ? (
        <div className="translationKeywords" aria-label={showKorean ? "한국어 키워드" : "English keywords"}>
          {keywords.map((keyword) => <span className="pill" key={keyword}>{keyword}</span>)}
        </div>
      ) : null}
    </div>
  );
}
