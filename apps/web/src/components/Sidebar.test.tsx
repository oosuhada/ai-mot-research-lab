import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("exposes the core research workflows", () => {
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: "Research Landscape" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Paper Library" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Compare Papers" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gap Canvas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evidence Chat" })).toBeInTheDocument();
  });
});

