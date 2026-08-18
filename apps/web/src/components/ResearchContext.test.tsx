import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { ResearchQuestion } from "@/lib/api";

import { ResearchContextBar, ResearchContextProvider } from "./ResearchContext";

const question: ResearchQuestion = {
  id: "11111111-1111-1111-1111-111111111111",
  title: "How does AI capability shape innovation performance?",
  question_text: "How does AI capability shape innovation performance?",
  motivation: null,
  scope_notes: null,
  importance_notes: null,
  evidence_status: "insufficient_evidence",
  uncertainty_notes: null,
  status: "active",
  papers: [],
  saved_searches: [],
  comparison_sets: [],
  gap_analyses: [],
  notes: [],
  directions: [],
  design: null,
  synthesis: null,
  workflow: null,
  created_at: "2026-08-23T00:00:00Z",
  updated_at: "2026-08-23T00:00:00Z",
};

describe("ResearchContext", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("keeps the active research question across remounts", () => {
    const firstRender = render(
      <ResearchContextProvider questions={[question]}>
        <ResearchContextBar questions={[question]} />
      </ResearchContextProvider>,
    );

    const select = screen.getByRole("combobox", { name: "Current research question" });
    fireEvent.change(select, { target: { value: question.id } });
    expect(select).toHaveValue(question.id);

    firstRender.unmount();

    render(
      <ResearchContextProvider questions={[question]}>
        <ResearchContextBar questions={[question]} />
      </ResearchContextProvider>,
    );

    expect(screen.getByRole("combobox", { name: "Current research question" })).toHaveValue(question.id);
    expect(screen.getByRole("link", { name: "Ask this question →" })).toHaveAttribute(
      "href",
      `/chat?scope_key=research_question:${question.id}`,
    );
  });
});
