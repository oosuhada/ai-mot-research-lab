"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/", "Landscape", "01"],
  ["/library", "Library", "02"],
  ["/questions", "Research Questions", "03"],
  ["/compare", "Compare", "04"],
  ["/gap-canvas", "Gap Canvas", "05"],
  ["/chat", "Evidence Chat", "06"],
  ["/imports", "Import", "+"],
] as const;

export function Sidebar() {
  const pathname = usePathname() ?? "";

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brandMark">A↗</div>
        <h1 className="brandTitle">AI × MOT Research Lab</h1>
        <p className="brandSubtitle">AI & Management of Technology Research Intelligence</p>
      </div>

      <nav className="nav" aria-label="Primary navigation">
        <p className="navSectionLabel">Workspace</p>
        {links.map(([href, label, index]) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link className={`navLink${active ? " navLinkActive" : ""}`} href={href} key={href}>
              <span className="navIndex">{index}</span>
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebarNote">
        <div className="sidebarStatus"><span className="statusDot" /> Evidence-first workspace</div>
        <p>Gap candidates stay hypotheses. Paper claims, system inference, and your notes remain separated.</p>
      </div>
    </aside>
  );
}
