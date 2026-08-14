"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Pin, PinOff } from "lucide-react";
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
  ["/library", "Library", "라이브러리", "⌕"],
  ["/questions", "Questions", "질문", "Q"],
  ["/chat", "Chat", "채팅", "↗"],
] as const;

export function Sidebar({
  workspaceMode,
  desktopOpen: controlledDesktopOpen,
  onDesktopOpenChange,
}: {
  workspaceMode: WorkspaceMode;
  desktopOpen?: boolean;
  onDesktopOpenChange?: (open: boolean) => void;
}) {
  const pathname = usePathname() ?? "";
  const { locale } = useLocalePreference();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [internalDesktopOpen, setInternalDesktopOpen] = useState(false);
  const desktopOpen = controlledDesktopOpen ?? internalDesktopOpen;
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const currentLink = links.find(([href]) => href === "/" ? pathname === "/" : pathname.startsWith(href));
  const korean = locale === "ko";
  const currentPage = currentLink ? currentLink[korean ? 2 : 1] : korean ? "워크스페이스" : "Workspace";
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
            aria-label={desktopOpen ? "Unpin navigation sidebar" : "Pin navigation sidebar"}
            aria-pressed={desktopOpen}
            aria-expanded={desktopOpen}
            aria-controls="primary-navigation"
            title={desktopOpen ? "Unpin sidebar" : "Pin sidebar open"}
            onClick={(event) => {
              const nextOpen = !desktopOpen;
              if (onDesktopOpenChange) onDesktopOpenChange(nextOpen);
              else setInternalDesktopOpen(nextOpen);
              if (desktopOpen && event.detail > 0) event.currentTarget.blur();
            }}
          >
            {desktopOpen
              ? <Pin aria-hidden="true" size={17} strokeWidth={2} />
              : <PinOff aria-hidden="true" size={17} strokeWidth={2} />}
          </button>

          <div className="mobilePageContext">
            <span>{currentPage}</span>
            <small>{readOnly ? (korean ? "공개 데모" : "Public demo") : (korean ? "개인 워크스페이스" : "Personal workspace")}</small>
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
            <p className="navSectionLabel">{korean ? "워크스페이스" : "Workspace"}</p>
            <span className={`workspaceBadge${readOnly ? " workspaceBadgeReadOnly" : ""}`}>
              {readOnly ? (korean ? "공개 데모 · 읽기 전용" : "Public Demo · Read-only") : (korean ? "개인 워크스페이스" : "Personal Workspace")}
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
            <span>{korean ? "표시 언어" : "Display language · 표시 언어"}</span>
            <LanguageSwitch />
          </div>
        </nav>

        <div className="sidebarNote">
          <LanguageSwitch compact />
          <div className="sidebarStatus"><span className="statusDot" /> {korean ? "근거 우선 워크스페이스" : "Evidence-first workspace"}</div>
          <p>{korean ? "연구 공백 후보는 가설로 유지합니다. 논문 주장, 시스템 추론, 사용자 노트를 서로 구분합니다." : "Gap candidates stay hypotheses. Paper claims, system inference, and your notes remain separated."}</p>
          {readOnly ? <p><strong>{korean ? "포트폴리오 모드:" : "Portfolio mode:"}</strong> {korean ? "자유롭게 탐색할 수 있지만 변경 작업은 비활성화됩니다." : "browse and inspect freely; mutations are disabled."}</p> : null}
        </div>
      </aside>

      <nav className="mobileBottomNav" aria-label="Quick navigation">
        {bottomLinks.map(([href, label, koreanLabel, icon]) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              className={`mobileBottomLink${active ? " mobileBottomLinkActive" : ""}`}
              href={href}
              key={href}
              aria-current={active ? "page" : undefined}
            >
              <span aria-hidden="true">{icon}</span>
              <small>{korean ? koreanLabel : label}</small>
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
          <small>{korean ? "더보기" : "More"}</small>
        </button>
      </nav>
    </>
  );
}
