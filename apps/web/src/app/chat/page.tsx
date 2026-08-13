import Link from "next/link";

import {
  askChat,
  getPaper,
  listComparisonSets,
  listResearchQuestions,
  listSavedSearches,
  type PaperDetail,
} from "@/lib/api";

type ChatScope = "corpus" | "papers" | "comparison_set" | "research_question" | "saved_search";

type ChatSearchParams = {
  q?: string;
  scope?: string;
  ids?: string;
  scope_key?: string;
};

function resolveScope(params: ChatSearchParams): { scope: ChatScope; ids: string[]; scopeKey: string } {
  const explicitKey = params.scope_key?.trim();
  if (explicitKey) {
    if (explicitKey === "corpus") return { scope: "corpus", ids: [], scopeKey: "corpus" };
    if (explicitKey === "papers") {
      const ids = (params.ids ?? "").split(",").map((value) => value.trim()).filter(Boolean);
      return { scope: "papers", ids, scopeKey: "papers" };
    }
    const [kind, id] = explicitKey.split(":", 2);
    if (id && (kind === "comparison_set" || kind === "research_question" || kind === "saved_search")) {
      return { scope: kind, ids: [id], scopeKey: explicitKey };
    }
  }

  const legacyScope = params.scope;
  const legacyIds = (params.ids ?? "").split(",").map((value) => value.trim()).filter(Boolean);
  if (legacyScope === "papers") return { scope: "papers", ids: legacyIds, scopeKey: "papers" };
  if (legacyIds[0] && (legacyScope === "comparison_set" || legacyScope === "research_question" || legacyScope === "saved_search")) {
    return { scope: legacyScope, ids: [legacyIds[0]], scopeKey: `${legacyScope}:${legacyIds[0]}` };
  }
  return { scope: "corpus", ids: [], scopeKey: "corpus" };
}

