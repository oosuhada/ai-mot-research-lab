import Link from "next/link";

const links = [
  ["/", "Research Landscape"],
  ["/library", "Paper Library"],
  ["/imports", "Import Papers"],
  ["/questions", "Research Questions"],
  ["/compare", "Compare Papers"],
  ["/gap-canvas", "Gap Canvas"],
  ["/chat", "Evidence Chat"],
] as const;

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brandMark">A↗</div>
        <h1 className="brandTitle">AI × MOT Research Lab</h1>
        <p className="brandSubtitle">AI & Management of Technology Research Intelligence</p>
      </div>

      <nav className="nav" aria-label="Primary navigation">
        {links.map(([href, label]) => (
          <Link className="navLink" href={href} key={href}>
            {label}
          </Link>
        ))}
      </nav>

      <div className="sidebarNote">
        Gap candidates are hypotheses to validate. Generated claims stay visibly separate from paper
        claims, facts, and your own notes.
      </div>
    </aside>
  );
}

