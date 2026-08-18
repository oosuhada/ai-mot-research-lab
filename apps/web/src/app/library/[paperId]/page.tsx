import Link from "next/link";
import { notFound } from "next/navigation";

import { MutationFeedback } from "@/components/MutationFeedback";
import { BilingualPaperText } from "@/components/BilingualPaperText";
import { LocalizedTaxonomyText, LocalizedText } from "@/components/LocalizedText";
import { getCitationSnowball, getPaper, getPaperResearchCard } from "@/lib/api";
import { isWorkspaceReadOnly } from "@/lib/workspace";

import {
  addNoteAction,
  addTagAction,
  removeNoteAction,
  removeTagAction,
  startResearchCardAction,
  updateReadingAction,
  updateResearchCardAction,
  uploadPdfAction,
} from "./actions";

const researchCardFields = [
  ["one_line_summary", "Evidence lead", "핵심 근거 한 줄"],
  ["research_question", "Research question / purpose", "연구 질문 / 목적"],
  ["theoretical_lens", "Theoretical lens", "이론적 관점"],
  ["unit_of_analysis", "Unit of analysis", "분석 단위"],
  ["context_industry_country", "Context / industry / country", "맥락 / 산업 / 국가"],
  ["dataset_and_sample", "Dataset / sample", "데이터 / 표본"],
  ["methodology", "Methodology", "연구방법"],
  ["analysis_technique", "Analysis technique", "분석 기법"],
  ["variables_or_constructs", "Variables / constructs", "변수 / 구성개념"],
  ["findings", "Main findings", "주요 결과"],
  ["limitations", "Limitations", "한계"],
  ["claimed_contribution", "Claimed contribution", "연구 기여"],
  ["future_research", "Future research", "후속 연구"],
] as const;

function externalHref(url: string | null, doi: string | null): string | null {
  return url ?? (doi ? `https://doi.org/${doi}` : null);
}

const feedbackMessages = {
  imported: { message: "Metadata imported successfully. Review the normalized record and provenance before treating fields as verified." },
  "reading-saved": { message: "Reading state saved." },
  "tag-added": { message: "Tag added." },
  "tag-removed": { message: "Tag removed." },
  "note-added": { message: "Research note saved." },
  "note-removed": { message: "Research note removed." },
  "pdf-uploaded": { message: "Private PDF extracted successfully. The source file remains private and is not redistributed." },
  "invalid-reading": { message: "Choose a valid reading state and numeric priority.", tone: "error" },
  "invalid-tag": { message: "Enter a tag before saving it.", tone: "error" },
  "invalid-note": { message: "Enter a research note before saving it.", tone: "error" },
  "missing-pdf": { message: "Choose a PDF file before starting private extraction.", tone: "error" },
  "rights-required": { message: "Confirm that you own the PDF or have permission to process it privately.", tone: "error" },
  "pdf-error": { message: "Private PDF extraction failed. No successful extraction is being claimed.", tone: "error" },
  "research-card-started": { message: "Structured Research Card started from the current evidence." },
  "research-card-saved": { message: "Research Card saved as a working review." },
  "research-card-reviewed": { message: "Research Card marked reviewed. It can now contribute to question synthesis." },
  "research-card-error": { message: "The Research Card could not be saved. Existing review data was not changed.", tone: "error" },
  error: { message: "The paper workspace change could not be saved. Existing research data was not presented as updated.", tone: "error" },
} as const;

