"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";

import type { ResearchQuestion } from "@/lib/api";
import { useLocalePreference } from "./LocalePreference";

type ResearchContextValue = {
  activeQuestionId: string | null;
  activeQuestion: ResearchQuestion | null;
  setActiveQuestionId: (questionId: string | null) => void;
};

const STORAGE_KEY = "ai-mot-research-lab:current-question";
const STORAGE_EVENT = "ai-mot-research-lab:current-question-change";
const ResearchContext = createContext<ResearchContextValue | null>(null);

export function ResearchContextProvider({
  questions,
  children,
}: {
  questions: ResearchQuestion[];
  children: React.ReactNode;
}) {
  const subscribe = useCallback((onStoreChange: () => void) => {
    window.addEventListener("storage", onStoreChange);
    window.addEventListener(STORAGE_EVENT, onStoreChange);
    return () => {
      window.removeEventListener("storage", onStoreChange);
      window.removeEventListener(STORAGE_EVENT, onStoreChange);
    };
  }, []);

  const storedQuestionId = useSyncExternalStore(
    subscribe,
    () => window.localStorage.getItem(STORAGE_KEY),
    () => null,
  );
  const activeQuestionId = storedQuestionId && questions.some((question) => question.id === storedQuestionId)
    ? storedQuestionId
    : null;

  const activeQuestion = useMemo(
    () => questions.find((question) => question.id === activeQuestionId) ?? null,
    [activeQuestionId, questions],
  );

  function setActiveQuestionId(questionId: string | null) {
    const normalizedId = questionId && questions.some((question) => question.id === questionId) ? questionId : null;
    if (normalizedId) {
      window.localStorage.setItem(STORAGE_KEY, normalizedId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    window.dispatchEvent(new Event(STORAGE_EVENT));
  }

  return (
    <ResearchContext.Provider value={{ activeQuestionId, activeQuestion, setActiveQuestionId }}>
      {children}
    </ResearchContext.Provider>
  );
}

export function ResearchContextBar({ questions }: { questions: ResearchQuestion[] }) {
  const { activeQuestionId, activeQuestion, setActiveQuestionId } = useResearchContext();
  const pathname = usePathname() ?? "";
  const { locale } = useLocalePreference();
  const korean = locale === "ko";

  if (pathname === "/" || pathname.startsWith("/imports")) return null;

  return (
    <section className="researchContextBar" aria-label="Current research question">
      <div className="researchContextCopy">
        <span className="cardKicker">{korean ? "현재 연구 질문" : "Current research question"}</span>
        <strong>{activeQuestion?.title ?? (korean ? "활성 연구 질문 없음" : "No active question")}</strong>
        <small>{korean ? "라이브러리, 논문 비교, 근거 채팅을 이동하는 동안 하나의 질문을 중심에 유지하세요." : "Keep one question in view while moving through Library, Compare, and Evidence Chat."}</small>
      </div>
      <div className="researchContextControls">
        <label className="srOnly" htmlFor="current-research-question">Current research question</label>
        <select
          className="select"
          id="current-research-question"
          value={activeQuestionId ?? ""}
          disabled={!questions.length}
          onChange={(event) => setActiveQuestionId(event.target.value || null)}
        >
          <option value="">{questions.length ? (korean ? "활성 연구 질문 없음" : "No active question") : (korean ? "아직 연구 질문이 없습니다" : "No research questions yet")}</option>
          {questions.map((question) => (
            <option value={question.id} key={question.id}>{question.title}</option>
          ))}
        </select>
        {activeQuestion ? (
          <div className="researchContextActions">
            <Link className="textLink" href={`/questions/${activeQuestion.id}`}>{korean ? "질문 열기" : "Open question"}</Link>
            <Link className="textLink" href={`/chat?scope_key=research_question:${activeQuestion.id}`}>{korean ? "이 질문으로 묻기 →" : "Ask this question →"}</Link>
          </div>
        ) : (
          <div className="researchContextActions">
            <Link className="textLink" href="/questions">{questions.length ? (korean ? "연구 질문 선택하기 →" : "Choose a research question →") : (korean ? "연구 질문 만들기 또는 살펴보기 →" : "Create or inspect research questions →")}</Link>
          </div>
        )}
      </div>
    </section>
  );
}

export function useResearchContext(): ResearchContextValue {
  const context = useContext(ResearchContext);
  if (!context) {
    throw new Error("useResearchContext must be used within ResearchContextProvider");
  }
  return context;
}
