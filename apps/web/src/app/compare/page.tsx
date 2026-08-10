const fields = [
  "Research question",
  "Theoretical lens",
  "Unit of analysis",
  "Context / industry / country",
  "Dataset and sample",
  "Methodology",
  "Variables or constructs",
  "Findings",
  "Limitations",
  "Claimed contribution",
  "Future research",
];

export default function ComparePage() {
  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Compare Papers</p>
          <h2 className="pageTitle">Compare study design, not just summaries.</h2>
          <p className="pageIntro">
            Every comparison cell is designed to carry evidence links or an explicit insufficient-evidence state.
          </p>
        </div>
      </header>

      <section className="card">
        <div className="axisList">
          {fields.map((field) => (
            <div className="axisRow" key={field}>
              <span>{field}</span>
              <span className="pill">evidence</span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

