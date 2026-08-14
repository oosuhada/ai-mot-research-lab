import Link from "next/link";

import { LocalizedText } from "@/components/LocalizedText";
import {
  askChat,
  getPaper,
  listComparisonSets,
  listResearchQuestions,
  listSavedSearches,
  type PaperDetail,
} from "@/lib/api";

type ChatScope = "corpus" | "papers" | "comparison_set" | "research_question" | "saved_search";

type ChatSearchParams = {
  q?: string;
  scope?: string;
  ids?: string;
  scope_key?: string;
};

function resolveScope(params: ChatSearchParams): { scope: ChatScope; ids: string[]; scopeKey: string } {
  const explicitKey = params.scope_key?.trim();
  if (explicitKey) {
    if (explicitKey === "corpus") return { scope: "corpus", ids: [], scopeKey: "corpus" };
    if (explicitKey === "papers") {
      const ids = (params.ids ?? "").split(",").map((value) => value.trim()).filter(Boolean);
      return { scope: "papers", ids, scopeKey: "papers" };
    }
    const [kind, id] = explicitKey.split(":", 2);
    if (id && (kind === "comparison_set" || kind === "research_question" || kind === "saved_search")) {
      return { scope: kind, ids: [id], scopeKey: explicitKey };
    }
  }

  const legacyScope = params.scope;
  const legacyIds = (params.ids ?? "").split(",").map((value) => value.trim()).filter(Boolean);
  if (legacyScope === "papers") return { scope: "papers", ids: legacyIds, scopeKey: "papers" };
  if (legacyIds[0] && (legacyScope === "comparison_set" || legacyScope === "research_question" || legacyScope === "saved_search")) {
    return { scope: legacyScope, ids: [legacyIds[0]], scopeKey: `${legacyScope}:${legacyIds[0]}` };
  }
  return { scope: "corpus", ids: [], scopeKey: "corpus" };
}

