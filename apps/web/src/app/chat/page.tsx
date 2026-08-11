import { askChat } from "@/lib/api";

type ChatSearchParams = {
  q?: string;
  scope?: string;
  ids?: string;
};

function normalizeScope(
  value: string | undefined,
): "corpus" | "papers" | "comparison_set" | "research_question" | "saved_search" {
  if (
    value === "papers" ||
    value === "comparison_set" ||
    value === "research_question" ||
    value === "saved_search"
  ) {
    return value;
  }
  return "corpus";
}

export default async function ChatPage({
  searchParams,
}: {
  searchParams: Promise<ChatSearchParams>;
}) {
  const params = await searchParams;
  const question = params.q?.trim() ?? "";
  const scope = normalizeScope(params.scope);
  const scopeIds = (params.ids ?? "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const answer = question ? await askChat(question, scope, scopeIds) : null;

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Evidence-grounded Chat</p>
          <h2 className="pageTitle">Ask inside a declared evidence scope.</h2>
          <p className="pageIntro">
            Every assertive paragraph must carry citation indexes. The no-key baseline reports traceable
            abstract evidence rather than pretending to provide an uncited scholarly synthesis.
          </p>
        </div>
      </header>

      <section className="card">
        <form className="chatForm" action="/chat" method="get">
          <textarea
            className="input textarea"
            name="q"
            required
            minLength={2}
            defaultValue={question}
            placeholder="e.g. How does AI capability relate to firm performance?"
            rows={3}
          />
          <div className="chatControls">
            <select className="select" name="scope" defaultValue={scope}>
              <option value="corpus">Entire corpus</option>
              <option value="papers">Selected paper IDs</option>
              <option value="comparison_set">Comparison set</option>
              <option value="research_question">Research question</option>
              <option value="saved_search">Saved search</option>
            </select>
            <input
              className="input"
              name="ids"
              defaultValue={params.ids ?? ""}
              placeholder="Optional UUIDs, comma-separated"
            />
            <button className="button" type="submit">Ask with evidence</button>
          </div>
        </form>
      </section>

      {question && !answer ? (
        <section className="card" style={{ marginTop: 16 }}>
          <div className="emptyState">
            The selected scope could not produce a grounded response. Check scope IDs and the local API.
          </div>
        </section>
      ) : null}

      {answer ? (
        <div className="grid chatLayout">
          <section className="card span8">
            <div className="resultSummary">
              <strong>Grounded response</strong>
              <span className="pill">scope: {answer.scope_type}</span>
              <span className="pill">provider: {answer.provider}</span>
              <span className="pill">unsupported: {answer.structural_unsupported_claim_rate.toFixed(2)}</span>
            </div>
            <div className="answerStack">
              {answer.paragraphs.map((paragraph, index) => (
                <article className="answerParagraph" key={`${index}-${paragraph.text.slice(0, 20)}`}>
                  <div className="rankRow">
                    <span className={`statusBadge status-${paragraph.support_status}`}>
                      {paragraph.support_status}
                    </span>
                    <span className="pill">{paragraph.claim_kind}</span>
                  </div>
                  <p>{paragraph.text}</p>
                </article>
              ))}
            </div>
            <div className="followupLinks">
              {[
                "What evidence contradicts this?",
                "Which papers support this most strongly?",
                "What is still uncertain?",
                "What theory could explain this?",
                "What should I read next?",
              ].map((followup) => {
                const href = `/chat?q=${encodeURIComponent(followup)}&scope=${scope}&ids=${encodeURIComponent(params.ids ?? "")}`;
                return <a className="pill" href={href} key={followup}>{followup}</a>;
              })}
            </div>
            <div className="callout chatLimitations">
              <strong>Current limitations</strong>
              {answer.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}
            </div>
          </section>

          <aside className="card span4">
            <h3 className="sectionTitle">Evidence drawer</h3>
            <div className="evidenceStack">
              {answer.citations.map((citation) => (
                <article className="claimCard" key={citation.index}>
                  <span className="pill">[{citation.index}] {citation.source_locator}</span>
                  <h4 className="evidenceTitle">{citation.paper_title}</h4>
                  <p>{citation.excerpt}</p>
                  <a
                    className="evidenceLink"
                    href={citation.primary_url ?? (citation.doi ? `https://doi.org/${citation.doi}` : "#")}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open source ↗
                  </a>
                </article>
              ))}
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}
