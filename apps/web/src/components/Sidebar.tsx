"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { LanguageSwitch, useLocalePreference } from "./LocalePreference";
import type { WorkspaceMode } from "@/lib/workspace";

const links = [
  ["/", "Landscape", "연구 지형", "01"],
  ["/library", "Library", "논문 라이브러리", "02"],
  ["/questions", "Research Questions", "연구 질문", "03"],
  ["/compare", "Compare", "논문 비교", "04"],
  ["/gap-canvas", "Gap Canvas", "연구 공백 캔버스", "05"],
  ["/chat", "Evidence Chat", "근거 채팅", "06"],
  ["/whats-new", "What’s New", "새로운 MOT 논문", "07"],
  ["/opportunities", "Research Opportunities", "연구 기회", "08"],
  ["/imports", "Import", "가져오기", "09"],
] as const;

const bottomLinks = [
  ["/library", "Library", "⌕"],
  ["/questions", "Questions", "Q"],
  ["/chat", "Chat", "↗"],
] as const;

export function Sidebar({ workspaceMode }: { workspaceMode: WorkspaceMode }) {
  const pathname = usePathname() ?? "";
  const { locale } = useLocalePreference();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [desktopOpen, setDesktopOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const currentLink = links.find(([href]) => href === "/" ? pathname === "/" : pathname.startsWith(href));
  const currentPage = currentLink ? currentLink[locale === "ko" ? 2 : 1] : "Workspace";
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
      <aside className={`sidebar${mobileOpen ? " sidebarMobileOpen" : ""}${desktopOpen ? " sidebarPinnedOpen" : ""}`}>
        <div className="sidebarTopbar">
          <Link className="brand" href="/" onClick={() => setMobileOpen(false)}>
            <div className="brandText">
              <h1 className="brandTitle">AI × MOT Research Lab</h1>
              <p className="brandSubtitle">AI & Management of Technology Research Intelligence</p>
            </div>
          </Link>

          <button
            className="sidebarToggleButton"
            type="button"
            aria-label={desktopOpen ? "Collapse navigation sidebar" : "Pin navigation sidebar open"}
            aria-expanded={desktopOpen}
            aria-controls="primary-navigation"
            onClick={(event) => {
              setDesktopOpen((current) => !current);
              if (desktopOpen && event.detail > 0) event.currentTarget.blur();
            }}
          >
            <span aria-hidden="true">{desktopOpen ? "←" : "→"}</span>
          </button>

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
          {links.map(([href, label, koreanLabel, index]) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            const displayLabel = locale === "ko" ? koreanLabel : label;
            return (
              <Link
                className={`navLink${active ? " navLinkActive" : ""}`}
                href={href}
                key={href}
                aria-label={displayLabel}
                aria-current={active ? "page" : undefined}
                onClick={() => setMobileOpen(false)}
              >
                <span className="navIndex">{index}</span>
                <span className="navLabel">{displayLabel}</span>
                {active ? <span className="navActiveMark" aria-hidden="true">●</span> : null}
              </Link>
            );
          })}
          <div className="mobileLanguageSwitch">
            <span>Display language · 표시 언어</span>
            <LanguageSwitch />
          </div>
        </nav>

        <div className="sidebarNote">
          <LanguageSwitch compact />
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
