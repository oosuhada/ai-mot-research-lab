import { importMetadataAction } from "./actions";
import { MutationFeedback } from "@/components/MutationFeedback";
import { LocalizedText } from "@/components/LocalizedText";
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
    <header className="pageHeader"><div><p className="eyebrow"><LocalizedText en="User Imports" ko="사용자 자료 가져오기" /></p><h2 className="pageTitle"><LocalizedText en="Bring your own bibliography without losing provenance." ko="출처 이력을 잃지 않고 내 참고문헌을 가져오세요." /></h2><p className="pageIntro"><LocalizedText en="DOI, BibTeX, RIS, and CSV imports deduplicate by DOI and record an ingestion run plus user-import source version. Private PDFs are attached from the paper detail page and are never committed to Git." ko="DOI, BibTeX, RIS, CSV 자료는 DOI 기준으로 중복을 제거하고 수집 실행 기록과 사용자 자료 출처 버전을 보존합니다. 비공개 PDF는 논문 상세 화면에서 첨부하며 Git에 저장하지 않습니다." /></p></div></header>
    <section className="card span8">{readOnly ? <div className="readOnlyPanel"><strong><LocalizedText en="Public Demo · Import disabled" ko="공개 데모 · 가져오기 비활성화" /></strong><span><LocalizedText en="The portfolio deployment does not accept shared writes or file uploads. Import is available only in a personal workspace." ko="포트폴리오 배포 환경에서는 공유 데이터 변경이나 파일 업로드를 허용하지 않습니다. 가져오기는 개인 워크스페이스에서만 사용할 수 있습니다." /></span></div> : <form action={importMetadataAction} className="formStack">
      <label className="fieldLabel"><LocalizedText en="Format" ko="형식" /><select className="select" name="format" defaultValue="doi"><option value="doi">DOI(s)</option><option value="bibtex">BibTeX</option><option value="ris">RIS</option><option value="csv">CSV</option></select></label>
      <textarea className="textarea importTextarea" name="content" required placeholder={"10.1234/example\n10.5678/example\n\nor paste BibTeX / RIS / CSV"} />
      <button className="button" type="submit"><LocalizedText en="Import metadata" ko="서지정보 가져오기" /></button>
    </form>}<div className="callout" style={{ marginTop: 18 }}><strong><LocalizedText en="Private-by-default." ko="기본 비공개." /></strong> <LocalizedText en="User PDFs remain local. Possessing a PDF is not treated as permission to redistribute it." ko="사용자 PDF는 로컬에만 보관합니다. PDF를 보유했다고 해서 재배포 권한이 있다고 간주하지 않습니다." /></div></section>
  </>;
}