export default async function ChatPage({ searchParams }: { searchParams: Promise<ChatSearchParams> }) {
  const params = await searchParams;
  const question = params.q?.trim() ?? "";
  const resolved = resolveScope(params);
  const [researchQuestions, savedSearches, comparisonSets, selectedPapers] = await Promise.all([
    listResearchQuestions(),
    listSavedSearches(),
    listComparisonSets(),
    resolved.scope === "papers"
      ? Promise.all(resolved.ids.map((id) => getPaper(id))).then((papers) => papers.filter((paper): paper is PaperDetail => Boolean(paper)))
      : Promise.resolve([] as PaperDetail[]),
  ]);
  const answer = question ? await askChat(question, resolved.scope, resolved.ids) : null;

  const followupHref = (followup: string) => {
    const search = new URLSearchParams({ q: followup, scope_key: resolved.scopeKey });
    if (resolved.scope === "papers" && resolved.ids.length) search.set("ids", resolved.ids.join(","));
    return `/chat?${search.toString()}`;
  };

  return (
    <>
      <header className="pageHeader">
        <div>
          <p className="eyebrow"><LocalizedText en="Evidence-grounded Chat" ko="근거 기반 채팅" /></p>
          <h2 className="pageTitle"><LocalizedText en="Ask a named research scope, not a database identifier." ko="데이터베이스 ID가 아니라 이름이 있는 연구 범위에 질문하세요." /></h2>
          <p className="pageIntro">
            <LocalizedText en="Choose the corpus, selected papers, a research question, a saved search, or a comparison set. The answer stays attached to inspectable citations and reports uncertainty explicitly." ko="전체 코퍼스, 선택한 논문, 연구 질문, 저장된 검색, 비교 세트 중 범위를 선택하세요. 답변은 확인 가능한 인용과 연결되고 불확실성을 명시합니다." />
          </p>
        </div>
      </header>

      <section className="evidenceProtocol" aria-label="Evidence scope and provenance policy">
        <div className="evidenceProtocolHeader">
          <span><LocalizedText en="Before asking" ko="질문하기 전에" /></span>
          <strong><LocalizedText en="Scope → locator → provenance → answer" ko="범위 → 근거 위치 → 출처 이력 → 답변" /></strong>
          <p><LocalizedText en="Chat is the final surface. The evidence boundary and unsupported-claim policy are shown first." ko="채팅은 최종 화면입니다. 먼저 근거 범위와 미지원 주장 처리 원칙을 확인합니다." /></p>
        </div>

        <aside className="chatScopePreview evidenceScopeLedger">
          <span className="cardKicker">01 · <LocalizedText en="Current scope" ko="현재 범위" /></span>
          {resolved.scope === "papers" ? (
            <>
              <strong><LocalizedText en={`${selectedPapers.length} selected papers`} ko={`선택한 논문 ${selectedPapers.length}편`} /></strong>
              <div className="chatScopePaperList">
                {selectedPapers.slice(0, 4).map((paper) => <span key={paper.id}>{paper.publication_year ?? "—"} · {paper.title}</span>)}
              </div>
              <Link className="textLink" href="/library"><LocalizedText en="Change selection in Library →" ko="라이브러리에서 선택 변경 →" /></Link>
            </>
          ) : (
            <>
              <strong><LocalizedText en={resolved.scope === "corpus" ? "Entire research corpus" : "Named saved workspace"} ko={resolved.scope === "corpus" ? "전체 연구 코퍼스" : "이름이 지정된 저장 워크스페이스"} /></strong>
              <p><LocalizedText en="The scope selector uses human-readable names. Internal UUIDs are not part of the research workflow." ko="범위 선택기는 사람이 이해할 수 있는 이름을 사용합니다. 내부 UUID는 연구 흐름에 노출하지 않습니다." /></p>
            </>
          )}
        </aside>

        <div className="evidencePolicyLedger">
          <div><span>02</span><strong><LocalizedText en="Locator" ko="근거 위치" /></strong><p><LocalizedText en="Abstract, page, or section locators stay attached to evidence excerpts." ko="초록, 페이지, 섹션 위치를 근거 발췌문과 함께 유지합니다." /></p></div>
          <div><span>03</span><strong><LocalizedText en="Provenance" ko="출처 이력" /></strong><p><LocalizedText en="Paper evidence, system inference, and user notes remain distinct claim kinds." ko="논문 근거, 시스템 추론, 사용자 노트를 서로 다른 주장 유형으로 구분합니다." /></p></div>
          <div><span>04</span><strong><LocalizedText en="Unsupported claims" ko="근거 없는 주장" /></strong><p><code>insufficient_evidence</code><LocalizedText en=" is a valid output, not a failure to fill space." ko="는 유효한 결과이며 빈칸을 채우지 못한 실패가 아닙니다." /></p></div>
        </div>

        <div className="chatComposer evidenceQuestionComposer">
        <form className="chatForm" action="/chat" method="get">
          <label className="fieldLabel" htmlFor="chat-question">
            <LocalizedText en="Research question or challenge" ko="연구 질문 또는 반론" />
            <textarea
              className="input textarea chatQuestionInput"
              id="chat-question"
              name="q"
              required
              minLength={2}
              defaultValue={question}
              placeholder="e.g. What evidence contradicts the claim that AI capability improves firm performance?"
              rows={3}
            />
          </label>
          <div className="chatControls chatControlsNamed">
            <label className="compactFieldLabel">
              <span><LocalizedText en="Evidence scope" ko="근거 범위" /></span>
              <select className="select" name="scope_key" defaultValue={resolved.scopeKey}>
                <option value="corpus">Entire corpus</option>
                {selectedPapers.length ? <option value="papers">Selected papers ({selectedPapers.length})</option> : null}
                {researchQuestions.length ? <optgroup label="Research questions">{researchQuestions.map((item) => <option value={`research_question:${item.id}`} key={item.id}>{item.title}</option>)}</optgroup> : null}
                {savedSearches.length ? <optgroup label="Saved searches">{savedSearches.map((item) => <option value={`saved_search:${item.id}`} key={item.id}>{item.name}</option>)}</optgroup> : null}
                {comparisonSets.length ? <optgroup label="Comparison sets">{comparisonSets.map((item) => <option value={`comparison_set:${item.id}`} key={item.id}>{item.name}</option>)}</optgroup> : null}
              </select>
            </label>
            {resolved.scope === "papers" && resolved.ids.length ? <input type="hidden" name="ids" value={resolved.ids.join(",")} /> : null}
            <button className="button" type="submit"><LocalizedText en="Ask with evidence" ko="근거로 질문하기" /></button>
          </div>
        </form>
        </div>
      </section>

      {question && !answer ? (
        <section className="card" style={{ marginTop: 16 }}>
          <div className="emptyState"><LocalizedText en="The selected scope could not produce a grounded response. Try a broader evidence scope or inspect the linked records." ko="선택한 범위에서 근거 기반 답변을 만들지 못했습니다. 근거 범위를 넓히거나 연결된 레코드를 확인하세요." /></div>
        </section>
      ) : null}

      {answer ? (
        <div className="evidenceAnswerLayout">
          <aside className="evidenceSourceLedger">
            <div className="evidenceSourceLedgerHeader">
              <span><LocalizedText en="Source ledger" ko="출처 기록" /></span>
              <strong><LocalizedText en={`${answer.citations.length} citations`} ko={`인용 ${answer.citations.length}개`} /></strong>
              <small><LocalizedText en="Inspect before reading synthesis." ko="종합 결과를 읽기 전에 확인하세요." /></small>
            </div>
            <div className="evidenceStack">
              {answer.citations.map((citation) => (
                <article className="claimCard" key={citation.index}>
                  <span className="pill">[{citation.index}] {citation.source_locator}</span>
                  <h4 className="evidenceTitle">{citation.paper_title}</h4>
                  <p>{citation.excerpt}</p>
                  <a className="evidenceLink" href={citation.primary_url ?? (citation.doi ? `https://doi.org/${citation.doi}` : "#")} target="_blank" rel="noreferrer"><LocalizedText en="Open source ↗" ko="원문 열기 ↗" /></a>
                </article>
              ))}
            </div>
          </aside>

          <section className="groundedNarrative">
            <div className="resultSummary">
              <strong><LocalizedText en="Grounded response" ko="근거 기반 답변" /></strong>
              <span className="pill"><LocalizedText en="scope" ko="범위" />: {answer.scope_type.replaceAll("_", " ")}</span>
              <span className="pill"><LocalizedText en="provider" ko="제공자" />: {answer.provider}</span>
              <span className="pill"><LocalizedText en="unsupported" ko="미지원 비율" />: {answer.structural_unsupported_claim_rate.toFixed(2)}</span>
            </div>
            <div className="answerStack">
              {answer.paragraphs.map((paragraph, index) => (
                <article className="answerParagraph" key={`${index}-${paragraph.text.slice(0, 20)}`}>
                  <div className="rankRow">
                    <span className={`statusBadge status-${paragraph.support_status}`}>{paragraph.support_status}</span>
                    <span className="pill">{paragraph.claim_kind.replaceAll("_", " ")}</span>
                  </div>
                  <p>{paragraph.text}</p>
                </article>
              ))}
            </div>
            <div className="followupLinks">
              {["What evidence contradicts this?", "Which papers support this most strongly?", "What is still uncertain?", "What theory could explain this?", "What should I read next?"].map((followup) => (
                <Link className="pill" href={followupHref(followup)} key={followup}>{followup}</Link>
              ))}
            </div>
            <div className="callout chatLimitations">
              <strong><LocalizedText en="Current limitations" ko="현재 한계" /></strong>
              {answer.limitations.map((limitation) => <p key={limitation}>{limitation}</p>)}
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
