"use client";

import { useLocalePreference } from "./LocalePreference";

export function LocalizedText({ en, ko }: { en: React.ReactNode; ko: React.ReactNode }) {
  const { locale } = useLocalePreference();
  return <>{locale === "ko" ? ko : en}</>;
}

export function LocalizedTaxonomyText({ label }: { label: string }) {
  const { locale } = useLocalePreference();
  return <>{localizeResearchLabel(label, locale)}</>;
}

export function LocalizedHomeSearch() {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  return (
    <form className="researchThreadSearch" action="/library" method="get">
      <label htmlFor="thread-search">{korean ? "문헌 탐색 시작하기" : "Start a literature thread"}</label>
      <div>
        <input
          id="thread-search"
          name="q"
          placeholder={korean ? "AI 역량 → 조직 변화 → 혁신 성과" : "AI capability → organizational change → innovation performance"}
        />
        <input type="hidden" name="mode" value="hybrid" />
        <button type="submit">{korean ? "근거 추적하기 →" : "Trace evidence →"}</button>
      </div>
    </form>
  );
}

const RESEARCH_LABELS_KO: Record<string, string> = {
  "AI adoption and business value": "AI 도입과 비즈니스 가치",
  "Technology and innovation management": "기술·혁신 경영",
  "AI-enabled organizational change": "AI 기반 조직 변화",
  "Industrial AI and smart operations": "산업 AI와 스마트 운영",
  "AI governance and responsible deployment": "AI 거버넌스와 책임 있는 도입",
  "Agentic systems and enterprise workflows": "에이전틱 시스템과 기업 워크플로",
  "Adoption determinants": "AI 도입 결정요인",
  "Organizational readiness and complementary assets": "조직 준비도와 보완 자산",
  "AI capability development": "AI 역량 개발",
  "Workflow and process transformation": "워크플로와 프로세스 전환",
  "Productivity and operational performance": "생산성과 운영 성과",
  "Innovation outcomes": "혁신 성과",
  "Financial value and ROI measurement": "재무적 가치와 ROI 측정",
  "Scaling and implementation": "확장과 구현",
  "Workforce, skills, and human–AI collaboration": "인력·역량과 인간–AI 협업",
  "Pilot-to-production transition": "파일럿에서 운영 단계로 전환",
  "Systems and workflow integration": "시스템·워크플로 통합",
  "Change management and organizational rollout": "변화관리와 조직 확산",
  "Scaling governance and operating model": "확장 거버넌스와 운영모델",
  "Process automation and augmentation": "프로세스 자동화와 증강",
  "Knowledge-work redesign": "지식노동 재설계",
  "Decision-process redesign": "의사결정 프로세스 재설계",
  "Human-in-the-loop workflow design": "Human-in-the-loop 워크플로 설계",
  "Productivity and efficiency": "생산성과 효율성",
  "Firm and financial performance": "기업·재무 성과",
  "Operational quality and reliability": "운영 품질과 신뢰성",
  "Skills, reskilling, and AI literacy": "역량·재교육과 AI 리터러시",
  "Human–AI collaboration": "인간–AI 협업",
  "Job and role redesign": "직무와 역할 재설계",
  "Employee outcomes and experience": "직원 성과와 경험",
  "Technology characteristics and fit": "기술 특성과 적합성",
  "Organizational capabilities and leadership": "조직 역량과 리더십",
  "Environmental and institutional pressures": "환경·제도적 압력",
  "Trust, risk, and adoption barriers": "신뢰·위험과 도입 장벽",
  "Technology strategy and portfolio management": "기술전략과 포트폴리오 관리",
  "R&D and new product development": "R&D와 신제품 개발",
  "Dynamic capabilities and reconfiguration": "동적 역량과 자원 재구성",
  "Absorptive capacity and knowledge integration": "흡수역량과 지식 통합",
  "Innovation diffusion and ecosystems": "혁신 확산과 생태계",
  "Innovation performance and outcomes": "혁신 성과와 결과",
  "Job, task, and work redesign": "직무·과업·업무 재설계",
  "Human–AI collaboration and augmentation": "인간–AI 협업과 증강",
  "Decision-making and delegation": "의사결정과 위임",
  "Teams, coordination, and structure": "팀·조정과 조직구조",
  "Knowledge work and professional expertise": "지식노동과 전문성",
  "Leadership and change management": "리더십과 변화관리",
  "Smart manufacturing and factory systems": "스마트 제조와 공장 시스템",
  "Predictive maintenance and asset reliability": "예지보전과 자산 신뢰성",
  "Quality, yield, and process control": "품질·수율과 공정 제어",
  "Digital twins and simulation": "디지털 트윈과 시뮬레이션",
  "Supply chain and operations planning": "공급망과 운영계획",
  "Robotics and autonomous operations": "로보틱스와 자율 운영",
  "Responsible AI principles and practice": "책임 있는 AI 원칙과 실행",
  "Trust, transparency, and explainability": "신뢰·투명성과 설명가능성",
  "Accountability and human oversight": "책임성과 인간 감독",
  "AI risk, safety, and assurance": "AI 위험·안전과 보증",
  "Regulation and compliance": "규제와 컴플라이언스",
  "Fairness, ethics, and social impact": "공정성·윤리와 사회적 영향",
  "Agent architectures and tool use": "에이전트 아키텍처와 도구 사용",
  "Multi-agent coordination": "멀티에이전트 조정",
  "Agentic workflow automation": "에이전틱 워크플로 자동화",
  "Human oversight and intervention": "인간 감독과 개입",
  "Delegation, autonomy, and control": "위임·자율성과 통제",
  "Enterprise integration and evaluation": "기업 시스템 통합과 평가",
  "Trust formation and calibration": "신뢰 형성과 조정",
  "Explainable AI and explanation design": "설명가능 AI와 설명 설계",
  "Transparency and disclosure": "투명성과 정보 공개",
  "Interpretability and human understanding": "해석가능성과 인간 이해",
  "AI regulation and policy frameworks": "AI 규제와 정책 프레임워크",
  "Compliance controls and management systems": "컴플라이언스 통제와 관리체계",
  "Data governance and privacy": "데이터 거버넌스와 프라이버시",
  "Sector-specific regulation": "산업별 규제",
  "Bias and fairness": "편향과 공정성",
  "Ethical principles and frameworks": "윤리 원칙과 프레임워크",
  "Social impact and rights": "사회적 영향과 권리",
  "Discrimination and inclusion": "차별과 포용",
  "AI decision support": "AI 의사결정 지원",
  "Algorithmic and automated decisions": "알고리즘·자동화 의사결정",
  "Decision delegation and autonomy": "의사결정 위임과 자율성",
  "Decision quality, bias, and performance": "의사결정 품질·편향과 성과",
  "Coordination and orchestration": "조정과 오케스트레이션",
  "Agent communication and protocols": "에이전트 통신과 프로토콜",
  "Task allocation and planning": "과업 배분과 계획",
  "Collaboration and negotiation": "협업과 협상",
  "Real-time monitoring and synchronization": "실시간 모니터링과 동기화",
  "Simulation and virtual experimentation": "시뮬레이션과 가상 실험",
  "Optimization and control": "최적화와 제어",
  "Lifecycle and systems integration": "수명주기와 시스템 통합",
  "Fault detection and diagnosis": "고장 탐지와 진단",
  "Prognostics and remaining useful life": "예지와 잔여수명 예측",
  "Condition monitoring": "상태 모니터링",
  "Maintenance planning and scheduling": "유지보수 계획과 스케줄링",
  Survey: "설문 연구",
  "Systematic Review": "체계적 문헌고찰",
  Qualitative: "질적 연구",
  Experiment: "실험 연구",
  "Case Study": "사례 연구",
  Conceptual: "개념 연구",
  Simulation: "시뮬레이션",
  "Panel Longitudinal": "패널·종단 연구",
  Econometric: "계량경제 연구",
};

export function localizeResearchLabel(label: string, locale: "en" | "ko"): string {
  return locale === "ko" ? RESEARCH_LABELS_KO[label] ?? label : label;
}
