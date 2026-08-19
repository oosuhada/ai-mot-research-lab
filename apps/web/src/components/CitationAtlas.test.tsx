import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { LandscapeAxis } from "@/lib/api";

import { CitationAtlas } from "./CitationAtlas";
import { LocalePreferenceProvider } from "./LocalePreference";

const axis = (
  slug: string,
  displayName: string,
  paperCount: number,
  fullTextCount: number,
): LandscapeAxis => ({
  slug,
  display_name: displayName,
  paper_count: paperCount,
  abstract_paper_count: Math.max(fullTextCount, paperCount - 8),
  full_text_paper_count: fullTextCount,
  oa_paper_count: Math.floor(paperCount * 0.7),
  parent_slug: null,
  years: [
    { year: 2025, paper_count: Math.floor(paperCount * 0.35) },
    { year: 2026, paper_count: Math.floor(paperCount * 0.5) },
  ],
  top_methodologies: [
    { slug: "methodology-survey", display_name: "Survey", paper_count: Math.floor(paperCount * 0.2) },
  ],
});

describe("CitationAtlas", () => {
  beforeEach(() => window.localStorage.clear());

  it("turns the corpus overview into an evidence-depth inspector with real drill-down actions", () => {
    const adoption = axis("ai-adoption-business-value", "AI adoption and business value", 100, 12);
    const governance = axis("ai-governance-responsible-deployment", "AI governance and responsible deployment", 60, 30);
    const readiness: LandscapeAxis = {
      ...axis("organizational-readiness", "Organizational readiness", 28, 8),
      parent_slug: adoption.slug,
    };

    render(
      <LocalePreferenceProvider>
        <CitationAtlas
          axes={[adoption, governance]}
          subaxes={[readiness]}
          years={[{ year: 2025, paper_count: 90 }, { year: 2026, paper_count: 130 }]}
          totalPapers={160}
          coverage={{
            total_records: 160,
            metadata_only: 10,
            abstract_ready: 150,
            full_text_ready: 42,
            full_text_queued: 12,
            full_text_restricted: 0,
            translated_ko: 20,
            expansion_target_total: 100000,
            expansion_progress_pct: 0.16,
            expansion_fetched_total: 420,
            expansion_accepted_total: 260,
            expansion_inserted_total: 160,
            expansion_updated_total: 100,
          }}
        />
      </LocalePreferenceProvider>,
    );

    expect(screen.queryByRole("button", { name: "Zoom out" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AI adoption and business value, 100 papers/i })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /AI governance and responsible deployment, 60 papers/i }));
    expect(screen.getByRole("link", { name: "Explore papers →" })).toHaveAttribute(
      "href",
      "/library?view=browse&axis=ai-governance-responsible-deployment",
    );

    fireEvent.click(screen.getByRole("button", { name: /AI adoption and business value, 100 papers/i }));
    expect(screen.getByRole("button", { name: "← All research axes" })).toBeInTheDocument();
    expect(screen.getByText("compare subareas · keyword taxonomy may overlap")).toBeInTheDocument();
    expect(screen.queryByText("Drill into subareas")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Organizational readiness, 28 papers/i }));
    expect(screen.getByRole("link", { name: "Explore papers →" })).toHaveAttribute(
      "href",
      "/library?view=browse&axis=organizational-readiness",
    );

    fireEvent.click(screen.getByRole("button", { name: "← All research axes" }));
    expect(screen.getByRole("button", { name: /AI governance and responsible deployment, 60 papers/i })).toBeInTheDocument();
  });
});
