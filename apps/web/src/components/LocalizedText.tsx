"use client";

import { useLocalePreference } from "./LocalePreference";

export function LocalizedText({ en, ko }: { en: React.ReactNode; ko: React.ReactNode }) {
  const { locale } = useLocalePreference();
  return <>{locale === "ko" ? ko : en}</>;
}

export function LocalizedTaxonomyText({ label }: { label: string }) {
  const { locale } = useLocalePreference();
  return <>{localizeResearchLabel(label, locale)}</>;
}

export function LocalizedHomeSearch() {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  return (
    <form className="researchThreadSearch" action="/library" method="get">
      <label htmlFor="thread-search">{korean ? "문헌 탐색 시작하기" : "Start a literature thread"}</label>
      <div>
        <input
          id="thread-search"
          name="q"
          placeholder={korean ? "AI 역량 → 조직 변화 → 혁신 성과" : "AI capability → organizational change → innovation performance"}
        />
        <input type="hidden" name="mode" value="hybrid" />
        <button type="submit">{korean ? "근거 추적하기 →" : "Trace evidence →"}</button>
      </div>
    </form>
  );
}

const RESEARCH_LABELS_KO: Record<string, string> = {
  "AI adoption and business value": "AI 도입과 비즈니스 가치",
  "Technology and innovation management": "기술·혁신 경영",
  "AI-enabled organizational change": "AI 기반 조직 변화",
  "Industrial AI and smart operations": "산업 AI와 스마트 운영",
  "AI governance and responsible deployment": "AI 거버넌스와 책임 있는 도입",
  "Agentic systems and enterprise workflows": "에이전틱 시스템과 기업 워크플로",
  Survey: "설문 연구",
  "Systematic Review": "체계적 문헌고찰",
  Qualitative: "질적 연구",
  Experiment: "실험 연구",
  "Case Study": "사례 연구",
  Conceptual: "개념 연구",
  Simulation: "시뮬레이션",
  "Panel Longitudinal": "패널·종단 연구",
  Econometric: "계량경제 연구",
};

export function localizeResearchLabel(label: string, locale: "en" | "ko"): string {
  return locale === "ko" ? RESEARCH_LABELS_KO[label] ?? label : label;
}
