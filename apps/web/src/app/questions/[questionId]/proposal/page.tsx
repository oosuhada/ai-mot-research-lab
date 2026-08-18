import Link from "next/link";
import { notFound } from "next/navigation";

import { LocalizedText } from "@/components/LocalizedText";
import { getResearchProposal, getResearchQuestion } from "@/lib/api";

export default async function ProposalBuilderPage({
  params,
}: {
  params: Promise<{ questionId: string }>;
}) {
  const { questionId } = await params;
  const [question, proposal] = await Promise.all([
    getResearchQuestion(questionId),
    getResearchProposal(questionId),
  ]);
  if (!question || !proposal) notFound();

  const ready = proposal.sections.filter((section) => section.evidence_state === "ready").length;
  const partial = proposal.sections.filter((section) => section.evidence_state === "partial").length;
  const missing = proposal.sections.filter((section) => section.evidence_state === "missing").length;

  return (
    <>
      <header className="proposalBuilderHeader">
        <div>
          <p className="eyebrow"><LocalizedText en="Research Proposal Builder" ko="연구계획서 빌더" /></p>
          <h2 className="paperDetailTitle">{question.title}</h2>
          <p className="pageIntro">{question.question_text}</p>
          <div className="headerActionRow">
            <Link className="secondaryButton" href={`/questions/${question.id}`}><LocalizedText en="Back to research thread →" ko="연구 스레드로 돌아가기 →" /></Link>
            <Link className="secondaryButton" href={`/chat?scope=research_question&ids=${question.id}`}><LocalizedText en="Interrogate the evidence →" ko="근거에 질문하기 →" /></Link>
          </div>
        </div>
        <div className="proposalReadinessPanel">
          <strong>{proposal.readiness_pct}%</strong>
          <span><LocalizedText en="workflow readiness" ko="워크플로 준비도" /></span>
          <small><LocalizedText en="Diagnostic, not a thesis-quality score" ko="논문 품질 점수가 아닌 진행 진단값" /></small>
        </div>
      </header>

      <main className="proposalBuilderDocument">
        <aside className="proposalBuilderRail">
          <div><span>READY</span><strong>{ready}</strong><small><LocalizedText en="developed sections" ko="충분히 발전한 섹션" /></small></div>
          <div><span>PARTIAL</span><strong>{partial}</strong><small><LocalizedText en="needs development" ko="추가 발전 필요" /></small></div>
          <div><span>MISSING</span><strong>{missing}</strong><small><LocalizedText en="not yet framed" ko="아직 정의되지 않음" /></small></div>
          <div><span>CORE</span><strong>{question.workflow?.core_papers ?? 0}</strong><small><LocalizedText en="core papers" ko="핵심 논문" /></small></div>
          <div><span>REVIEWED</span><strong>{question.workflow?.reviewed_cards ?? 0}</strong><small><LocalizedText en="Research Cards" ko="검토 리서치 카드" /></small></div>
        </aside>

        <div className="proposalBuilderBody">
          <section className="proposalProtocol">
            <p className="eyebrow"><LocalizedText en="Assembly rule" ko="조립 원칙" /></p>
            <h3><LocalizedText en="This page assembles what you have actually developed; it does not write missing scholarship for you." ko="이 화면은 실제로 발전시킨 연구 내용을 조립하며, 비어 있는 학술적 논리를 임의로 작성하지 않습니다." /></h3>
            <p><LocalizedText en="Missing sections remain visible. Literature synthesis is limited to reviewed Research Cards, gap language remains a candidate until challenged, and design choices stay editable in the Research Question workspace." ko="비어 있는 섹션은 그대로 표시됩니다. 문헌 종합은 검토 완료한 리서치 카드에 한정하고, 연구공백은 반증 전까지 후보로 유지하며, 연구설계는 Research Question 워크스페이스에서 계속 수정할 수 있습니다." /></p>
          </section>

          <div className="proposalSectionStack">
            {proposal.sections.map((section, index) => (
              <section className={`proposalSection proposalSection-${section.evidence_state}`} key={section.key}>
                <div className="proposalSectionIndex">{String(index + 1).padStart(2, "0")}</div>
                <div className="proposalSectionContent">
                  <div className="proposalSectionHeading">
                    <h3>{section.title}</h3>
                    <span className={`statusBadge status-${section.evidence_state === "ready" ? "supported" : "insufficient_evidence"}`}>{section.evidence_state}</span>
                  </div>
                  {section.content ? <div className="proposalSectionText">{section.content.split("\n").map((line, lineIndex) => line.startsWith("- ") ? <p className="proposalReferenceLine" key={`${section.key}-${lineIndex}`}>{line}</p> : <p key={`${section.key}-${lineIndex}`}>{line}</p>)}</div> : <p className="proposalMissingText"><LocalizedText en="Not developed yet. Return to the research thread and resolve this decision before treating the proposal as coherent." ko="아직 발전되지 않은 항목입니다. 연구 스레드로 돌아가 이 결정을 해결한 뒤 연구계획서가 일관되었다고 판단하세요." /></p>}
                </div>
              </section>
            ))}
          </div>

          <section className="proposalMarkdownPanel">
            <div className="sectionHeadingRow"><div><p className="eyebrow"><LocalizedText en="Portable outline" ko="이식 가능한 개요" /></p><h3 className="sectionTitle"><LocalizedText en="Markdown research outline" ko="Markdown 연구 개요" /></h3></div><span className="pill"><LocalizedText en="evidence-aware draft skeleton" ko="근거 상태를 보존한 초안 골격" /></span></div>
            <p className="muted"><LocalizedText en="Use this as a working outline in your own writing environment. It intentionally contains incomplete sections rather than inventing citations or claims." ko="자신의 글쓰기 환경에서 작업 개요로 사용하세요. 인용이나 주장을 지어내지 않고 미완성 섹션을 의도적으로 그대로 둡니다." /></p>
            <pre className="proposalMarkdownPreview">{proposal.markdown}</pre>
          </section>
        </div>
      </main>
    </>
  );
}
