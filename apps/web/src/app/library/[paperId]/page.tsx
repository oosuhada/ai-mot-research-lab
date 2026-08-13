import Link from "next/link";
import { notFound } from "next/navigation";

import { getCitationSnowball, getPaper } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import {
  addNoteAction,
  addTagAction,
  removeNoteAction,
  removeTagAction,
  updateReadingAction,
  uploadPdfAction,
} from "./actions";

function externalHref(url: string | null, doi: string | null): string | null {
  return url ?? (doi ? `https://doi.org/${doi}` : null);
}

export default async function PaperDetailPage({ params }: { params: Promise<{ paperId: string }> }) {
  const { paperId } = await params;
  const [paper, snowball] = await Promise.all([getPaper(paperId), getCitationSnowball(paperId)]);
  if (!paper) notFound();
  const readOnly = isWorkspaceReadOnly();

  const sourceHref = externalHref(paper.primary_url, paper.doi);
  const axes = paper.topics.filter((topic) => topic.kind === "research_axis");
  const methodologies = paper.topics.filter((topic) => topic.kind === "methodology");
  const readingAction = updateReadingAction.bind(null, paper.id);
  const tagAction = addTagAction.bind(null, paper.id);
  const noteAction = addNoteAction.bind(null, paper.id);

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow">Paper Detail</p>
          <h2 className="paperDetailTitle">{paper.title}</h2>
          <p className="pageIntro">
            {paper.publication_year ?? "Year unknown"} · {paper.venue?.name ?? paper.publisher ?? "Venue unknown"} · {paper.is_oa ? "Open access" : "OA unknown/closed"}
          </p>
          <div className="headerActionRow"><Link className="secondaryButton" href={`/compare?papers=${paper.id}`}>Add to comparison →</Link><Link className="secondaryButton" href={`/chat?scope=papers&ids=${paper.id}`}>Ask about this paper →</Link></div>
        </div>
        <Link className="button buttonSecondary" href="/library">← Library</Link>
      </header>

      <section className="grid">
        <article className="card span8">
          <h3 className="sectionTitle">Abstract</h3>
          <p className="longText">{paper.abstract ?? "No abstract is available in the local metadata record."}</p>
          <div className="rankRow">
            {paper.doi ? <a className="pill" href={`https://doi.org/${paper.doi}`} target="_blank" rel="noreferrer">DOI ↗</a> : null}
            {sourceHref ? <a className="pill" href={sourceHref} target="_blank" rel="noreferrer">Publisher/source ↗</a> : null}
            {paper.pdf_url ? <a className="pill" href={paper.pdf_url} target="_blank" rel="noreferrer">OA/PDF location ↗</a> : null}
            <span className="pill">Citations {paper.latest_citation_count ?? "—"}</span>
          </div>
        </article>

        <aside className="card span4">
          <h3 className="sectionTitle">Reading workflow</h3>
          {!readOnly ? <form action={readingAction} className="formStack">
            <select className="select" name="status" defaultValue={paper.reading?.status ?? "unread"}>
              <option value="unread">Unread</option><option value="skimming">Skimming</option>
              <option value="reading">Reading</option><option value="read">Read</option><option value="archived">Archived</option>
            </select>
            <label className="fieldLabel">Priority (0–100)<input className="input" name="priority" type="number" min="0" max="100" defaultValue={paper.reading?.priority ?? 0} /></label>
            <button className="button" type="submit">Save reading state</button>
          </form> : <div className="readOnlyPanel"><strong>Public Demo · Read-only</strong><span>Reading state: {paper.reading?.status ?? "unread"} · priority {paper.reading?.priority ?? 0}</span></div>}
        </aside>

        <article className="card span6">
          <h3 className="sectionTitle">Research classification</h3>
          <div className="tagCloud">{axes.map((topic) => <span className="pill" key={topic.slug}>{topic.display_name}</span>)}</div>
          <h4>Methodology signals</h4>
          <p className="muted">System heuristic, not author-reported methodology. Verify against the paper before using it as a study-design fact.</p>
          <div className="tagCloud">{methodologies.length ? methodologies.map((topic) => <span className="pill" key={topic.slug}>{topic.display_name}</span>) : <span className="muted">No methodology heuristic assigned.</span>}</div>
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Bibliographic record</h3>
          <dl className="detailList">
            <div><dt>Authors</dt><dd>{paper.authors.map((author) => author.display_name).join(", ") || "Unknown"}</dd></div>
            <div><dt>Work type</dt><dd>{paper.work_type ?? "Unknown"}</dd></div>
            <div><dt>Retraction</dt><dd>{paper.retraction_status}</dd></div>
            <div><dt>Correction</dt><dd>{paper.correction_status}</dd></div>
            <div><dt>Citation snapshot</dt><dd>{paper.latest_citation_snapshot_at ? new Date(paper.latest_citation_snapshot_at).toLocaleDateString("en-CA") : "None"}</dd></div>
          </dl>
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Tags</h3>
          <div className="tagCloud">
            {readOnly ? paper.tags.map((tag) => <span className="pill" key={tag.id}>{tag.name}</span>) : paper.tags.map((tag) => (
              <form action={removeTagAction.bind(null, paper.id)} key={tag.id}>
                <input type="hidden" name="name" value={tag.name} />
                <button className="pill chipButton" type="submit">{tag.name} ×</button>
              </form>
            ))}
          </div>
          {!readOnly ? <form action={tagAction} className="inlineForm"><input className="input" name="name" placeholder="Add tag" /><button className="button" type="submit">Add</button></form> : null}
        </article>

        <article className="card span6">
          <h3 className="sectionTitle">Research notes</h3>
          {!readOnly ? <form action={noteAction} className="formStack">
            <textarea className="textarea" name="note" required placeholder="Your interpretation, question, or reading note" />
            <input className="input" name="source_locator" placeholder="Optional source locator, e.g. abstract or p. 7" />
            <button className="button" type="submit">Save note</button>
          </form> : null}
          <div className="noteStack">
            {paper.notes.map((note) => (
              <div className="noteCard" key={note.id}><p>{note.note_markdown}</p><small>{note.source_locator ?? "No source locator"}</small>
                {!readOnly ? <form action={removeNoteAction.bind(null, paper.id)}><input type="hidden" name="note_id" value={note.id} /><button className="textButton" type="submit">Delete</button></form> : null}
              </div>
            ))}
          </div>
        </article>

        <article className="card span12">
          <h3 className="sectionTitle">Citation snowballing</h3>
          <p className="muted">
            Local OpenAlex citation IDs are resolved only when both papers exist in this corpus. These are discovery
            paths, not evidence that a cited paper supports the citing paper&apos;s claim.
          </p>
          <div className="citationColumns">
            <div>
              <h4>Backward · references in this paper</h4>
              <div className="noteStack">
                {snowball?.backward.length ? snowball.backward.map((neighbor) => (
                  <Link className="noteCard citationCard" href={`/library/${neighbor.id}`} key={neighbor.id}>
                    <strong>{neighbor.title}</strong>
                    <small>{neighbor.publication_year ?? "Year unknown"} · citations {neighbor.citation_count ?? "—"}</small>
                  </Link>
                )) : <span className="muted">No locally resolved references in the current corpus.</span>}
              </div>
            </div>
            <div>
              <h4>Forward · local papers citing this paper</h4>
              <div className="noteStack">
                {snowball?.forward.length ? snowball.forward.map((neighbor) => (
                  <Link className="noteCard citationCard" href={`/library/${neighbor.id}`} key={neighbor.id}>
                    <strong>{neighbor.title}</strong>
                    <small>{neighbor.publication_year ?? "Year unknown"} · citations {neighbor.citation_count ?? "—"}</small>
                  </Link>
                )) : <span className="muted">No locally resolved forward citations in the current corpus.</span>}
              </div>
            </div>
          </div>
        </article>

        <article className="card span12">
          <h3 className="sectionTitle">Provenance</h3>
          <dl className="detailList provenanceGrid">
            <div><dt>Primary source</dt><dd>{paper.primary_source}</dd></div>
            <div><dt>Source record ID</dt><dd>{paper.source_record_id}</dd></div>
            <div><dt>Retrieved</dt><dd>{new Date(paper.retrieved_at).toISOString()}</dd></div>
            <div><dt>License</dt><dd>{paper.license ?? "Unknown"}</dd></div>
          </dl>
          <details><summary>Raw normalized provenance metadata</summary><pre className="codeBlock">{JSON.stringify(paper.provenance, null, 2)}</pre></details>
        </article>

        <article className="card span12">
          <h3 className="sectionTitle">Private full-text evidence</h3>
          <p className="muted">Attach a PDF only when you own it or have permission to process it privately. The file is stored under Git-ignored local private data, is not redistributed, and OCR is not run automatically.</p>
          {!readOnly ? <form action={uploadPdfAction.bind(null, paper.id)} className="formStack" encType="multipart/form-data">
            <input className="input" name="file" type="file" accept="application/pdf,.pdf" required />
            <label className="checkboxLabel"><input name="rights_confirmed" type="checkbox" required /> I confirm I own this file or have permission to process it privately.</label>
            <button className="button" type="submit">Extract private full text</button>
          </form> : <div className="readOnlyPanel"><strong>Uploads disabled in public demo</strong><span>Private PDF processing is available only inside a personal workspace.</span></div>}
          <p className="metricHelp">When extraction succeeds, page-preserving chunks become available to full-text search and evidence citation.</p>
        </article>
      </section>
    </>
  );
}
