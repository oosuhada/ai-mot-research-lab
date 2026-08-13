import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Sidebar } from "./Sidebar";

describe("Sidebar", () => {
  it("exposes the core research workflows", () => {
    render(<Sidebar workspaceMode="personal" />);

    const navigation = within(screen.getByRole("navigation", { name: "Primary navigation" }));
    expect(navigation.getByRole("link", { name: /Landscape/ })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: /Library/ })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: /Research Questions/ })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: /Compare/ })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: /Gap Canvas/ })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: /Evidence Chat/ })).toBeInTheDocument();
    expect(navigation.getByRole("link", { name: /Import/ })).toBeInTheDocument();
  });
});

