export default function GapCanvasPage() {
  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Research Question & Gap Canvas</p>
          <h2 className="pageTitle">Turn evidence patterns into questions you can disprove.</h2>
          <p className="pageIntro">
            The canvas keeps search strategy, inclusion rules, conflicts, under-studied contexts, and
            falsifiability notes editable instead of freezing an LLM output as a conclusion.
          </p>
        </div>
      </header>

      <section className="grid">
        <article className="card span6">
          <h3 className="sectionTitle">Research question</h3>
          <textarea className="input" rows={7} placeholder="What relationship do you want to investigate?" />
        </article>
        <article className="card span6">
          <h3 className="sectionTitle">Evidence status</h3>
          <div className="callout">
            <strong>Candidate, not conclusion.</strong>
            Gap generation remains in draft until claims link to papers/chunks or are explicitly marked as
            insufficient evidence.
          </div>
        </article>
      </section>
    </>
  );
}

