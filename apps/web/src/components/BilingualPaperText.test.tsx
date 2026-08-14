import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { BilingualPaperText } from "./BilingualPaperText";
import { LocalePreferenceProvider } from "./LocalePreference";

describe("BilingualPaperText", () => {
  beforeEach(() => window.localStorage.clear());

  it("switches between the provider abstract and a provenance-tagged Korean localization", () => {
    render(
      <LocalePreferenceProvider>
        <BilingualPaperText
          englishAbstract="English abstract"
          englishKeywords={["AI capability"]}
          englishTitle="English title"
          koreanAbstract="한국어 초록"
          koreanKeywords={["AI 역량"]}
          koreanTitle="한국어 제목"
        />
      </LocalePreferenceProvider>,
    );

    expect(screen.getByText("English abstract")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "한국어" }));
    expect(screen.getByText("한국어 초록")).toBeInTheDocument();
    expect(screen.getByText("AI 역량")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByText("English abstract")).toBeInTheDocument();
  });

  it("does not claim Korean availability before a translation exists", () => {
    render(
      <LocalePreferenceProvider>
        <BilingualPaperText
          englishAbstract="English abstract"
          englishKeywords={[]}
          englishTitle="English title"
          koreanAbstract={null}
          koreanKeywords={[]}
          koreanTitle={null}
        />
      </LocalePreferenceProvider>,
    );

    expect(screen.getByRole("button", { name: "한국어 준비 중" })).toBeDisabled();
  });
});
