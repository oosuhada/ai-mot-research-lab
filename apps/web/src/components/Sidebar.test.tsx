import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("exposes the core research workflows", () => {
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: /Landscape/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Library/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Research Questions/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Compare/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Gap Canvas/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Evidence Chat/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Import/ })).toBeInTheDocument();
  });
});