export default async function PaperDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ paperId: string }>;
  searchParams: Promise<{ feedback?: string; imported?: string }>;
}) {
  const { paperId } = await params;
  const query = await searchParams;
  const [paper, snowball, researchCard] = await Promise.all([
    getPaper(paperId),
    getCitationSnowball(paperId),
    getPaperResearchCard(paperId),
  ]);
  if (!paper) notFound();
  const readOnly = isWorkspaceReadOnly();
  const feedback = query.imported === "1" ? "imported" : query.feedback;

  const sourceHref = externalHref(paper.primary_url, paper.doi);
  const axes = paper.topics.filter((topic) => topic.kind === "research_axis");
  const methodologies = paper.topics.filter((topic) => topic.kind === "methodology");
  const subaxes = paper.topics.filter((topic) => topic.kind === "research_subaxis");
  const korean = paper.localizations.find((localization) => localization.locale === "ko" && localization.status === "completed");
  const readingAction = updateReadingAction.bind(null, paper.id);
  const tagAction = addTagAction.bind(null, paper.id);
  const noteAction = addNoteAction.bind(null, paper.id);
  const cardStartAction = startResearchCardAction.bind(null, paper.id);
  const cardUpdateAction = updateResearchCardAction.bind(null, paper.id);

  return (
    <>
      {!readOnly ? <MutationFeedback feedback={feedback} messages={feedbackMessages} /> : null}
      <header className="paperDocumentHeader">
        <div>
          <p className="eyebrow"><LocalizedText en="Research document" ko="연구 문서" /> · {paper.primary_source}</p>
          <h2 className="paperDetailTitle">{paper.title}</h2>
          <p className="pageIntro">
            {paper.publication_year ?? <LocalizedText en="Year unknown" ko="연도 미상" />} · {paper.venue?.name ?? paper.publisher ?? <LocalizedText en="Venue unknown" ko="학술지 미상" />} · {paper.is_oa ? <LocalizedText en="Open access" ko="오픈 액세스" /> : <LocalizedText en="OA unknown/closed" ko="비공개 또는 상태 미상" />}
          </p>
          <div className="headerActionRow"><Link className="secondaryButton" href={`/compare?papers=${paper.id}`}><LocalizedText en="Add to comparison →" ko="비교에 추가 →" /></Link><Link className="secondaryButton" href={`/chat?scope=papers&ids=${paper.id}`}><LocalizedText en="Ask about this paper →" ko="이 논문에 질문하기 →" /></Link></div>
        </div>
        <Link className="button buttonSecondary" href="/library">← Library</Link>
      </header>

      <article className="paperReadingDocument">
        <div className="paperDocumentBody">
        <section className="paperDocumentAbstract">
          <div className="paperDocumentSectionLabel"><span>01</span><strong><LocalizedText en="Abstract" ko="초록" /></strong></div>
          <BilingualPaperText
            englishAbstract={paper.abstract}
            englishKeywords={[...axes, ...subaxes].map((topic) => topic.display_name)}
            englishTitle={paper.title}
            koreanAbstract={korean?.abstract ?? null}
            koreanKeywords={korean?.keywords ?? []}
            koreanTitle={korean?.title ?? null}
          />
          <div className="rankRow">
            {paper.doi ? <a className="pill" href={`https://doi.org/${paper.doi}`} target="_blank" rel="noreferrer">DOI ↗</a> : null}
            {sourceHref ? <a className="pill" href={sourceHref} target="_blank" rel="noreferrer">Publisher/source ↗</a> : null}
            {paper.pdf_url ? <a className="pill" href={paper.pdf_url} target="_blank" rel="noreferrer">OA/PDF location ↗</a> : null}
            <span className="pill">Citations {paper.latest_citation_count ?? "—"}</span>
            <span className="pill">Abstract · {paper.content_profile.abstract_status}</span>
            <span className="pill">Full text · {paper.content_profile.full_text_status}</span>
          </div>
        </section>

        <aside className="paperDocumentMargin">
          <div className="paperDocumentSectionLabel"><span><LocalizedText en="Margin" ko="여백" /></span><strong><LocalizedText en="Reading state" ko="읽기 상태" /></strong></div>
          {!readOnly ? <form action={readingAction} className="formStack">
            <select className="select" name="status" defaultValue={paper.reading?.status ?? "unread"}>
              <option value="unread">Unread</option><option value="skimming">Skimming</option>
              <option value="reading">Reading</option><option value="read">Read</option><option value="archived">Archived</option>
            </select>
            <label className="fieldLabel"><LocalizedText en="Priority (0–100)" ko="우선순위 (0–100)" /><input className="input" name="priority" type="number" min="0" max="100" defaultValue={paper.reading?.priority ?? 0} /></label>
            <button className="button" type="submit"><LocalizedText en="Save reading state" ko="읽기 상태 저장" /></button>
          </form> : <div className="readOnlyPanel"><strong><LocalizedText en="Public Demo · Read-only" ko="공개 데모 · 읽기 전용" /></strong><span><LocalizedText en="Reading state" ko="읽기 상태" />: {paper.reading?.status ?? "unread"} · <LocalizedText en="priority" ko="우선순위" /> {paper.reading?.priority ?? 0}</span></div>}
        </aside>
        </div>

        <div className="paperDocumentApparatus">

        <section className="paperDocumentSection">
          <h3 className="sectionTitle"><LocalizedText en="Research classification" ko="연구 분류" /></h3>
          <div className="tagCloud">{axes.map((topic) => <span className="pill" key={topic.slug}><LocalizedTaxonomyText label={topic.display_name} /></span>)}</div>
          {subaxes.length ? <><h4><LocalizedText en="Adoption sub-areas" ko="도입 세부 영역" /></h4><div className="tagCloud">{subaxes.map((topic) => <span className="pill" key={topic.slug}><LocalizedTaxonomyText label={topic.display_name} /></span>)}</div></> : null}
          <h4><LocalizedText en="Methodology signals" ko="연구방법 신호" /></h4>
          <p className="muted"><LocalizedText en="System heuristic, not author-reported methodology. Verify against the paper before using it as a study-design fact." ko="저자가 보고한 연구방법이 아닌 시스템 휴리스틱입니다. 연구 설계 사실로 사용하기 전에 논문 원문에서 확인하세요." /></p>
          <div className="tagCloud">{methodologies.length ? methodologies.map((topic) => <span className="pill" key={topic.slug}><LocalizedTaxonomyText label={topic.display_name} /></span>) : <span className="muted"><LocalizedText en="No methodology heuristic assigned." ko="분류된 연구방법 휴리스틱이 없습니다." /></span>}</div>
        </section>

        <section className="paperDocumentSection paperDocumentWide researchCardWorkspace">
          <div className="sectionHeadingRow">
            <div>
              <p className="eyebrow"><LocalizedText en="Structured reading" ko="구조화 읽기" /></p>
              <h3 className="sectionTitle"><LocalizedText en="Research Card" ko="리서치 카드" /></h3>
            </div>
            {researchCard ? <div className="rankRow"><span className={`statusBadge status-${researchCard.status === "reviewed" ? "supported" : "insufficient_evidence"}`}>{researchCard.status}</span><span className="pill"><LocalizedText en="evidence" ko="근거" /> · {researchCard.evidence_depth}</span></div> : null}
          </div>
          <p className="muted">
            <LocalizedText
              en="This is the durable reading record for this paper. Candidate fields are extracted only from the abstract or permitted full text; they do not enter question-level synthesis until you mark the card reviewed."
              ko="이 카드는 논문을 한 번 읽고 끝내지 않고 계속 재사용하기 위한 구조화 연구 기록입니다. 후보 항목은 초록 또는 허용된 전문에서만 추출하며, 사용자가 검토 완료로 표시하기 전에는 연구 질문 단위 종합에 포함하지 않습니다."
            />
          </p>
          {researchCard ? (
            !researchCard.persisted && !readOnly ? (
              <>
                <div className="researchCardPreviewGrid">
                  {researchCardFields.map(([key, en, ko]) => {
                    const field = researchCard.fields[key];
                    return <article className="researchCardField" key={key}><strong><LocalizedText en={en} ko={ko} /></strong><p>{field?.value_text ?? <LocalizedText en="No grounded candidate yet." ko="아직 근거가 있는 후보가 없습니다." />}</p><small>{field?.source_locator ?? "insufficient evidence"}</small></article>;
                  })}
                </div>
                <form action={cardStartAction}><button className="button" type="submit"><LocalizedText en="Start structured review →" ko="구조화 검토 시작 →" /></button></form>
              </>
            ) : readOnly || !researchCard.persisted ? (
              <div className="researchCardPreviewGrid">
                {researchCardFields.map(([key, en, ko]) => {
                  const field = researchCard.fields[key];
                  return <article className="researchCardField" key={key}><div className="researchCardFieldHeader"><strong><LocalizedText en={en} ko={ko} /></strong><span className={`statusBadge status-${field?.support_status ?? "insufficient_evidence"}`}>{field?.origin ?? "system_inference"}</span></div><p>{field?.value_text ?? <LocalizedText en="No grounded candidate yet." ko="아직 근거가 있는 후보가 없습니다." />}</p><small>{field?.source_locator ?? "insufficient evidence"}</small></article>;
                })}
              </div>
            ) : (
              <form action={cardUpdateAction} className="researchCardForm">
                <div className="researchCardPreviewGrid">
                  {researchCardFields.map(([key, en, ko]) => {
                    const field = researchCard.fields[key];
                    return (
                      <article className="researchCardField researchCardFieldEditable" key={key}>
                        <div className="researchCardFieldHeader"><strong><LocalizedText en={en} ko={ko} /></strong><span className={`statusBadge status-${field?.support_status ?? "insufficient_evidence"}`}>{field?.origin ?? "system_inference"}</span></div>
                        <textarea className="textarea compactTextarea" name={`field_${key}`} defaultValue={field?.value_text ?? ""} placeholder="Record only what the available evidence supports." />
                        <input className="input researchCardLocator" name={`locator_${key}`} defaultValue={field?.source_locator ?? ""} placeholder="Source locator, e.g. abstract or p. 12 · Methods" />
                      </article>
                    );
                  })}
                </div>
                <div className="researchCardReflectionGrid">
                  <label className="fieldLabel"><LocalizedText en="Important quotes / evidence excerpts" ko="중요 인용 / 근거 발췌" /><textarea className="textarea" name="important_quotes" defaultValue={researchCard.important_quotes ?? ""} placeholder="Quote + page/section locator" /></label>
                  <label className="fieldLabel"><LocalizedText en="My interpretation" ko="내 해석" /><textarea className="textarea" name="my_interpretation" defaultValue={researchCard.my_interpretation ?? ""} placeholder="What does this paper change in your understanding?" /></label>
                  <label className="fieldLabel"><LocalizedText en="Questions raised" ko="새로 생긴 질문" /><textarea className="textarea" name="questions_raised" defaultValue={researchCard.questions_raised ?? ""} placeholder="What is unresolved, surprising, or worth testing next?" /></label>
                  <label className="fieldLabel"><LocalizedText en="Review notes" ko="검토 메모" /><textarea className="textarea" name="review_notes" defaultValue={researchCard.review_notes ?? ""} placeholder="Verification concerns, terminology, caveats…" /></label>
                </div>
                <div className="researchCardSaveRow">
                  <label className="compactFieldLabel"><span><LocalizedText en="Review state" ko="검토 상태" /></span><select className="select" name="card_status" defaultValue={researchCard.status}><option value="candidate">Candidate</option><option value="in_review">In review</option><option value="reviewed">Reviewed · include in synthesis</option></select></label>
                  <button className="button" type="submit"><LocalizedText en="Save Research Card" ko="리서치 카드 저장" /></button>
                </div>
              </form>
            )
          ) : <p className="muted"><LocalizedText en="Research Card extraction is unavailable for this record." ko="이 레코드에서는 리서치 카드 추출을 사용할 수 없습니다." /></p>}
        </section>

        <section className="paperDocumentSection">
          <h3 className="sectionTitle"><LocalizedText en="Bibliographic record" ko="서지정보" /></h3>
          <dl className="detailList">
            <div><dt><LocalizedText en="Authors" ko="저자" /></dt><dd>{paper.authors.map((author) => author.display_name).join(", ") || "—"}</dd></div>
            <div><dt><LocalizedText en="Work type" ko="자료 유형" /></dt><dd>{paper.work_type ?? "—"}</dd></div>
            <div><dt><LocalizedText en="Retraction" ko="철회 상태" /></dt><dd>{paper.retraction_status}</dd></div>
            <div><dt><LocalizedText en="Correction" ko="정정 상태" /></dt><dd>{paper.correction_status}</dd></div>
            <div><dt><LocalizedText en="Citation snapshot" ko="인용 스냅샷" /></dt><dd>{paper.latest_citation_snapshot_at ? new Date(paper.latest_citation_snapshot_at).toLocaleDateString("en-CA") : "—"}</dd></div>
          </dl>
        </section>

        <section className="paperDocumentSection">
          <h3 className="sectionTitle"><LocalizedText en="Tags" ko="태그" /></h3>
          <div className="tagCloud">
            {readOnly ? paper.tags.map((tag) => <span className="pill" key={tag.id}>{tag.name}</span>) : paper.tags.map((tag) => (
              <form action={removeTagAction.bind(null, paper.id)} key={tag.id}>
                <input type="hidden" name="name" value={tag.name} />
                <button className="pill chipButton" type="submit">{tag.name} ×</button>
              </form>
            ))}
          </div>
          {!readOnly ? <form action={tagAction} className="inlineForm"><input className="input" name="name" placeholder="Add tag / 태그 추가" /><button className="button" type="submit"><LocalizedText en="Add" ko="추가" /></button></form> : null}
        </section>

        <section className="paperDocumentSection paperDocumentNotes">
          <h3 className="sectionTitle"><LocalizedText en="Research notes" ko="연구 노트" /></h3>
          {!readOnly ? <form action={noteAction} className="formStack">
            <textarea className="textarea" name="note" required placeholder="Your interpretation, question, or reading note" />
            <input className="input" name="source_locator" placeholder="Optional source locator, e.g. abstract or p. 7" />
            <button className="button" type="submit"><LocalizedText en="Save note" ko="노트 저장" /></button>
          </form> : null}
          <div className="noteStack">
            {paper.notes.map((note) => (
              <div className="noteCard" key={note.id}><p>{note.note_markdown}</p><small>{note.source_locator ?? "No source locator"}</small>
                {!readOnly ? <form action={removeNoteAction.bind(null, paper.id)}><input type="hidden" name="note_id" value={note.id} /><button className="textButton" type="submit"><LocalizedText en="Delete" ko="삭제" /></button></form> : null}
              </div>
            ))}
          </div>
        </section>

        <section className="paperDocumentSection paperDocumentWide">
          <h3 className="sectionTitle"><LocalizedText en="Citation snowballing" ko="인용 확장 탐색" /></h3>
          <p className="muted">
            Local OpenAlex citation IDs are resolved only when both papers exist in this corpus. These are discovery
            paths, not evidence that a cited paper supports the citing paper&apos;s claim.
          </p>
          <div className="citationColumns">
            <div>
              <h4><LocalizedText en="Backward · references in this paper" ko="후방 탐색 · 이 논문의 참고문헌" /></h4>
              <div className="noteStack">
                {snowball?.backward.length ? snowball.backward.map((neighbor) => (
                  <Link className="noteCard citationCard" href={`/library/${neighbor.id}`} key={neighbor.id}>
                    <strong>{neighbor.title}</strong>
                    <small>{neighbor.publication_year ?? "Year unknown"} · citations {neighbor.citation_count ?? "—"}</small>
                  </Link>
                )) : <span className="muted"><LocalizedText en="No locally resolved references in the current corpus." ko="현재 코퍼스에서 연결된 참고문헌이 없습니다." /></span>}
              </div>
            </div>
            <div>
              <h4><LocalizedText en="Forward · local papers citing this paper" ko="전방 탐색 · 이 논문을 인용한 로컬 논문" /></h4>
              <div className="noteStack">
                {snowball?.forward.length ? snowball.forward.map((neighbor) => (
                  <Link className="noteCard citationCard" href={`/library/${neighbor.id}`} key={neighbor.id}>
                    <strong>{neighbor.title}</strong>
                    <small>{neighbor.publication_year ?? "Year unknown"} · citations {neighbor.citation_count ?? "—"}</small>
                  </Link>
                )) : <span className="muted"><LocalizedText en="No locally resolved forward citations in the current corpus." ko="현재 코퍼스에서 연결된 전방 인용 논문이 없습니다." /></span>}
              </div>
            </div>
          </div>
        </section>

        <section className="paperDocumentSection paperDocumentWide paperDocumentProvenance">
          <h3 className="sectionTitle"><LocalizedText en="Provenance" ko="출처 이력" /></h3>
          <dl className="detailList provenanceGrid">
            <div><dt><LocalizedText en="Primary source" ko="기본 출처" /></dt><dd>{paper.primary_source}</dd></div>
            <div><dt><LocalizedText en="Source record ID" ko="출처 레코드 ID" /></dt><dd>{paper.source_record_id}</dd></div>
            <div><dt><LocalizedText en="Retrieved" ko="수집 시각" /></dt><dd>{new Date(paper.retrieved_at).toISOString()}</dd></div>
            <div><dt><LocalizedText en="License" ko="라이선스" /></dt><dd>{paper.license ?? "—"}</dd></div>
          </dl>
          <details><summary>Raw normalized provenance metadata</summary><pre className="codeBlock">{JSON.stringify(paper.provenance, null, 2)}</pre></details>
        </section>

        <section className="paperDocumentSection paperDocumentWide">
          <h3 className="sectionTitle"><LocalizedText en="Private full-text evidence" ko="비공개 논문 전문 근거" /></h3>
          <p className="muted"><LocalizedText en="Attach a PDF only when you own it or have permission to process it privately. The file is stored under Git-ignored local private data, is not redistributed, and OCR is not run automatically." ko="소유권이 있거나 비공개 처리 권한이 있는 PDF만 첨부하세요. 파일은 Git에서 제외된 로컬 비공개 영역에 저장되며 재배포하지 않고 OCR도 자동 실행하지 않습니다." /></p>
          {!readOnly ? <form action={uploadPdfAction.bind(null, paper.id)} className="formStack">
            <input className="input" name="file" type="file" accept="application/pdf,.pdf" required />
            <label className="checkboxLabel"><input name="rights_confirmed" type="checkbox" required /> I confirm I own this file or have permission to process it privately.</label>
            <button className="button" type="submit"><LocalizedText en="Extract private full text" ko="비공개 논문 전문 추출" /></button>
          </form> : <div className="readOnlyPanel"><strong><LocalizedText en="Uploads disabled in public demo" ko="공개 데모에서는 업로드 비활성화" /></strong><span><LocalizedText en="Private PDF processing is available only inside a personal workspace." ko="비공개 PDF 처리는 개인 워크스페이스에서만 사용할 수 있습니다." /></span></div>}
          <p className="metricHelp"><LocalizedText en="When extraction succeeds, page-preserving chunks become available to full-text search and evidence citation." ko="추출이 성공하면 페이지 정보가 보존된 청크를 전문 검색과 근거 인용에 사용할 수 있습니다." /></p>
        </section>
        </div>
      </article>
    </>
  );
}
