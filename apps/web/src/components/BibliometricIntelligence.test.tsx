import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { BibliometricRelations, LandscapeAxis } from "@/lib/api";

import { BibliometricIntelligence } from "./BibliometricIntelligence";
import { LocalePreferenceProvider } from "./LocalePreference";

function axis(
  slug: string,
  displayName: string,
  paperCount: number,
  parentSlug: string | null = null,
): LandscapeAxis {
  return {
    slug,
    display_name: displayName,
    paper_count: paperCount,
    abstract_paper_count: paperCount,
    full_text_paper_count: Math.floor(paperCount * 0.5),
    oa_paper_count: Math.floor(paperCount * 0.7),
    parent_slug: parentSlug,
    years: [
      { year: 2022, paper_count: Math.max(1, Math.floor(paperCount * 0.12)) },
      { year: 2023, paper_count: Math.max(1, Math.floor(paperCount * 0.16)) },
      { year: 2024, paper_count: Math.max(1, Math.floor(paperCount * 0.2)) },
      { year: 2025, paper_count: Math.max(1, Math.floor(paperCount * 0.28)) },
      { year: 2026, paper_count: Math.max(1, Math.floor(paperCount * 0.1)) },
    ],
    top_methodologies: [],
  };
}

const governance = axis("ai-governance", "AI Governance", 120);
const adoption = axis("ai-adoption", "AI Adoption", 100);
const privacy = axis("privacy-risk", "Privacy and risk", 45, governance.slug);
const oversight = axis("human-oversight", "Human oversight", 38, governance.slug);
const implementation = axis("implementation", "Implementation", 52, adoption.slug);

const relations: BibliometricRelations = {
  generated_at: "2026-09-12T10:00:00Z",
  recent_window: "2024–2025",
  prior_window: "2022–2023",
  complete_through_year: 2025,
  observed_latest_year: 2026,
  latest_year_is_partial: true,
  corpus_total_papers: 230,
  total_papers: 220,
  excluded_non_scholarly: 10,
  future_dated_records: 2,
  full_text_papers: 110,
  axes: [governance, adoption],
  subaxes: [privacy, oversight, implementation],
  years: [
    { year: 2022, paper_count: 40 },
    { year: 2023, paper_count: 50 },
    { year: 2024, paper_count: 60 },
    { year: 2025, paper_count: 80 },
    { year: 2026, paper_count: 30 },
  ],
  top_authors: [
    { name: "Researcher A", paper_count: 30, recent_count: 14, prior_count: 8, growth_pct: 75 },
    { name: "Researcher B", paper_count: 28, recent_count: 9, prior_count: 10, growth_pct: -10 },
  ],
  top_institutions: [
    { name: "Institute A", paper_count: 50, recent_count: 22, prior_count: 15, growth_pct: 46.7 },
  ],
  top_venues: [
    { name: "Journal A", paper_count: 40, recent_count: 17, prior_count: 12, growth_pct: 41.7 },
  ],
  topic_nodes: [
    {
      id: "topic-privacy",
      slug: privacy.slug,
      label: privacy.display_name,
      count: 45,
      recent_count: 21,
      country_code: null,
      group: governance.slug,
      group_label: governance.display_name,
      kind: "topic",
    },
    {
      id: "topic-oversight",
      slug: oversight.slug,
      label: oversight.display_name,
      count: 38,
      recent_count: 18,
      country_code: null,
      group: governance.slug,
      group_label: governance.display_name,
      kind: "topic",
    },
  ],
  topic_edges: [
    {
      source: "topic-privacy",
      target: "topic-oversight",
      weight: 20,
      strength: 0.3175,
      kind: "topic_cooccurrence",
    },
  ],
  institution_nodes: [
    {
      id: "institution-a",
      slug: null,
      label: "Institute A",
      count: 50,
      recent_count: 22,
      country_code: "KR",
      group: null,
      group_label: null,
      kind: "institution",
    },
  ],
  institution_edges: [],
  patent_total: 0,
  patent_years: [],
  patent_jurisdictions: [],
  patent_applicants: [],
  patent_cpc: [],
  paper_patent_bridge: [],
  caveats: ["Test caveat"],
};

describe("BibliometricIntelligence", () => {
  beforeEach(() => window.localStorage.clear());

  it("keeps partial-year data out of growth comparisons and supports research drill-down", () => {
    render(
      <LocalePreferenceProvider>
        <BibliometricIntelligence relations={relations} signals={null} />
      </LocalePreferenceProvider>,
    );

    expect(screen.getByText("Complete through").closest("article")).toHaveTextContent("2025");
    expect(screen.getByText("Latest observed").closest("article")).toHaveTextContent("partial year");
    expect(screen.getByText("Analysis scope").closest("article")).toHaveTextContent("220 / 230");
    expect(screen.getByText("Analysis scope").closest("article")).toHaveTextContent("10 non-scholarly excluded");
    expect(screen.getByText("Latest observed").closest("article")).toHaveTextContent("2 future-dated excluded");
    expect(screen.getByText("Growth baseline").closest("article")).toHaveTextContent("2024–2025");
    expect(screen.getByText("Growth baseline").closest("article")).toHaveTextContent("vs 2022–2023");

    expect(screen.getByRole("button", { name: /Privacy and risk: 45/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Privacy and risk: 45/i }));
    expect(screen.getByRole("link", { name: "Open papers in this topic →" })).toHaveAttribute(
      "href",
      "/library?view=browse&axis=privacy-risk",
    );
    expect(screen.getByText(/20 · 31.8%/)).toBeInTheDocument();

    const momentum = screen.getByRole("button", { name: "Recent momentum" });
    fireEvent.click(momentum);
    expect(momentum).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("+75.0%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /AI Governance/i }));
    expect(screen.getByRole("link", { name: /Privacy and risk/i })).toHaveAttribute(
      "href",
      "/library?view=browse&axis=privacy-risk",
    );
    expect(screen.getByRole("link", { name: /Human oversight/i })).toBeInTheDocument();
  });
});
