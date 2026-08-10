export default function LibraryPage() {
  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Paper Library</p>
          <h2 className="pageTitle">Search the corpus with two retrieval lenses.</h2>
          <p className="pageIntro">
            Lexical and semantic ranks are kept visible so a fused ranking never hides where a result came from.
          </p>
        </div>
      </header>

      <section className="card">
        <form className="searchBar" action="/library" method="get">
          <input
            className="input"
            name="q"
            placeholder="e.g. human-AI decision making and organizational performance"
            aria-label="Search papers"
          />
          <button className="button" type="submit">
            Search
          </button>
        </form>
        <div className="emptyState" style={{ marginTop: 18 }}>
          Ingest the seed corpus, then search results will show year, axis, OA status, DOI, and the lexical /
          semantic contribution to the hybrid rank.
        </div>
      </section>
    </>
  );
}

