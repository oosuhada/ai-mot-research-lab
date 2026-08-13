import { importMetadataAction } from "./actions";
import { MutationFeedback } from "@/components/MutationFeedback";
import { isWorkspaceReadOnly } from "@/lib/workspace";

export default async function ImportsPage({ searchParams }: { searchParams: Promise<{ feedback?: string }> }) {
  const params = await searchParams;
  const readOnly = isWorkspaceReadOnly();
  return <>
    {!readOnly ? (
      <MutationFeedback
        feedback={params.feedback}
        messages={{
          "missing-content": { message: "Enter DOI, BibTeX, RIS, or CSV metadata before importing.", tone: "error" },
          empty: { message: "The import completed but did not produce a paper record.", tone: "error" },
          error: { message: "The metadata import failed. No partial success is being presented as complete.", tone: "error" },
        }}
      />
    ) : null}
    <header className="pageHeader"><div><p className="eyebrow">User Imports</p><h2 className="pageTitle">Bring your own bibliography without losing provenance.</h2><p className="pageIntro">DOI, BibTeX, RIS, and CSV imports deduplicate by DOI and record an ingestion run plus user-import source version. Private PDFs are attached from the paper detail page in the next step and are never committed to Git.</p></div></header>
    <section className="card span8">{readOnly ? <div className="readOnlyPanel"><strong>Public Demo · Import disabled</strong><span>The portfolio deployment does not accept shared writes or file uploads. Import is available only in a personal workspace.</span></div> : <form action={importMetadataAction} className="formStack">
      <label className="fieldLabel">Format<select className="select" name="format" defaultValue="doi"><option value="doi">DOI(s)</option><option value="bibtex">BibTeX</option><option value="ris">RIS</option><option value="csv">CSV</option></select></label>
      <textarea className="textarea importTextarea" name="content" required placeholder={"10.1234/example\n10.5678/example\n\nor paste BibTeX / RIS / CSV"} />
      <button className="button" type="submit">Import metadata</button>
    </form>}<div className="callout" style={{ marginTop: 18 }}><strong>Private-by-default.</strong> User PDFs remain local. Possessing a PDF is not treated as permission to redistribute it.</div></section>
  </>;
}