export default async function ChatPage({ searchParams }: { searchParams: Promise<ChatSearchParams> }) {
  const params = await searchParams;
  const question = params.q?.trim() ?? "";
  const resolved = resolveScope(params);
  const [researchQuestions, savedSearches, comparisonSets, selectedPapers] = await Promise.all([
    listResearchQuestions(),
    listSavedSearches(),
    listComparisonSets(),
    resolved.scope === "papers"
      ? Promise.all(resolved.ids.map((id) => getPaper(id))).then((papers) => papers.filter((paper): paper is PaperDetail => Boolean(paper)))
      : Promise.resolve([] as PaperDetail[]),
  ]);
  const answer = question ? await askChat(question, resolved.scope, resolved.ids) : null;

  const followupHref = (followup: string) => {
    const search = new URLSearchParams({ q: followup, scope_key: resolved.scopeKey });
    if (resolved.scope === "papers" && resolved.ids.length) search.set("ids", resolved.ids.join(","));
    return `/chat?${search.toString()}`;
  };

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Evidence-grounded Chat</p>
          <h2 className="pageTitle">Ask a named research scope, not a database identifier.</h2>
          <p className="pageIntro">
            Choose the corpus, selected papers, a research question, a saved search, or a comparison set. The answer stays attached to inspectable citations and reports uncertainty explicitly.
          </p>
        </div>
      </header>

      <section className="evidenceProtocol" aria-label="Evidence scope and provenance policy">
        <div className="evidenceProtocolHeader">
          <span>Before asking</span>
          <strong>Scope → locator → provenance → answer</strong>
          <p>Chat is the final surface. The evidence boundary and unsupported-claim policy are shown first.</p>
        </div>

        <aside className="chatScopePreview evidenceScopeLedger">
          <span className="cardKicker">01 · Current scope</span>
          {resolved.scope === "papers" ? (
            <>
              <strong>{selectedPapers.length} selected papers</strong>
              <div className="chatScopePaperList">
                {selectedPapers.slice(0, 4).map((paper) => <span key={paper.id}>{paper.publication_year ?? "—"} · {paper.title}</span>)}
              </div>
              <Link className="textLink" href="/library">Change selection in Library →</Link>
            </>
          ) : (
            <>
              <strong>{resolved.scope === "corpus" ? "Entire research corpus" : "Named saved workspace"}</strong>
              <p>The scope selector uses human-readable names. Internal UUIDs are not part of the research workflow.</p>
            </>
          )}
        </aside>

        <div className="evidencePolicyLedger">
          <div><span>02</span><strong>Locator</strong><p>Abstract, page, or section locators stay attached to evidence excerpts.</p></div>
          <div><span>03</span><strong>Provenance</strong><p>Paper evidence, system inference, and user notes remain distinct claim kinds.</p></div>
          <div><span>04</span><strong>Unsupported claims</strong><p><code>insufficient_evidence</code> is a valid output, not a failure to fill space.</p></div>
        </div>

        <div className="chatComposer evidenceQuestionComposer">
        <form className="chatForm" action="/chat" method="get">
          <label className="fieldLabel" htmlFor="chat-question">
            Research question or challenge
            <textarea
              className="input textarea chatQuestionInput"
              id="chat-question"
              name="q"
              required
              minLength={2}
              defaultValue={question}
              placeholder="e.g. What evidence contradicts the claim that AI capability improves firm performance?"
              rows={3}
            />
          </label>
          <div className="chatControls chatControlsNamed">
            <label className="compactFieldLabel">
              <span>Evidence scope</span>
              <select className="select" name="scope_key" defaultValue={resolved.scopeKey}>
                <option value="corpus">Entire corpus</option>
                {selectedPapers.length ? <option value="papers">Selected papers ({selectedPapers.length})</option> : null}
                {researchQuestions.length ? <optgroup label="Research questions">{researchQuestions.map((item) => <option value={`research_question:${item.id}`} key={item.id}>{item.title}</option>)}</optgroup> : null}
                {savedSearches.length ? <optgroup label="Saved searches">{savedSearches.map((item) => <option value={`saved_search:${item.id}`} key={item.id}>{item.name}</option>)}</optgroup> : null}
                {comparisonSets.length ? <optgroup label="Comparison sets">{comparisonSets.map((item) => <option value={`comparison_set:${item.id}`} key={item.id}>{item.name}</option>)}</optgroup> : null}
              </select>
            </label>
            {resolved.scope === "papers" && resolved.ids.length ? <input type="hidden" name="ids" value={resolved.ids.join(",")} /> : null}
            <button className="button" type="submit">Ask with evidence</button>
          </div>
        </form>
        </div>
      </section>

      {question && !answer ? (
        <section className="card" style={{ marginTop: 16 }}>
          <div className="emptyState">The selected scope could not produce a grounded response. Try a broader evidence scope or inspect the linked records.</div>
        </section>
      ) : null}

      {answer ? (
        <div className="evidenceAnswerLayout">
          <aside className="evidenceSourceLedger">
            <div className="evidenceSourceLedgerHeader">
              <span>Source ledger</span>
              <strong>{answer.citations.length} citations</strong>
              <small>Inspect before reading synthesis.</small>
            </div>
            <div className="evidenceStack">
              {answer.citations.map((citation) => (
                <article className="claimCard" key={citation.index}>
                  <span className="pill">[{citation.index}] {citation.source_locator}</span>
                  <h4 className="evidenceTitle">{citation.paper_title}</h4>
                  <p>{citation.excerpt}</p>
                  <a className="evidenceLink" href={citation.primary_url ?? (citation.doi ? `https://doi.org/${citation.doi}` : "#")} target="_blank" rel="noreferrer">Open source ↗</a>
                </article>
              ))}
            </div>
          </aside>

          <section className="groundedNarrative">
            <div className="resultSummary">
              <strong>Grounded response</strong>
              <span className="pill">scope: {answer.scope_type.replaceAll("_", " ")}</span>
              <span className="pill">provider: {answer.provider}</span>
              <span className="pill">unsupported: {answer.structural_unsupported_claim_rate.toFixed(2)}</span>
            </div>
            <div className="answerStack">
              {answer.paragraphs.map((paragraph, index) => (
                <article className="answerParagraph" key={`${index}-${paragraph.text.slice(0, 20)}`}>
                  <div className="rankRow">
                    <span className={`statusBadge status-${paragraph.support_status}`}>{paragraph.support_status}</span>
                    <span className="pill">{paragraph.claim_kind.replaceAll("_", " ")}</span>
                  </div>
                  <p>{paragraph.text}</p>
                </article>
              ))}
            </div>
            <div className="followupLinks">
              {["What evidence contradicts this?", "Which papers support this most strongly?", "What is still uncertain?", "What theory could explain this?", "What should I read next?"].map((followup) => (
                <Link className="pill" href={followupHref(followup)} key={followup}>{followup}</Link>
              ))}
            </div>
            <div className="callout chatLimitations">
              <strong>Current limitations</strong>
              {answer.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
