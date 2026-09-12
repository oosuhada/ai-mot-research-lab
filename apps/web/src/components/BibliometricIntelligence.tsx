"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type {
  BibliometricEdge,
  BibliometricNode,
  BibliometricRelations,
  Landscape,
  LandscapeAxis,
  ResearchSignalLiftResponse,
} from "@/lib/api";

import { localizeResearchLabel } from "./LocalizedText";
import { useLocalePreference } from "./LocalePreference";
import styles from "./BibliometricIntelligence.module.css";

type Props = {
  landscape: Landscape | null;
  relations: BibliometricRelations | null;
  signals: ResearchSignalLiftResponse | null;
};

type LeaderMode = "authors" | "institutions" | "venues";

const SERIES = ["#244d39", "#6d8f7b", "#9c7252", "#5b6f91", "#9b8d52", "#7e6485"];

function safeRatio(numerator: number, denominator: number) {
  return denominator > 0 ? numerator / denominator : 0;
}

function percent(numerator: number, denominator: number) {
  return Math.round(safeRatio(numerator, denominator) * 100);
}

function recentCount(axis: LandscapeAxis, latestYear: number) {
  return axis.years
    .filter((item) => item.year >= latestYear - 1)
    .reduce((sum, item) => sum + item.paper_count, 0);
}

function priorCount(axis: LandscapeAxis, latestYear: number) {
  return axis.years
    .filter((item) => item.year >= latestYear - 3 && item.year <= latestYear - 2)
    .reduce((sum, item) => sum + item.paper_count, 0);
}

function growthPct(axis: LandscapeAxis, latestYear: number) {
  const recent = recentCount(axis, latestYear);
  const prior = priorCount(axis, latestYear);
  if (!prior) return recent ? 100 : 0;
  return Math.round(((recent - prior) / prior) * 100);
}

