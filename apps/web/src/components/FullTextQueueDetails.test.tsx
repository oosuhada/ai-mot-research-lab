import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { FullTextQueueDetails } from "./FullTextQueueDetails";
import { LocalePreferenceProvider } from "./LocalePreference";

const details = {
  claimable: 49_542,
  deferred: 1_684,
  processing: 0,
  completed24h: 1_226,
  boosterEligible: 0,
  boosterCooldown: 663,
  boosterWaiting: 1_100,
};

describe("FullTextQueueDetails", () => {
  beforeEach(() => window.localStorage.clear());

  it("keeps queue classifications hidden until requested and shows one metric per row", () => {
    render(
      <LocalePreferenceProvider>
        <FullTextQueueDetails details={details} />
      </LocalePreferenceProvider>,
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Details" }));

    const dialog = screen.getByRole("dialog", { name: "Full-text queue details" });
    const rows = within(dialog).getAllByRole("term").map((term) => term.parentElement);
    expect(rows).toHaveLength(7);
    expect(rows[0]).toHaveTextContent("Ready49,542");
    expect(rows[1]).toHaveTextContent("retry delay1,684");
    expect(rows[2]).toHaveTextContent("processing0");

    fireEvent.click(within(dialog).getByRole("button", { name: "Close queue details" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
