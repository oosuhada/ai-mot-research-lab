import { importMetadataAction } from "./actions";
import { isWorkspaceReadOnly } from "@/lib/workspace";

export default function ImportsPage() {
  const readOnly = isWorkspaceReadOnly();
  return <>
    <header className="pageHeader"><div><p className="eyebrow">User Imports</p><h2 className="pageTitle">Bring your own bibliography without losing provenance.</h2><p className="pageIntro">DOI, BibTeX, RIS, and CSV imports deduplicate by DOI and record an ingestion run plus user-import source version. Private PDFs are attached from the paper detail page in the next step and are never committed to Git.</p></div></header>
    <section className="card span8">{readOnly ? <div className="readOnlyPanel"><strong>Public Demo · Import disabled</strong><span>The portfolio deployment does not accept shared writes or file uploads. Import is available only in a personal workspace.</span></div> : <form action={importMetadataAction} className="formStack">
      <label className="fieldLabel">Format<select className="select" name="format" defaultValue="doi"><option value="doi">DOI(s)</option><option value="bibtex">BibTeX</option><option value="ris">RIS</option><option value="csv">CSV</option></select></label>
      <textarea className="textarea importTextarea" name="content" required placeholder={"10.1234/example\n10.5678/example\n\nor paste BibTeX / RIS / CSV"} />
      <button className="button" type="submit">Import metadata</button>
    </form>}<div className="callout" style={{ marginTop: 18 }}><strong>Private-by-default.</strong> User PDFs remain local. Possessing a PDF is not treated as permission to redistribute it.</div></section>
  </>;
}