function compact(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function BubbleTrendMatrix({ axes, years }: { axes: LandscapeAxis[]; years: number[] }) {
  const width = 900;
  const labelWidth = 190;
  const top = 32;
  const rowHeight = 58;
  const plotWidth = width - labelWidth - 24;
  const max = Math.max(
    1,
    ...axes.flatMap((axis) => axis.years.filter((row) => years.includes(row.year)).map((row) => row.paper_count)),
  );
  const step = years.length > 1 ? plotWidth / (years.length - 1) : plotWidth;

  return (
    <div className={styles.svgScroller}>
      <svg
        className={styles.bubbleMatrix}
        viewBox={`0 0 ${width} ${top + rowHeight * axes.length + 28}`}
        role="img"
        aria-label="Topic volume by year bubble matrix"
      >
        {years.map((year, index) => (
          <g key={year}>
            <line
              className={styles.matrixGrid}
              x1={labelWidth + step * index}
              x2={labelWidth + step * index}
              y1={top - 8}
              y2={top + rowHeight * axes.length - 12}
            />
            <text className={styles.matrixYear} x={labelWidth + step * index} y={15} textAnchor="middle">
              {year}
            </text>
          </g>
        ))}
        {axes.map((axis, rowIndex) => {
          const byYear = new Map(axis.years.map((row) => [row.year, row.paper_count]));
          const y = top + rowIndex * rowHeight + 18;
          return (
            <g key={axis.slug}>
              <text className={styles.matrixLabel} x={0} y={y + 4}>{axis.display_name}</text>
              {years.map((year, index) => {
                const count = byYear.get(year) ?? 0;
                const radius = count ? 3 + Math.sqrt(count / max) * 16 : 1.5;
                return (
                  <g key={year}>
                    <circle
                      className={count ? styles.matrixBubble : styles.matrixBubbleEmpty}
                      cx={labelWidth + step * index}
                      cy={y}
                      r={radius}
                    >
                      <title>{`${axis.display_name} · ${year}: ${count.toLocaleString()}`}</title>
                    </circle>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function NetworkDiagram({
  nodes,
  edges,
  korean,
}: {
  nodes: BibliometricNode[];
  edges: BibliometricEdge[];
  korean: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(nodes[0]?.id ?? null);
  const width = 760;
  const height = 430;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 155;
  const maxCount = Math.max(...nodes.map((node) => node.count), 1);
  const maxEdge = Math.max(...edges.map((edge) => edge.weight), 1);
  const positions = new Map(
    nodes.map((node, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1) - Math.PI / 2;
      return [node.id, { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius }];
    }),
  );
  const selected = nodes.find((node) => node.id === selectedId) ?? nodes[0] ?? null;
  const connected = selected
    ? edges
      .filter((edge) => edge.source === selected.id || edge.target === selected.id)
      .map((edge) => ({
        edge,
        node: nodes.find((node) => node.id === (edge.source === selected.id ? edge.target : edge.source)),
      }))
      .filter((item): item is { edge: BibliometricEdge; node: BibliometricNode } => Boolean(item.node))
      .sort((a, b) => b.edge.weight - a.edge.weight)
      .slice(0, 5)
    : [];

  if (!nodes.length) {
    return <div className={styles.emptyPanel}>{korean ? "표시할 관계 데이터가 없습니다." : "No relationship data is available yet."}</div>;
  }

  return (
    <div className={styles.networkLayout}>
      <div className={styles.svgScroller}>
        <svg className={styles.networkSvg} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Research relationship network">
          {edges.map((edge) => {
            const a = positions.get(edge.source);
            const b = positions.get(edge.target);
            if (!a || !b) return null;
            const active = selectedId === edge.source || selectedId === edge.target;
            return (
              <line
                key={`${edge.source}-${edge.target}`}
                className={active ? styles.networkEdgeActive : styles.networkEdge}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                strokeWidth={1 + (edge.weight / maxEdge) * 5}
              />
            );
          })}
          {nodes.map((node, index) => {
            const pos = positions.get(node.id);
            if (!pos) return null;
            const r = 12 + Math.sqrt(node.count / maxCount) * 19;
            const active = node.id === selectedId;
            return (
              <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-label={`${node.label}: ${node.count.toLocaleString()}`}
                onClick={() => setSelectedId(node.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedId(node.id);
                  }
                }}
              >
                <circle
                  className={active ? styles.networkNodeActive : styles.networkNode}
                  cx={pos.x}
                  cy={pos.y}
                  r={r}
                  style={{ fill: SERIES[index % SERIES.length] }}
                />
                <title>{`${node.label}: ${node.count.toLocaleString()}`}</title>
                <text className={styles.networkLabel} x={pos.x} y={pos.y + r + 15} textAnchor="middle">
                  {node.label.length > 22 ? `${node.label.slice(0, 21)}…` : node.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <aside className={styles.networkInspector}>
        {selected ? (
          <>
            <span>{selected.kind === "topic" ? (korean ? "연구주제" : "Research topic") : (korean ? "기관" : "Institution")}</span>
            <h4>{selected.label}</h4>
            <div className={styles.networkStats}>
              <div><small>{korean ? "연결 논문" : "Linked papers"}</small><strong>{selected.count.toLocaleString()}</strong></div>
              <div><small>{korean ? "최근" : "Recent"}</small><strong>{selected.recent_count.toLocaleString()}</strong></div>
            </div>
            {selected.country_code ? <p>{korean ? "국가 코드" : "Country"}: {selected.country_code}</p> : null}
            <strong className={styles.inspectorSubhead}>{korean ? "강한 연결" : "Strong connections"}</strong>
            <ol className={styles.connectionList}>
              {connected.length ? connected.map(({ edge, node }) => (
                <li key={node.id}><span>{node.label}</span><b>{edge.weight.toLocaleString()}</b></li>
              )) : <li>{korean ? "상위 연결이 없습니다." : "No top connection available."}</li>}
            </ol>
          </>
        ) : null}
      </aside>
    </div>
  );
}

function EvolutionTimeline({ axes, korean }: { axes: LandscapeAxis[]; korean: boolean }) {
  const candidates = axes
    .map((axis) => {
      const active = axis.years.filter((row) => row.paper_count > 0);
      return {
        axis,
        first: active.at(0)?.year ?? 0,
        last: active.at(-1)?.year ?? 0,
        peak: Math.max(...active.map((row) => row.paper_count), 0),
      };
    })
    .filter((row) => row.first && row.last)
    .sort((a, b) => b.axis.paper_count - a.axis.paper_count)
    .slice(0, 12);
  const minYear = Math.min(...candidates.map((row) => row.first), new Date().getFullYear());
  const maxYear = Math.max(...candidates.map((row) => row.last), minYear + 1);
  const span = Math.max(maxYear - minYear, 1);

  return (
    <div className={styles.evolutionList}>
      {candidates.map(({ axis, first, last, peak }) => (
        <article key={axis.slug} className={styles.evolutionRow}>
          <div className={styles.evolutionName}>
            <strong>{axis.display_name}</strong>
            <small>{axis.paper_count.toLocaleString()} {korean ? "편" : "papers"}</small>
          </div>
          <div className={styles.evolutionTrack} aria-label={`${axis.display_name}: ${first}–${last}`}>
            <span
              className={styles.evolutionBar}
              style={{
                left: `${((first - minYear) / span) * 100}%`,
                width: `${Math.max(((last - first) / span) * 100, 2)}%`,
                opacity: 0.42 + Math.min(peak / 5000, 0.5),
              }}
            />
            <i style={{ left: `${((first - minYear) / span) * 100}%` }} />
            <i style={{ left: `${((last - minYear) / span) * 100}%` }} />
          </div>
          <div className={styles.evolutionYears}><span>{first}</span><span>{last}</span></div>
        </article>
      ))}
      <div className={styles.timelineScale}><span>{minYear}</span><span>{Math.round((minYear + maxYear) / 2)}</span><span>{maxYear}</span></div>
    </div>
  );
}

function PatentProcedure({ korean }: { korean: boolean }) {
  const stages = korean
    ? [
      ["출원", "우선일·출원번호·권리 범위의 시작점"],
      ["공개", "강의자료 기준 통상 출원 후 18개월 공개"],
      ["심사", "심사청구·우선심사 등 절차에 따라 진행"],
      ["등록", "등록 후 권리 행사·보상청구 등 별도 이슈 발생"],
    ]
    : [
      ["Filing", "Priority, application identity, and the start of the prosecution record"],
      ["Publication", "Course reference: publication is generally framed around an 18-month point"],
      ["Examination", "Examination request and accelerated routes affect timing"],
      ["Registration", "Rights and post-registration actions become a separate analysis layer"],
    ];
  const routes = korean
    ? [
      ["파리조약", "최초 출원 우선일을 보존하며 국가별 직접 출원"],
      ["PCT", "국제단계 후 국가단계 진입 시점을 늦춰 전략 시간을 확보"],
      ["EPC / 유니터리", "유럽 심사·등록 및 단일효 선택을 비교하는 경로"],
      ["국내우선권", "최초 출원의 핵심을 유지하며 보완 발명을 다시 구성"],
      ["조기공개", "기술 공개를 앞당기는 대신 공개 리스크를 함께 검토"],
      ["우선심사 / PPH", "심사 순서를 앞당기는 경로와 적용 요건을 비교"],
    ]
    : [
      ["Paris route", "Direct national filings while preserving the first filing's priority window"],
      ["PCT", "International phase used to defer national-stage decisions and preserve options"],
      ["EPC / Unitary", "European prosecution and post-grant unitary-effect choices"],
      ["Domestic priority", "Reframe an improved invention while referencing an earlier filing"],
      ["Early publication", "Bring disclosure forward while explicitly accepting disclosure risk"],
      ["Accelerated / PPH", "Compare faster examination routes and their eligibility conditions"],
    ];

  return (
    <>
      <div className={styles.patentTimeline}>
        {stages.map(([title, body], index) => (
          <article key={title}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{title}</strong>
            <p>{body}</p>
          </article>
        ))}
      </div>
      <div className={styles.routeGrid}>
        {routes.map(([title, body]) => (
          <article key={title}><strong>{title}</strong><p>{body}</p></article>
        ))}
      </div>
      <small className={styles.legalCaveat}>
        {korean
          ? "강의자료의 비교 구조를 연구·분석용 UI로 옮긴 것입니다. 실제 출원·권리 판단에는 최신 국가별 법령과 전문가 검토가 필요합니다."
          : "This reproduces the course material's comparison structure as an analysis UI. Filing or rights decisions still require current jurisdiction-specific rules and professional review."}
      </small>
    </>
  );
}

export function BibliometricIntelligence({ landscape, relations, signals }: Props) {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  const [leaderMode, setLeaderMode] = useState<LeaderMode>("authors");

  const latestYear = landscape?.years.at(-1)?.year ?? new Date().getFullYear();
  const topAxes = useMemo(
    () => [...(landscape?.axes ?? [])].sort((a, b) => b.paper_count - a.paper_count).slice(0, 6),
    [landscape?.axes],
  );
  const recentYears = useMemo(
    () => (landscape?.years ?? []).map((item) => item.year).filter((year) => year >= latestYear - 9),
    [landscape?.years, latestYear],
  );
  const trendData = recentYears.map((year) => {
    const row: Record<string, string | number> = { year: String(year) };
    for (const axis of topAxes) {
      row[axis.slug] = axis.years.find((item) => item.year === year)?.paper_count ?? 0;
    }
    return row;
  });
  const axisMetrics = topAxes.map((axis) => ({
    slug: axis.slug,
    label: localizeResearchLabel(axis.display_name, locale),
    count: axis.paper_count,
    share: percent(axis.paper_count, landscape?.total_papers ?? 0),
    recent: recentCount(axis, latestYear),
    growth: growthPct(axis, latestYear),
  }));
  const scatterData = axisMetrics.map((row) => ({ ...row, size: Math.max(row.count, 1) }));
  const leaders = leaderMode === "authors"
    ? landscape?.top_authors ?? []
    : leaderMode === "institutions"
      ? landscape?.top_institutions ?? []
      : landscape?.top_venues ?? [];
  const taxonomyRows = [...(landscape?.axes ?? [])]
    .sort((a, b) => b.paper_count - a.paper_count)
    .slice(0, 12);
  const normalizedSignals = signals?.normalized_signals ?? [];

  if (!landscape) {
    return (
      <section className={styles.emptyPage}>
        <h2>{korean ? "서지 인텔리전스를 불러올 수 없습니다." : "Bibliometric intelligence is temporarily unavailable."}</h2>
        <p>{korean ? "논문 라이브러리와 연구 신호 화면은 계속 사용할 수 있습니다." : "Library and Signal Lift remain available."}</p>
      </section>
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>{korean ? "서지정보 분석 · Research Intelligence" : "Bibliometrics · Research Intelligence"}</p>
          <h2>{korean ? "연구의 크기보다 움직임과 빈 공간을 봅니다." : "See movement and whitespace, not only corpus size."}</h2>
          <p>
            {korean
              ? "강의자료의 출원 트렌드, 점유율, 기술분류, 세대별 진화, 텍스트 네트워크, 선도자, 지식흐름 분석을 현재 AI×MOT 논문 코퍼스에 맞게 통합했습니다."
              : "This workspace adapts the course material's trend, share, classification, evolution, network, leader, and knowledge-flow views to the live AI×MOT corpus."}
          </p>
        </div>
        <div className={styles.heroStats}>
          <article><span>{korean ? "논문" : "Papers"}</span><strong>{landscape.total_papers.toLocaleString()}</strong></article>
          <article><span>{korean ? "전문" : "Full text"}</span><strong>{landscape.full_text_papers.toLocaleString()}</strong></article>
          <article><span>{korean ? "특허" : "Patents"}</span><strong>{(relations?.patent_total ?? 0).toLocaleString()}</strong></article>
          <article><span>{korean ? "최근 구간" : "Recent window"}</span><strong>{relations?.recent_window ?? `${latestYear - 1}–${latestYear}`}</strong></article>
        </div>
      </header>

      <nav className={styles.jumpNav} aria-label="Bibliometric sections">
        <a href="#trend">01 {korean ? "트렌드·비중" : "Trend & share"}</a>
        <a href="#evolution">02 {korean ? "주제 진화" : "Evolution"}</a>
        <a href="#network">03 {korean ? "연구 네트워크" : "Network"}</a>
        <a href="#leaders">04 {korean ? "선도자" : "Leaders"}</a>
        <a href="#taxonomy">05 {korean ? "분류체계" : "Taxonomy"}</a>
        <a href="#flow">06 {korean ? "지식 흐름" : "Knowledge flow"}</a>
        <a href="#patents">07 {korean ? "특허·논문 브리지" : "Patent bridge"}</a>
      </nav>

      <section className={styles.section} id="trend">
        <header className={styles.sectionHeader}>
          <div><span>01</span><p>{korean ? "트렌드 · 비중 · 성장" : "Trend · share · growth"}</p></div>
          <h3>{korean ? "어떤 연구축이 크고, 어느 축이 빠르게 움직이나요?" : "Which research axes are large, and which are moving fastest?"}</h3>
          <p>{korean ? "강의자료 p.8·p.14의 시계열/비중/성장률 구성을 논문 연구축으로 재구성했습니다." : "Adapts the course's p.8/p.14 time-series, share, and growth views to research axes."}</p>
        </header>
        <div className={styles.twoColumn}>
          <article className={styles.chartPanel}>
            <div className={styles.panelTitle}><strong>{korean ? "연도별 연구축 추이" : "Research-axis trend"}</strong><small>{recentYears.at(0)}–{recentYears.at(-1)}</small></div>
            <div className={styles.chartBox}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 5" vertical={false} />
                  <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                  <YAxis width={44} tick={{ fontSize: 11 }} tickFormatter={(value) => compact(Number(value))} />
                  <Tooltip formatter={(value, name) => [Number(value).toLocaleString(), topAxes.find((axis) => axis.slug === name)?.display_name ?? name]} />
                  {topAxes.slice(0, 5).map((axis, index) => (
                    <Line key={axis.slug} dataKey={axis.slug} stroke={SERIES[index]} strokeWidth={2.2} dot={false} type="monotone" />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className={styles.chartLegend}>{topAxes.slice(0, 5).map((axis, index) => <span key={axis.slug}><i style={{ background: SERIES[index] }} />{localizeResearchLabel(axis.display_name, locale)}</span>)}</div>
          </article>

          <article className={styles.chartPanel}>
            <div className={styles.panelTitle}><strong>{korean ? "비중 × 최근 성장" : "Share × recent growth"}</strong><small>{korean ? "원 크기 = 전체 논문수" : "Bubble size = total papers"}</small></div>
            <div className={styles.chartBox}>
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 16, right: 18, bottom: 22, left: 4 }}>
                  <CartesianGrid strokeDasharray="3 5" />
                  <XAxis type="number" dataKey="share" name="Share" unit="%" tick={{ fontSize: 11 }} />
                  <YAxis type="number" dataKey="growth" name="Growth" unit="%" width={46} tick={{ fontSize: 11 }} />
                  <ZAxis type="number" dataKey="size" range={[90, 720]} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(value, name) => [name === "size" ? Number(value).toLocaleString() : `${value}%`, name]} />
                  <Scatter data={scatterData} fill="#244d39" />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className={styles.metricRows}>{axisMetrics.map((row) => <div key={row.slug}><span>{row.label}</span><b>{row.share}%</b><em>{row.growth >= 0 ? "+" : ""}{row.growth}%</em></div>)}</div>
          </article>
        </div>
        <article className={styles.widePanel}>
          <div className={styles.panelTitle}><strong>{korean ? "연도별 연구축 버블 매트릭스" : "Year × research-axis bubble matrix"}</strong><small>{korean ? "강의자료 p.8 방식" : "Course p.8 pattern"}</small></div>
          <BubbleTrendMatrix axes={topAxes.slice(0, 5)} years={recentYears} />
        </article>
      </section>

      <section className={styles.section} id="evolution">
        <header className={styles.sectionHeader}>
          <div><span>02</span><p>{korean ? "연구주제 진화" : "Topic evolution"}</p></div>
          <h3>{korean ? "어떤 주제가 언제 등장하고 얼마나 오래 이어졌나요?" : "When did each topic emerge, and how long has it persisted?"}</h3>
          <p>{korean ? "강의자료 p.11의 기술세대 타임라인을 연구주제의 등장·성장·지속 구간으로 변환했습니다." : "Adapts the p.11 technology-generation timeline into topic emergence and persistence."}</p>
        </header>
        <article className={styles.widePanel}><EvolutionTimeline axes={landscape.subaxes.length ? landscape.subaxes : landscape.axes} korean={korean} /></article>
      </section>

      <section className={styles.section} id="network">
        <header className={styles.sectionHeader}>
          <div><span>03</span><p>{korean ? "연구주제 네트워크" : "Research network"}</p></div>
          <h3>{korean ? "어떤 연구주제가 같은 논문 안에서 함께 움직이나요?" : "Which research topics move together inside the same papers?"}</h3>
          <p>{korean ? "강의자료 p.13의 제목·초록 네트워크 아이디어를 현재 taxonomy co-occurrence로 구현했습니다." : "Implements the p.13 text-network idea with current taxonomy co-occurrence evidence."}</p>
        </header>
        <article className={styles.widePanel}>
          <NetworkDiagram nodes={relations?.topic_nodes ?? []} edges={relations?.topic_edges ?? []} korean={korean} />
        </article>
        <div className={styles.signalRibbon}>
          {(normalizedSignals.slice(0, 8)).map((signal) => (
            <Link key={`${signal.signal_type}-${signal.normalized_label}`} href={signal.example_paper_id ? `/library/${signal.example_paper_id}` : "/signal-lift"}>
              <span>{signal.signal_type.replaceAll("_", " ")}</span><strong>{signal.label}</strong><small>{signal.paper_count.toLocaleString()} {korean ? "편" : "papers"}</small>
            </Link>
          ))}
        </div>
      </section>

      <section className={styles.section} id="leaders">
        <header className={styles.sectionHeader}>
          <div><span>04</span><p>{korean ? "선도자·영향 지형" : "Leader landscape"}</p></div>
          <h3>{korean ? "누가 이 연구 지형에서 반복적으로 나타나나요?" : "Who repeatedly appears in this research landscape?"}</h3>
          <p>{korean ? "강의자료 p.9의 출원인 분석을 저자·기관·학술지 관점으로 옮겼습니다." : "Adapts the p.9 applicant ranking to authors, institutions, and venues."}</p>
        </header>
        <article className={styles.widePanel}>
          <div className={styles.segmented}>
            {(["authors", "institutions", "venues"] as LeaderMode[]).map((mode) => (
              <button key={mode} type="button" aria-pressed={leaderMode === mode} onClick={() => setLeaderMode(mode)}>
                {mode === "authors" ? (korean ? "연구자" : "Researchers") : mode === "institutions" ? (korean ? "기관" : "Institutions") : (korean ? "학술지" : "Venues")}
              </button>
            ))}
          </div>
          <div className={styles.leaderChart}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={leaders.slice(0, 10)} layout="vertical" margin={{ top: 6, right: 26, bottom: 4, left: 34 }}>
                <CartesianGrid strokeDasharray="3 5" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(value) => compact(Number(value))} />
                <YAxis type="category" dataKey="name" width={160} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => Number(value).toLocaleString()} />
                <Bar dataKey="paper_count" fill="#244d39" radius={[0, 5, 5, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <small className={styles.panelNote}>{korean ? "논문 수 기준의 corpus-local 리더보드입니다. 권위나 질의 순위로 해석하지 마세요." : "Corpus-local volume leaderboard only; do not read it as authority or quality ranking."}</small>
        </article>
      </section>

      <section className={styles.section} id="taxonomy">
        <header className={styles.sectionHeader}>
          <div><span>05</span><p>{korean ? "분류체계·기술비중" : "Taxonomy & share"}</p></div>
          <h3>{korean ? "현재 코퍼스는 어떤 연구축으로 구성되어 있나요?" : "How is the current corpus partitioned across research axes?"}</h3>
          <p>{korean ? "강의자료 p.10의 CPC 비중 분석을 AI×MOT 연구축 분류체계에 적용했습니다." : "Applies the p.10 CPC-share logic to the AI×MOT taxonomy."}</p>
        </header>
        <article className={styles.widePanel}>
          <div className={styles.taxonomyStrip}>
            {taxonomyRows.map((axis, index) => (
              <Link
                href={`/library?view=browse&axis=${encodeURIComponent(axis.slug)}`}
                key={axis.slug}
                className={styles.taxonomyBlock}
                style={{ flexGrow: Math.max(axis.paper_count, 1), background: `${SERIES[index % SERIES.length]}18`, borderColor: `${SERIES[index % SERIES.length]}55` }}
              >
                <span>{percent(axis.paper_count, landscape.total_papers)}%</span>
                <strong>{localizeResearchLabel(axis.display_name, locale)}</strong>
                <small>{axis.paper_count.toLocaleString()}</small>
              </Link>
            ))}
          </div>
        </article>
      </section>

      <section className={styles.section} id="flow">
        <header className={styles.sectionHeader}>
          <div><span>06</span><p>{korean ? "기관 지식흐름" : "Institution knowledge flow"}</p></div>
          <h3>{korean ? "어떤 기관들이 같은 연구 결과를 함께 만들어내나요?" : "Which institutions repeatedly produce research together?"}</h3>
          <p>{korean ? "강의자료 p.16의 Brain Drain/클러스터 분석 아이디어를, 현재 DB가 안전하게 말할 수 있는 공동저자·기관 협업 네트워크로 변환했습니다." : "Adapts the p.16 brain-drain/cluster idea into the collaboration network that the current affiliation data can safely support."}</p>
        </header>
        <article className={styles.widePanel}>
          <NetworkDiagram nodes={relations?.institution_nodes ?? []} edges={relations?.institution_edges ?? []} korean={korean} />
        </article>
        <div className={styles.caveatBox}><strong>{korean ? "해석 경계" : "Interpretation boundary"}</strong><p>{korean ? "현재 AuthorInstitution은 연도별 소속 이력을 보존하지 않으므로 이 그래프를 인력 유출입이나 Brain Drain으로 부르지 않습니다. 지금은 공동 논문 기반 Knowledge Flow입니다." : "AuthorInstitution does not preserve year-specific affiliation history, so this is not labeled migration or brain drain. It is a shared-paper knowledge-flow view."}</p></div>
      </section>

      <section className={styles.section} id="patents">
        <header className={styles.sectionHeader}>
          <div><span>07</span><p>{korean ? "특허 인텔리전스 · 논문-특허 브리지" : "Patent intelligence · paper-patent bridge"}</p></div>
          <h3>{korean ? "과학적 연구축이 기술개발 신호로 이어지는 지점을 준비합니다." : "Prepare the bridge from scientific research axes to technology-development signals."}</h3>
          <p>{korean ? "강의자료 p.8~10·p.15와 2주차의 특허 절차/제도 비교를 한 모듈로 묶었습니다." : "Combines the patent trend/classification/bridge ideas with the week-2 process and route comparisons."}</p>
        </header>

        {(relations?.patent_total ?? 0) === 0 ? (
          <div className={styles.patentEmpty}>
            <div><span>0</span><strong>{korean ? "현재 PatentDocument 레코드" : "PatentDocument records"}</strong></div>
            <p>{korean ? "특허 시각화 엔진은 구현되어 있지만 아직 WIPS ON 특허가 import되지 않았습니다. 특허를 넣는 순간 국가별 출원 트렌드, 출원인 순위, CPC 비중, 논문-특허 lexical bridge가 자동 활성화됩니다." : "The visualization engine is implemented, but no WIPS ON patent records are imported yet. Jurisdiction trend, applicant ranking, CPC share, and paper-patent lexical bridge activate once patent data arrives."}</p>
            <Link className={styles.primaryLink} href="/imports">{korean ? "WIPS ON 특허 가져오기 →" : "Import WIPS ON patents →"}</Link>
          </div>
        ) : (
          <div className={styles.patentAnalyticsGrid}>
            <article className={styles.chartPanel}>
              <div className={styles.panelTitle}><strong>{korean ? "국가별 특허 비중" : "Patent share by jurisdiction"}</strong></div>
              <div className={styles.chartBoxSmall}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={relations?.patent_jurisdictions ?? []} margin={{ top: 10, right: 16, bottom: 10, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 5" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => compact(Number(value))} />
                    <Tooltip formatter={(value) => Number(value).toLocaleString()} />
                    <Bar dataKey="count" fill="#244d39" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </article>
            <article className={styles.rankPanel}>
              <strong>{korean ? "상위 출원인" : "Top applicants"}</strong>
              {(relations?.patent_applicants ?? []).slice(0, 10).map((item, index) => <div key={item.label}><span>{index + 1}. {item.label}</span><b>{item.count.toLocaleString()}</b></div>)}
            </article>
            <article className={styles.rankPanel}>
              <strong>{korean ? "상위 CPC" : "Top CPC"}</strong>
              {(relations?.patent_cpc ?? []).slice(0, 10).map((item, index) => <div key={item.label}><span>{index + 1}. {item.label}</span><b>{item.count.toLocaleString()}</b></div>)}
            </article>
            <article className={styles.rankPanel}>
              <strong>{korean ? "논문 ↔ 특허 브리지 후보" : "Paper ↔ patent bridge candidates"}</strong>
              {(relations?.paper_patent_bridge ?? []).slice(0, 10).map((item) => <div key={`${item.paper_topic}-${item.patent_concept}`}><span>{item.paper_topic} → {item.patent_concept}</span><b>{item.count.toLocaleString()}</b></div>)}
            </article>
          </div>
        )}

        <article className={styles.widePanel}>
          <div className={styles.panelTitle}><strong>{korean ? "특허 절차·국제출원 Route Explorer" : "Patent process & international route explorer"}</strong><small>{korean ? "2주차 강의 구조 적용" : "Week-2 course structure"}</small></div>
          <PatentProcedure korean={korean} />
        </article>
      </section>

      {relations?.caveats?.length ? (
        <section className={styles.caveats}>
          <strong>{korean ? "데이터 해석 규칙" : "Interpretation rules"}</strong>
          <ul>{relations.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}</ul>
        </section>
      ) : null}

      <section className={styles.actionRail}>
        <div><span>{korean ? "동향" : "Landscape"}</span><strong>{korean ? "움직임을 확인" : "See movement"}</strong></div>
        <i>→</i>
        <div><span>{korean ? "신호" : "Signals"}</span><strong>{korean ? "반복 한계·새 방법 포착" : "Find repeated limits"}</strong></div>
        <i>→</i>
        <div><span>{korean ? "기회" : "Opportunities"}</span><strong>{korean ? "빈 조합 검토" : "Inspect whitespace"}</strong></div>
        <i>→</i>
        <div><span>{korean ? "질문" : "Question"}</span><strong>{korean ? "인용 가능한 워크스페이스 생성" : "Build a citable workspace"}</strong></div>
        <footer>
          <Link href="/signal-lift">{korean ? "연구 신호 보기 →" : "Open Signal Lift →"}</Link>
          <Link href="/opportunities">{korean ? "연구 기회 보기 →" : "Open Opportunities →"}</Link>
        </footer>
      </section>
    </div>
  );
}
