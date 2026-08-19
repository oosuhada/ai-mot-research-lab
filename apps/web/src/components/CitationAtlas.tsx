"use client";

import Link from "next/link";
import { scaleLinear } from "d3-scale";
import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState, type ReactNode } from "react";

import type { CorpusCoverage, LandscapeAxis, LandscapeYear } from "@/lib/api";

import { localizeResearchLabel } from "./LocalizedText";
import { useLocalePreference } from "./LocalePreference";
import styles from "./CitationAtlas.module.css";

type CitationAtlasProps = {
  axes: LandscapeAxis[];
  subaxes: LandscapeAxis[];
  years: LandscapeYear[];
  totalPapers: number;
  coverage: CorpusCoverage | null;
};

type SortMode = "volume" | "evidence" | "recent";

function safeRatio(numerator: number, denominator: number) {
  return denominator > 0 ? numerator / denominator : 0;
}

function percent(numerator: number, denominator: number) {
  return Math.round(safeRatio(numerator, denominator) * 100);
}

function recentCount(territory: LandscapeAxis, latestYear: number | null) {
  if (!latestYear) return 0;
  return territory.years
    .filter((item) => item.year >= latestYear - 1)
    .reduce((sum, item) => sum + item.paper_count, 0);
}

function evidenceLayers(territory: LandscapeAxis) {
  const deep = Math.min(territory.full_text_paper_count, territory.paper_count);
  const abstractReady = Math.min(Math.max(territory.abstract_paper_count, deep), territory.paper_count);
  return {
    deep,
    abstractOnly: Math.max(abstractReady - deep, 0),
    metadataOnly: Math.max(territory.paper_count - abstractReady, 0),
  };
}

function Sparkline({
  years,
  label,
  compact = false,
}: {
  years: LandscapeYear[];
  label: string;
  compact?: boolean;
}) {
  const width = compact ? 228 : 390;
  const height = compact ? 74 : 118;
  const paddingX = compact ? 4 : 8;
  const paddingTop = compact ? 8 : 12;
  const paddingBottom = compact ? 8 : 18;
  const maxCount = Math.max(...years.map((item) => item.paper_count), 1);
  const minYear = years.at(0)?.year ?? 0;
  const maxYear = years.at(-1)?.year ?? minYear + 1;
  const x = scaleLinear().domain([minYear, Math.max(maxYear, minYear + 1)]).range([paddingX, width - paddingX]);
  const y = scaleLinear().domain([0, maxCount]).range([height - paddingBottom, paddingTop]);
  const points = years.map((item) => `${x(item.year)},${y(item.paper_count)}`).join(" ");
  const areaPoints = years.length
    ? `${paddingX},${height - paddingBottom} ${points} ${width - paddingX},${height - paddingBottom}`
    : "";

  return (
    <svg
      className={compact ? styles.sparklineCompact : styles.sparkline}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label}
    >
      <line className={styles.sparkBaseline} x1={paddingX} y1={height - paddingBottom} x2={width - paddingX} y2={height - paddingBottom} />
      {areaPoints ? <polygon className={styles.sparkArea} points={areaPoints} /> : null}
      {points ? <polyline className={styles.sparkLine} points={points} /> : null}
      {!compact ? years.map((item) => (
        <g key={item.year}>
          <circle className={styles.sparkPoint} cx={x(item.year)} cy={y(item.paper_count)} r="2.6" />
          <text className={styles.sparkYear} x={x(item.year)} y={height - 4} textAnchor="middle">{String(item.year).slice(-2)}</text>
        </g>
      )) : null}
    </svg>
  );
}

