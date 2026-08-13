import Link from "next/link";

import { CitationAtlas } from "@/components/CitationAtlas";
import { getLandscape, listResearchQuestions } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

const fallbackAxes = [
  "AI adoption and business value",
  "Technology and innovation management",
  "AI-enabled organizational change",
  "Industrial AI and smart operations",
  "AI governance and responsible deployment",
  "Agentic systems and enterprise workflows",
];

export default async function HomePage() {
  const landscape = await getLandscape();
  const questions = await listResearchQuestions();
  const readOnly = isWorkspaceReadOnly();
  const axes = landscape?.axes ?? fallbackAxes.map((display_name, index) => ({
    slug: `axis-${index}`,
    display_name,
    paper_count: 0,
  }));
  const methodologies = landscape?.methodologies ?? [];
  const oaRatio = landscape?.total_papers ? Math.round((landscape.oa_papers / landscape.total_papers) * 100) : 0;
  const abstractRatio = landscape?.total_papers ? Math.round((landscape.abstract_papers / landscape.total_papers) * 100) : 0;
  const missingAbstracts = Math.max((landscape?.total_papers ?? 0) - (landscape?.abstract_papers ?? 0), 0);
  const fullTextRatio = landscape?.total_papers ? Math.round((landscape.full_text_papers / landscape.total_papers) * 100) : 0;
  const years = landscape?.years ?? [];
  const coverageStart = years.at(0)?.year;
  const coverageEnd = years.at(-1)?.year;
  const dominantYear = years.reduce((current, candidate) => candidate.paper_count > current.paper_count ? candidate : current, years[0] ?? { year: 0, paper_count: 0 });
  const dominantYearRatio = landscape?.total_papers && dominantYear.year ? Math.round((dominantYear.paper_count / landscape.total_papers) * 100) : 0;

  return (
    <>
      <section className="researchThreadHero">
        <div className="researchThreadLead">
          <div className="researchThreadMarker"><span>Field note</span><strong>01</strong></div>
          <p className="eyebrow">Scholarly Atlas × Living Research Journal</p>
          <h2>What has the literature actually explained about AI and management of technology?</h2>
          <p>
            Begin with a research question, not a dashboard metric. Move outward through evidence territories,
            paper records, comparison arguments, and falsification paths while keeping provenance visible.
          </p>
          <form className="researchThreadSearch" action="/library" method="get">
            <label htmlFor="thread-search">Start a literature thread</label>
            <div>
              <input id="thread-search" name="q" placeholder="AI capability → organizational change → innovation performance" />
              <input type="hidden" name="mode" value="hybrid" />
              <button type="submit">Trace evidence →</button>
            </div>
          </form>
        </div>

        <aside className="researchQuestionLedger" aria-label="Research question ledger">
          <div className="ledgerTitleRow"><span>Research question thread</span><small>{questions.length} active</small></div>
          {questions.length ? questions.slice(0, 4).map((question, index) => (
            <Link className="ledgerQuestion" href={`/questions/${question.id}`} key={question.id}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{question.title}</strong>
              <small>Open journal thread →</small>
            </Link>
          )) : (
            <div className="ledgerQuestion ledgerQuestionEmpty">
              <span>01</span><strong>No saved question yet.</strong><small>Frame one before claiming a gap.</small>
            </div>
          )}
          <Link className="ledgerFootLink" href="/questions">{readOnly ? "Explore research questions" : "Create a research question"} →</Link>
        </aside>
      </section>

      <nav className="researchThreadRail" aria-label="Research workflow">
        <Link href="/questions"><span>Question</span><small>frame the thread</small></Link>
        <Link href="/library"><span>Library</span><small>collect evidence</small></Link>
        <Link href="/compare"><span>Compare</span><small>test differences</small></Link>
        <Link href="/gap-canvas"><span>Gap Canvas</span><small>challenge the claim</small></Link>
        <Link href="/chat"><span>Evidence Chat</span><small>inspect synthesis</small></Link>
      </nav>

      <CitationAtlas axes={axes} years={years} totalPapers={landscape?.total_papers ?? 0} />

      <section className="fieldJournal" aria-label="Corpus field notes">
        <header className="fieldJournalHeader">
          <p className="eyebrow">Field journal · corpus diagnostics</p>
          <h3>Read the limits beside the evidence.</h3>
          <p>These notes describe the local corpus. They do not claim to describe the full scholarly field.</p>
        </header>
        <div className="fieldJournalColumns">
          <article className="fieldNoteBlock">
            <span className="fieldNoteNumber">A</span>
            <h4>Coverage ledger</h4>
            <dl>
              <div><dt>Period</dt><dd>{coverageStart && coverageEnd ? `${coverageStart}–${coverageEnd}` : "—"}</dd></div>
              <div><dt>Open-access metadata</dt><dd>{oaRatio}%</dd></div>
              <div><dt>Missing abstracts</dt><dd>{missingAbstracts} · {abstractRatio}% abstract coverage</dd></div>
              <div><dt>Full-text evidence</dt><dd>{fullTextRatio}% · {landscape?.full_text_papers ?? 0} records</dd></div>
              <div><dt>Last ingestion</dt><dd>{landscape?.last_ingestion_at ? new Date(landscape.last_ingestion_at).toLocaleDateString("en-CA") : "—"}</dd></div>
            </dl>
          </article>

          <article className="fieldNoteBlock">
            <span className="fieldNoteNumber">B</span>
            <h4>Method signals</h4>
            <p>Heuristic labels are system inference, never author-reported methodology.</p>
            <ol className="methodLedger">
              {methodologies.slice(0, 7).map((method) => <li key={method.slug}><span>{method.display_name}</span><strong>{method.paper_count}</strong></li>)}
            </ol>
          </article>

          <article className="fieldNoteBlock fieldNoteRules">
            <span className="fieldNoteNumber">C</span>
            <h4>Interpretation rules</h4>
            <p><strong>01</strong> Sparse coverage is a search signal, not proof of a literature gap.</p>
            <p><strong>02</strong> System inference and paper evidence remain visibly separate.</p>
            <p><strong>03</strong> Unsupported fields stay <code>insufficient_evidence</code>.</p>
            <p><strong>04</strong> The {dominantYear.year || "dominant"} year share is {dominantYearRatio}% of this corpus; concentration must be read as sampling context.</p>
          </article>
        </div>

        <footer className="fieldJournalFooter">
          <span>Top authors · {landscape?.top_authors.slice(0, 3).map((item) => `${item.name} (${item.paper_count})`).join(" · ") || "—"}</span>
          <span>Top venues · {landscape?.top_venues.slice(0, 3).map((item) => `${item.name} (${item.paper_count})`).join(" · ") || "—"}</span>
          <Link href="/library?view=browse">Open the scholarly index →</Link>
        </footer>
      </section>
    </>
  );
}
