"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import type { WorkspaceMode } from "@/lib/workspace";

const links = [
  ["/", "Landscape", "01"],
  ["/library", "Library", "02"],
  ["/questions", "Research Questions", "03"],
  ["/compare", "Compare", "04"],
  ["/gap-canvas", "Gap Canvas", "05"],
  ["/chat", "Evidence Chat", "06"],
  ["/imports", "Import", "+"],
] as const;

const bottomLinks = [
  ["/library", "Library", "⌕"],
  ["/questions", "Questions", "Q"],
  ["/chat", "Chat", "↗"],
] as const;

export function Sidebar({ workspaceMode }: { workspaceMode: WorkspaceMode }) {
  const pathname = usePathname() ?? "";
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const currentPage = links.find(([href]) => href === "/" ? pathname === "/" : pathname.startsWith(href))?.[1] ?? "Workspace";
  const readOnly = workspaceMode === "public_demo";

  useEffect(() => {
    if (!mobileOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMobileOpen(false);
      window.requestAnimationFrame(() => mobileMenuButtonRef.current?.focus());
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen]);

  return (
    <>
      <aside className={`sidebar${mobileOpen ? " sidebarMobileOpen" : ""}`}>
        <div className="sidebarTopbar">
          <Link className="brand" href="/" onClick={() => setMobileOpen(false)}>
            <div className="brandMark">A↗</div>
            <div className="brandText">
              <h1 className="brandTitle">AI × MOT Research Lab</h1>
              <p className="brandSubtitle">AI & Management of Technology Research Intelligence</p>
            </div>
          </Link>

          <div className="mobilePageContext">
            <span>{currentPage}</span>
            <small>{readOnly ? "Public demo" : "Personal workspace"}</small>
          </div>

          <button
            className="mobileMenuButton"
            type="button"
            ref={mobileMenuButtonRef}
            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileOpen}
            aria-controls="primary-navigation"
            onClick={() => setMobileOpen((current) => !current)}
          >
            <span />
            <span />
            <span />
          </button>
        </div>

        <nav className="nav" id="primary-navigation" aria-label="Primary navigation">
          <div className="navHeaderRow">
            <p className="navSectionLabel">Workspace</p>
            <span className={`workspaceBadge${readOnly ? " workspaceBadgeReadOnly" : ""}`}>
              {readOnly ? "Public Demo · Read-only" : "Personal Workspace"}
            </span>
          </div>
          {links.map(([href, label, index]) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                className={`navLink${active ? " navLinkActive" : ""}`}
                href={href}
                key={href}
                aria-current={active ? "page" : undefined}
                onClick={() => setMobileOpen(false)}
              >
                <span className="navIndex">{index}</span>
                <span>{label}</span>
                {active ? <span className="navActiveMark" aria-hidden="true">●</span> : null}
              </Link>
            );
          })}
        </nav>

        <div className="sidebarNote">
          <div className="sidebarStatus"><span className="statusDot" /> Evidence-first workspace</div>
          <p>Gap candidates stay hypotheses. Paper claims, system inference, and your notes remain separated.</p>
          {readOnly ? <p><strong>Portfolio mode:</strong> browse and inspect freely; mutations are disabled.</p> : null}
        </div>
      </aside>

      <nav className="mobileBottomNav" aria-label="Quick navigation">
        {bottomLinks.map(([href, label, icon]) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              className={`mobileBottomLink${active ? " mobileBottomLinkActive" : ""}`}
              href={href}
              key={href}
              aria-current={active ? "page" : undefined}
            >
              <span aria-hidden="true">{icon}</span>
              <small>{label}</small>
            </Link>
          );
        })}
        <button
          className="mobileBottomLink"
          type="button"
          aria-label="Open more navigation options"
          aria-expanded={mobileOpen}
          aria-controls="primary-navigation"
          onClick={() => setMobileOpen(true)}
        >
          <span aria-hidden="true">•••</span>
          <small>More</small>
        </button>
      </nav>
    </>
  );
}
