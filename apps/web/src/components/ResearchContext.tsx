"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";

import type { ResearchQuestion } from "@/lib/api";

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

  if (pathname === "/" || pathname.startsWith("/imports")) return null;

  return (
    <section className="researchContextBar" aria-label="Current research question">
      <div className="researchContextCopy">
        <span className="cardKicker">Current research question</span>
        <strong>{activeQuestion?.title ?? "No active question"}</strong>
        <small>Keep one question in view while moving through Library, Compare, and Evidence Chat.</small>
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
          <option value="">{questions.length ? "No active question" : "No research questions yet"}</option>
          {questions.map((question) => (
            <option value={question.id} key={question.id}>{question.title}</option>
          ))}
        </select>
        {activeQuestion ? (
          <div className="researchContextActions">
            <Link className="textLink" href={`/questions/${activeQuestion.id}`}>Open question</Link>
            <Link className="textLink" href={`/chat?scope_key=research_question:${activeQuestion.id}`}>Ask this question →</Link>
          </div>
        ) : (
          <div className="researchContextActions">
            <Link className="textLink" href="/questions">{questions.length ? "Choose a research question →" : "Create or inspect research questions →"}</Link>
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
