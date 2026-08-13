import { fireEvent, render, screen, within } from "@testing-library/react";
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

  it("pins and collapses the desktop sidebar without the legacy brand mark", () => {
    const { container } = render(<Sidebar workspaceMode="public_demo" />);
    const sidebar = screen.getByRole("complementary");
    const toggle = screen.getByRole("button", { name: "Pin navigation sidebar open" });

    expect(container.querySelector(".brandMark")).not.toBeInTheDocument();
    expect(sidebar).not.toHaveClass("sidebarPinnedOpen");

    fireEvent.click(toggle);
    expect(sidebar).toHaveClass("sidebarPinnedOpen");
    expect(screen.getByRole("button", { name: "Collapse navigation sidebar" })).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(screen.getByRole("button", { name: "Collapse navigation sidebar" }));
    expect(sidebar).not.toHaveClass("sidebarPinnedOpen");
  });
});
