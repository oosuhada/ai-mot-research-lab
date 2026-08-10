export default function ChatPage() {
  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Evidence-grounded Chat</p>
          <h2 className="pageTitle">Ask inside a declared evidence scope.</h2>
          <p className="pageIntro">
            Answers are intended to distinguish source facts, paper claims, system inference, and your notes,
            with paragraph-level evidence rather than a single citation list at the end.
          </p>
        </div>
      </header>

      <section className="card">
        <div className="emptyState">
          Chat is wired after retrieval and evidence-link checks are in place. This avoids shipping a persuasive
          chat surface before grounding can be tested.
        </div>
      </section>
    </>
  );
}

