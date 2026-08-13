import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MutationFeedback } from "./MutationFeedback";

const messages = {
  saved: { message: "Research state saved." },
  error: { message: "Research state could not be saved.", tone: "error" as const },
};

describe("MutationFeedback", () => {
  it("announces successful mutation feedback as status", () => {
    render(<MutationFeedback feedback="saved" messages={messages} />);

    expect(screen.getByRole("status")).toHaveTextContent("Research state saved.");
  });

  it("announces failed mutation feedback as an alert", () => {
    render(<MutationFeedback feedback="error" messages={messages} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Research state could not be saved.");
  });

  it("does not render unknown feedback values", () => {
    const { container } = render(<MutationFeedback feedback="unknown" messages={messages} />);

    expect(container).toBeEmptyDOMElement();
  });
});