export function CitationAtlas({ axes, subaxes, years, totalPapers, coverage }: CitationAtlasProps) {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  const reduceMotion = useReducedMotion();
  const [sortMode, setSortMode] = useState<SortMode>("volume");
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [expandedSlugs, setExpandedSlugs] = useState<string[]>([]);

  const latestYear = years.at(-1)?.year ?? null;
  const defaultAxis = useMemo(
    () => [...axes].sort((a, b) => b.paper_count - a.paper_count)[0] ?? null,
    [axes],
  );
  const allTerritories = useMemo(() => [...axes, ...subaxes], [axes, subaxes]);
  const territoryBySlug = useMemo(
    () => new Map(allTerritories.map((territory) => [territory.slug, territory])),
    [allTerritories],
  );
  const selectedTerritory = territoryBySlug.get(activeSlug ?? "") ?? defaultAxis;
  const selectedParent = selectedTerritory?.parent_slug
    ? territoryBySlug.get(selectedTerritory.parent_slug) ?? null
    : selectedTerritory;
  const childrenByParent = useMemo(() => {
    const groups = new Map<string, LandscapeAxis[]>();
    for (const territory of subaxes) {
      if (!territory.parent_slug) continue;
      const group = groups.get(territory.parent_slug) ?? [];
      group.push(territory);
      groups.set(territory.parent_slug, group);
    }
    return groups;
  }, [subaxes]);

  function sortTerritories(items: LandscapeAxis[]) {
    const rows = [...items];
    return rows.sort((a, b) => {
      if (sortMode === "evidence") {
        return safeRatio(b.full_text_paper_count, b.paper_count) - safeRatio(a.full_text_paper_count, a.paper_count);
      }
      if (sortMode === "recent") {
        return recentCount(b, latestYear) - recentCount(a, latestYear);
      }
      return b.paper_count - a.paper_count;
    });
  }

  const sortedAxes = sortTerritories(axes);

  function selectTerritory(territory: LandscapeAxis) {
    setActiveSlug(territory.slug);
  }

  function toggleExpanded(territory: LandscapeAxis) {
    setActiveSlug(territory.slug);
    setExpandedSlugs((current) => current.includes(territory.slug)
      ? current.filter((slug) => slug !== territory.slug)
      : [...current, territory.slug]);
  }

  function collapseAll() {
    setExpandedSlugs([]);
  }

  const selectedHref = selectedTerritory
    ? `/library?view=browse&axis=${encodeURIComponent(selectedTerritory.slug)}`
    : "/library?view=browse";
  const selectedCount = selectedTerritory?.paper_count ?? totalPapers;
  const selectedYears = selectedTerritory?.years.length ? selectedTerritory.years : years;
  const selectedAbstractPct = selectedTerritory
    ? percent(selectedTerritory.abstract_paper_count, selectedTerritory.paper_count)
    : percent(coverage?.abstract_ready ?? 0, coverage?.total_records ?? totalPapers);
  const selectedFullTextPct = selectedTerritory
    ? percent(selectedTerritory.full_text_paper_count, selectedTerritory.paper_count)
    : percent(coverage?.full_text_ready ?? 0, coverage?.total_records ?? totalPapers);
  const selectedOaPct = selectedTerritory
    ? percent(selectedTerritory.oa_paper_count, selectedTerritory.paper_count)
    : 0;
  const latestCorpusYear = years.at(-1);
  const previousCorpusYear = years.at(-2);
  const latestCoverageDelta = latestCorpusYear && previousCorpusYear && previousCorpusYear.paper_count > 0
    ? Math.round(((latestCorpusYear.paper_count - previousCorpusYear.paper_count) / previousCorpusYear.paper_count) * 100)
    : null;

  function renderTerritoryGroup(items: LandscapeAxis[], depth = 0): ReactNode {
    const sorted = sortTerritories(items);
    const maxCount = Math.max(...items.map((item) => item.paper_count), 1);
    const widthScale = scaleLinear().domain([0, maxCount]).range([18, 100]);

    return sorted.map((territory, index) => {
      const layers = evidenceLayers(territory);
      const isSelected = selectedTerritory?.slug === territory.slug;
      const recent = recentCount(territory, latestYear);
      const children = childrenByParent.get(territory.slug) ?? [];
      const childCount = children.length;
      const expanded = expandedSlugs.includes(territory.slug);
      const drillLabel = expanded
        ? korean ? `${childCount}개 하위 영역 접기 ↑` : `collapse ${childCount} subareas ↑`
        : korean ? `${childCount}개 세부 영역 펼치기 ↓` : `expand ${childCount} subareas ↓`;

      return (
        <div
          className={`${styles.territoryBranch}${depth > 0 ? ` ${styles.childBranch}` : ""}${depth > 1 ? ` ${styles.grandchildBranch}` : ""}`}
          key={territory.slug}
        >
          <motion.div
            layout
            className={`${styles.territoryBand}${isSelected ? ` ${styles.territoryBandActive}` : ""}`}
            transition={{ duration: reduceMotion ? 0 : 0.24, ease: "easeOut" }}
          >
            <button
              className={styles.bandSelect}
              type="button"
              onClick={() => selectTerritory(territory)}
              aria-pressed={isSelected}
              aria-label={korean
                ? `${localizeResearchLabel(territory.display_name, locale)}, 논문 ${territory.paper_count.toLocaleString()}편, 전문 ${percent(territory.full_text_paper_count, territory.paper_count)}%${childCount ? `, 하위 영역 ${childCount}개` : ""}`
                : `${territory.display_name}, ${territory.paper_count.toLocaleString()} papers, ${percent(territory.full_text_paper_count, territory.paper_count)}% full text${childCount ? `, ${childCount} subareas` : ""}`}
            >
              <div className={styles.bandRank}>{String(index + 1).padStart(2, "0")}</div>
              <div className={styles.bandLabel}>
                <strong>{localizeResearchLabel(territory.display_name, locale)}</strong>
                <span>{territory.paper_count.toLocaleString()} {korean ? "편" : "papers"}</span>
              </div>
              <div className={styles.bandTrackWrap}>
                <div className={styles.bandTrack} style={{ width: `${widthScale(territory.paper_count)}%` }}>
                  <span className={styles.bandFullText} style={{ width: `${percent(layers.deep, territory.paper_count)}%` }} />
                  <span className={styles.bandAbstract} style={{ width: `${percent(layers.abstractOnly, territory.paper_count)}%` }} />
                  <span className={styles.bandMetadata} style={{ width: `${percent(layers.metadataOnly, territory.paper_count)}%` }} />
                </div>
              </div>
              <div className={styles.bandMetrics}>
                <span><b>{percent(territory.full_text_paper_count, territory.paper_count)}%</b>{korean ? "전문" : "full"}</span>
                <span><b>{recent.toLocaleString()}</b>{latestYear ? `${latestYear - 1}–${latestYear}` : korean ? "최근" : "recent"}</span>
              </div>
            </button>
            {childCount ? (
              <button
                className={`${styles.drillAction}${isSelected ? ` ${styles.drillActionSelected}` : ""}${expanded ? ` ${styles.drillActionExpanded}` : ""}`}
                type="button"
                onClick={() => toggleExpanded(territory)}
                aria-expanded={expanded}
              >
                <span>{depth === 0 ? (korean ? "세부 구조" : "Substructure") : (korean ? "더 세분화" : "Deeper level")}</span>
                <strong>{drillLabel}</strong>
              </button>
            ) : null}
          </motion.div>

          {expanded && childCount ? (
            <motion.div
              className={styles.childTerritories}
              initial={reduceMotion ? false : { opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
            >
              <div className={styles.childContext}>
                <span>{String(depth + 2).padStart(2, "0")}</span>
                <div>
                  <strong>{localizeResearchLabel(territory.display_name, locale)}</strong>
                  <small>{korean ? "하위 영역 · 서로 중복될 수 있는 키워드 기반 분류" : "subareas · overlapping keyword-based taxonomy"}</small>
                </div>
              </div>
              {renderTerritoryGroup(children, depth + 1)}
            </motion.div>
          ) : null}
        </div>
      );
    });
  }

  return (
    <section className={styles.observatory} aria-labelledby="corpus-observatory-title">
      <header className={styles.observatoryHeader}>
        <div className={styles.headerIdentity}>
          <p className={styles.kicker}>{korean ? "코퍼스 관측소 · 연구 영역 탐색" : "Corpus observatory · research territory"}</p>
          <h2 id="corpus-observatory-title">{korean ? "어디에 논문이 있고, 어디까지 깊게 읽을 수 있는가." : "See where the literature is—and how deeply it can be read."}</h2>
          <p>
            {korean
              ? "연구 축은 서로 중복될 수 있습니다. 길이는 로컬 코퍼스의 연결 논문 수, 내부 층은 현재 확보된 근거 깊이를 나타냅니다."
              : "Research axes can overlap. Band length shows connected papers in the local corpus; internal layers show current evidence depth."}
          </p>
        </div>
        <div className={styles.headerMetrics}>
          <div><span>{korean ? "전체 레코드" : "Records"}</span><strong>{totalPapers.toLocaleString()}</strong></div>
          <div><span>{korean ? "초록 분석 가능" : "Abstract-ready"}</span><strong>{percent(coverage?.abstract_ready ?? 0, coverage?.total_records ?? totalPapers)}%</strong></div>
          <div><span>{korean ? "전문 근거" : "Full text"}</span><strong>{percent(coverage?.full_text_ready ?? 0, coverage?.total_records ?? totalPapers)}%</strong></div>
          <div><span>{korean ? "100K 진행" : "100K progress"}</span><strong>{(coverage?.expansion_progress_pct ?? 0).toFixed(1)}%</strong></div>
        </div>
      </header>

      <div className={styles.observatoryBody}>
        <section className={styles.territoryPanel} aria-label={korean ? "연구 영역 비교" : "Research territory comparison"}>
          <div className={styles.panelToolbar}>
            <div>
              <span className={styles.panelIndex}>01</span>
              <div>
                <strong>{korean ? "연구 축 비교" : "Compare research axes"}</strong>
                <small>{korean ? "행을 선택하면 오른쪽에서 먼저 확인하고, 별도 펼치기 버튼으로 하위 구조를 엽니다" : "select a row to inspect it first, then use the separate expand control to reveal its hierarchy"}</small>
              </div>
            </div>
            <div className={styles.toolbarActions}>
              {expandedSlugs.length ? (
                <button className={styles.collapseHierarchyButton} type="button" onClick={collapseAll}>
                  ← {korean ? "전체 연구 축만 보기" : "Show top-level axes only"}
                </button>
              ) : null}
              <div className={styles.sortTabs} role="group" aria-label={korean ? "연구 영역 정렬" : "Sort research territories"}>
                {([
                  ["volume", korean ? "논문량" : "Volume"],
                  ["evidence", korean ? "전문 근거" : "Evidence"],
                  ["recent", korean ? "최근 수집" : "Recent"],
                ] as const).map(([mode, label]) => (
                  <button
                    className={sortMode === mode ? styles.sortTabActive : undefined}
                    key={mode}
                    type="button"
                    onClick={() => setSortMode(mode)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className={styles.hierarchyTrail} aria-label={korean ? "연구 영역 계층" : "Research territory hierarchy"}>
            <span>{korean ? "전체 코퍼스" : "Corpus"}</span>
            <i>›</i>
            <strong>{korean ? "연구 축" : "Research axes"}</strong>
            {expandedSlugs.length ? <><i>›</i><span>{korean ? `${expandedSlugs.length}개 계층 펼침` : `${expandedSlugs.length} branches expanded`}</span></> : null}
          </div>

          <div className={styles.bandLegend} aria-label={korean ? "근거 깊이 범례" : "Evidence depth legend"}>
            <span><i className={styles.legendFullText} />{korean ? "전문 확보" : "full text"}</span>
            <span><i className={styles.legendAbstract} />{korean ? "초록만" : "abstract only"}</span>
            <span><i className={styles.legendMetadata} />{korean ? "서지정보만" : "metadata only"}</span>
          </div>

          <div className={styles.territoryBands}>
            {renderTerritoryGroup(sortedAxes)}
          </div>
        </section>

        <aside className={styles.inspectorPanel} aria-live="polite">
          <div className={styles.inspectorHeader}>
            <div>
              <span className={styles.panelIndex}>02</span>
              <small>{selectedTerritory?.parent_slug ? (korean ? "세부 연구영역" : "Subarea") : (korean ? "선택 연구축" : "Selected axis")}</small>
            </div>
            {selectedTerritory?.parent_slug && selectedParent ? (
              <button className={styles.parentButton} type="button" onClick={() => setActiveSlug(selectedParent.slug)}>
                ← {localizeResearchLabel(selectedParent.display_name, locale)}
              </button>
            ) : null}
          </div>

          <div className={styles.inspectorTitle}>
            <h3>{selectedTerritory ? localizeResearchLabel(selectedTerritory.display_name, locale) : (korean ? "전체 코퍼스" : "Corpus")}</h3>
            <div><strong>{selectedCount.toLocaleString()}</strong><span>{korean ? "연결 논문" : "connected papers"}</span></div>
          </div>

          <div className={styles.coverageTriptych}>
            <article><span>{korean ? "초록" : "Abstract"}</span><strong>{selectedAbstractPct}%</strong><i><b style={{ width: `${selectedAbstractPct}%` }} /></i></article>
            <article><span>{korean ? "전문" : "Full text"}</span><strong>{selectedFullTextPct}%</strong><i><b style={{ width: `${selectedFullTextPct}%` }} /></i></article>
            <article><span>OA</span><strong>{selectedOaPct}%</strong><i><b style={{ width: `${selectedOaPct}%` }} /></i></article>
          </div>

          <section className={styles.trajectoryBlock}>
            <div className={styles.blockHeading}>
              <div><span>{korean ? "연도별 로컬 수집" : "Local coverage by year"}</span><small>{korean ? "학계 성장률로 해석하지 않음" : "not a field-growth measure"}</small></div>
              <strong>{latestYear ? `${latestYear - 1}–${latestYear}` : "—"}</strong>
            </div>
            <Sparkline
              years={selectedYears}
              label={korean ? "선택 영역의 연도별 로컬 코퍼스 수집량" : "Local corpus coverage by year for selected territory"}
            />
          </section>

          <section className={styles.methodBlock}>
            <div className={styles.blockHeading}>
              <div><span>{korean ? "주요 방법론 신호" : "Method signals"}</span><small>{korean ? "휴리스틱 분류" : "heuristic taxonomy"}</small></div>
            </div>
            <div className={styles.methodChips}>
              {selectedTerritory?.top_methodologies.length
                ? selectedTerritory.top_methodologies.map((method) => (
                  <Link href={`/library?view=browse&axis=${encodeURIComponent(selectedTerritory.slug)}&methodology=${encodeURIComponent(method.slug)}`} key={method.slug}>
                    <span>{localizeResearchLabel(method.display_name, locale)}</span><b>{method.paper_count.toLocaleString()}</b>
                  </Link>
                ))
                : <span className={styles.emptySignal}>{korean ? "방법론 신호가 아직 없습니다." : "No methodology signal yet."}</span>}
            </div>
          </section>

          <div className={styles.inspectorActions}>
            <Link className={styles.primaryAction} href={selectedHref}>{korean ? "이 영역 논문 보기 →" : "Explore papers →"}</Link>
            <Link className={styles.secondaryAction} href="/questions">{korean ? "연구 질문에 연결" : "Connect to a research question"}</Link>
          </div>
        </aside>
      </div>

      <footer className={styles.observatoryFooter}>
        <section className={styles.pipelinePanel}>
          <div className={styles.footerHeading}>
            <div><span className={styles.panelIndex}>03</span><div><strong>{korean ? "수집 파이프라인" : "Acquisition pipeline"}</strong><small>{korean ? "OpenAlex bootstrap 누적 상태" : "OpenAlex bootstrap cumulative state"}</small></div></div>
            <strong className={styles.targetProgress}>{(coverage?.expansion_progress_pct ?? 0).toFixed(1)}%</strong>
          </div>
          <div className={styles.pipelineStages}>
            {[
              [korean ? "가져옴" : "Fetched", coverage?.expansion_fetched_total ?? 0],
              [korean ? "채택" : "Accepted", coverage?.expansion_accepted_total ?? 0],
              [korean ? "신규" : "Inserted", coverage?.expansion_inserted_total ?? 0],
              [korean ? "갱신" : "Updated", coverage?.expansion_updated_total ?? 0],
            ].map(([label, value]) => (
              <div key={String(label)}><span>{label}</span><strong>{Number(value).toLocaleString()}</strong></div>
            ))}
          </div>
          <div className={styles.targetTrack} aria-label={korean ? "10만 편 목표 진행률" : "Progress toward 100,000 records"}>
            <span style={{ width: `${Math.min(coverage?.expansion_progress_pct ?? 0, 100)}%` }} />
          </div>
          <p>{korean ? "수집량은 탐색 진행 상태이며 연구 중요도나 근거 강도를 뜻하지 않습니다." : "Acquisition volume describes pipeline progress, not scholarly importance or evidence strength."}</p>
        </section>

        <section className={styles.corpusTrajectory}>
          <div className={`${styles.footerHeading} ${styles.trajectoryHeading}`}>
            <div>
              <span className={styles.panelIndex}>04</span>
              <div>
                <strong className={styles.trajectoryTitle}>
                  {korean ? (
                    <><span>전체</span><span>코퍼스</span><span>연도 궤적</span></>
                  ) : (
                    <><span>Corpus</span><span>coverage</span><span>trajectory</span></>
                  )}
                </strong>
                <small>{korean ? "2026년 증가는 수집 집중의 영향이 큼" : "2026 is strongly affected by current ingestion"}</small>
              </div>
            </div>
            <div className={styles.trajectoryDelta}>
              <span>{latestCorpusYear?.year ?? "—"}</span>
              <strong>{latestCorpusYear?.paper_count.toLocaleString() ?? "—"}</strong>
              <small>{latestCoverageDelta === null ? "—" : `${latestCoverageDelta >= 0 ? "+" : ""}${latestCoverageDelta}% vs ${previousCorpusYear?.year}`}</small>
            </div>
          </div>
          <Sparkline years={years} label={korean ? "전체 코퍼스의 연도별 수집량" : "Corpus coverage by publication year"} compact />
        </section>
      </footer>
    </section>
  );
}
