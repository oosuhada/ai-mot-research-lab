"use client";

import Link from "next/link";
import { scaleLinear } from "d3-scale";
import { AnimatePresence, motion, useMotionValue, useReducedMotion } from "motion/react";
import { useMemo, useRef, useState, type PointerEvent, type WheelEvent } from "react";

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

type AtlasLevel = "root" | "axes" | "subaxes";

const DECOMPOSED_AXIS_SLUG = "ai-adoption-business-value";
const MIN_ZOOM = 0.72;
const MAX_ZOOM = 1.45;

export function CitationAtlas({ axes, subaxes, years, totalPapers, coverage }: CitationAtlasProps) {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  const reduceMotion = useReducedMotion();
  const panX = useMotionValue(0);
  const panY = useMotionValue(0);
  const panStart = useRef<{ pointerX: number; pointerY: number; x: number; y: number } | null>(null);
  const [level, setLevel] = useState<AtlasLevel>("root");
  const [zoom, setZoom] = useState(1);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);

  const maxAxisCount = Math.max(...axes.map((axis) => axis.paper_count), 1);
  const maxSubaxisCount = Math.max(...subaxes.map((axis) => axis.paper_count), 1);
  const maxYearCount = Math.max(...years.map((year) => year.paper_count), 1);
  const axisRadiusScale = useMemo(() => scaleLinear().domain([0, maxAxisCount]).range([46, 70]), [maxAxisCount]);
  const subaxisRadiusScale = useMemo(() => scaleLinear().domain([0, maxSubaxisCount]).range([42, 66]), [maxSubaxisCount]);
  const yearHeightScale = useMemo(() => scaleLinear().domain([0, maxYearCount]).range([10, 66]), [maxYearCount]);

  const activeAxis = axes.find((axis) => axis.slug === activeSlug) ?? null;
  const activeSubaxis = subaxes.find((axis) => axis.slug === activeSlug) ?? null;
  const selectedTerritory = activeSubaxis ?? activeAxis;
  const selectedHref = selectedTerritory
    ? `/library?view=browse&axis=${encodeURIComponent(selectedTerritory.slug)}`
    : "/library?view=browse";

  const narrativeTitle = selectedTerritory
    ? localizeResearchLabel(selectedTerritory.display_name, locale)
    : level === "root"
      ? korean ? "AI × MOT 전체 코퍼스" : "AI × MOT corpus"
      : korean ? "연구 영역 지도" : "Research territory map";
  const narrativeCount = selectedTerritory?.paper_count ?? totalPapers;

  function resetViewport() {
    panX.set(0);
    panY.set(0);
    setZoom(1);
  }

  function setZoomClamped(nextZoom: number) {
    setZoom(Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, nextZoom)));
  }

  function handleWheel(event: WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    const direction = event.deltaY > 0 ? -0.08 : 0.08;
    setZoomClamped(zoom + direction);
  }

  function handlePanStart(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest("button")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    panStart.current = {
      pointerX: event.clientX,
      pointerY: event.clientY,
      x: panX.get(),
      y: panY.get(),
    };
  }

  function handlePanMove(event: PointerEvent<HTMLDivElement>) {
    if (!panStart.current) return;
    panX.set(panStart.current.x + event.clientX - panStart.current.pointerX);
    panY.set(panStart.current.y + event.clientY - panStart.current.pointerY);
  }

  function handlePanEnd(event: PointerEvent<HTMLDivElement>) {
    if (!panStart.current) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    panStart.current = null;
  }

  function expandRoot() {
    setLevel("axes");
    setActiveSlug(null);
    resetViewport();
  }

  function selectAxis(axis: LandscapeAxis) {
    setActiveSlug(axis.slug);
    if (axis.slug === DECOMPOSED_AXIS_SLUG && subaxes.length > 0) {
      setLevel("subaxes");
      resetViewport();
    }
  }

  function selectSubaxis(axis: LandscapeAxis) {
    setActiveSlug(axis.slug);
  }

  function collapseOneLevel() {
    if (level === "subaxes") {
      setLevel("axes");
      setActiveSlug(DECOMPOSED_AXIS_SLUG);
    } else if (level === "axes") {
      setLevel("root");
      setActiveSlug(null);
    }
    resetViewport();
  }

  const hierarchyLabel = level === "root"
    ? korean ? "전체 코퍼스" : "Corpus root"
    : level === "axes"
      ? korean ? "연구 축" : "Research axes"
      : korean ? "상위 영역 세분화" : "Parent territory breakdown";

  return (
    <section className={styles.atlas} aria-labelledby="citation-atlas-title">
      <div className={styles.atlasHeader}>
        <div>
          <p className={styles.kicker}>{korean ? "인용 지도 · 실시간 코퍼스" : "Citation Atlas · live corpus"}</p>
          <h2 id="citation-atlas-title">{korean ? "연결된 연구 영역으로 문헌 지형을 읽어보세요." : "Read the landscape as connected research territory."}</h2>
        </div>
        <div className={styles.corpusStamp}>
          <strong>{totalPapers.toLocaleString()}</strong>
          <span>{korean ? "실시간 연구 레코드" : "live research records"}</span>
        </div>
      </div>

      <div className={styles.atlasBody}>
        <div className={styles.axisField} aria-label="Research axis atlas">
          <div className={styles.axisNarrative} aria-live="polite">
            <div className={styles.narrativeCopy}>
              <span>{korean ? "현재 연구 영역" : "Active territory"}</span>
              <strong>{narrativeTitle}</strong>
              <p>
                {level === "subaxes" && !activeSubaxis
                  ? korean
                    ? "키워드 기반의 중복 가능한 세부 분류이며, 미분류 논문도 있어 합계는 상위 영역과 다를 수 있습니다."
                    : "Keyword-based subareas may overlap and exclude unclassified papers, so their total can differ from the parent territory."
                  : korean
                    ? `현재 로컬 코퍼스 기준 ${narrativeCount.toLocaleString()}편이 연결됩니다. 밀도는 수집 범위이며 중요도의 증거가 아닙니다.`
                    : `${narrativeCount.toLocaleString()} papers connect to this view of the local corpus. Density is coverage, not evidence of importance.`}
              </p>
            </div>
            <div className={styles.narrativeActions}>
              <span>{hierarchyLabel}</span>
              <Link className={styles.browseButton} href={selectedHref}>
                {korean ? "선택 영역으로 이동 →" : "Open selected territory →"}
              </Link>
              <div className={styles.inlineMapControls} aria-label={korean ? "지도 조작" : "Map controls"}>
                <button type="button" onClick={() => setZoomClamped(zoom - 0.12)} aria-label={korean ? "지도 축소" : "Zoom out"}>−</button>
                <span>{Math.round(zoom * 100)}%</span>
                <button type="button" onClick={() => setZoomClamped(zoom + 0.12)} aria-label={korean ? "지도 확대" : "Zoom in"}>+</button>
                <button type="button" onClick={resetViewport}>{korean ? "중앙 정렬" : "Center"}</button>
                <button type="button" disabled={level === "root"} onClick={collapseOneLevel}>{korean ? "상위로" : "Parent"}</button>
              </div>
            </div>
          </div>

          <div className={styles.axisNodes} onWheel={handleWheel}>
            <div className={styles.fieldGrid} aria-hidden="true" />
            <motion.div
              className={styles.graphStage}
              style={{ x: panX, y: panY, scale: zoom }}
              onPointerDown={handlePanStart}
              onPointerMove={handlePanMove}
              onPointerUp={handlePanEnd}
              onPointerCancel={handlePanEnd}
            >
              <AnimatePresence mode="popLayout" initial={false}>
                {level === "root" ? (
                  <motion.button
                    className={`${styles.axisNode} ${styles.rootNode}`}
                    key="corpus-root"
                    type="button"
                    initial={reduceMotion ? false : { opacity: 0, scale: 0.7 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={reduceMotion ? undefined : { opacity: 0, scale: 1.25 }}
                    transition={{ duration: reduceMotion ? 0 : 0.24 }}
                    onClick={expandRoot}
                  >
                    <span>ROOT</span>
                    <strong>{totalPapers.toLocaleString()}</strong>
                    <small>{korean ? "클릭하여 연구 축 펼치기" : "click to split into research axes"}</small>
                  </motion.button>
                ) : null}

                {level === "axes" ? axes.map((axis, index) => {
                  const radius = axisRadiusScale(axis.paper_count);
                  const isActive = axis.slug === activeSlug;
                  return (
                    <motion.button
                      className={`${styles.axisNode}${isActive ? ` ${styles.axisNodeActive}` : ""}`}
                      key={axis.slug}
                      type="button"
                      style={{ width: radius * 2, height: radius * 2 }}
                      initial={reduceMotion ? false : { opacity: 0, scale: 0.62 }}
                      animate={{ opacity: 1, scale: isActive ? 1.07 : 1 }}
                      exit={reduceMotion ? undefined : { opacity: 0, scale: 0.65 }}
                      transition={{ duration: reduceMotion ? 0 : 0.24, delay: reduceMotion ? 0 : index * 0.025 }}
                      aria-label={korean
                        ? `${localizeResearchLabel(axis.display_name, locale)}, 논문 ${axis.paper_count}편`
                        : `${axis.display_name}, ${axis.paper_count} papers`}
                      onClick={() => selectAxis(axis)}
                    >
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <b>{localizeResearchLabel(axis.display_name, locale)}</b>
                      <strong>{axis.paper_count.toLocaleString()}</strong>
                      {axis.slug === DECOMPOSED_AXIS_SLUG && subaxes.length > 0
                        ? <small>{korean ? `${subaxes.length}개 세부 영역 · 클릭하여 분해` : `${subaxes.length} subareas · click to split`}</small>
                        : null}
                    </motion.button>
                  );
                }) : null}

                {level === "subaxes" ? subaxes.map((subaxis, index) => {
                  const radius = subaxisRadiusScale(subaxis.paper_count);
                  const isActive = subaxis.slug === activeSlug;
                  return (
                    <motion.button
                      className={`${styles.axisNode} ${styles.subaxisNode}${isActive ? ` ${styles.axisNodeActive}` : ""}`}
                      key={subaxis.slug}
                      type="button"
                      style={{ width: radius * 2, height: radius * 2 }}
                      initial={reduceMotion ? false : { opacity: 0, scale: 0.55 }}
                      animate={{ opacity: 1, scale: isActive ? 1.08 : 1 }}
                      exit={reduceMotion ? undefined : { opacity: 0, scale: 0.65 }}
                      transition={{ duration: reduceMotion ? 0 : 0.22, delay: reduceMotion ? 0 : index * 0.022 }}
                      onClick={() => selectSubaxis(subaxis)}
                    >
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <b>{localizeResearchLabel(subaxis.display_name, locale)}</b>
                      <strong>{subaxis.paper_count.toLocaleString()}</strong>
                    </motion.button>
                  );
                }) : null}
              </AnimatePresence>
            </motion.div>
          </div>
        </div>

        <div className={styles.sideRail}>
          <aside className={styles.timeLedger} aria-label="Publication-year coverage">
            <div className={styles.ledgerHeader}>
              <span>{korean ? "출판 연도 기록" : "Publication ledger"}</span>
              <small>{korean ? "코퍼스 수집 범위 · 학계 추세 아님" : "corpus coverage · not field trend"}</small>
            </div>
            <div className={styles.yearBars}>
              {years.map((year) => (
                <div className={styles.yearColumn} key={year.year}>
                  <span className={styles.yearValue}>{year.paper_count}</span>
                  <motion.span
                    className={styles.yearBar}
                    style={{ height: yearHeightScale(year.paper_count) }}
                    initial={false}
                    animate={{ scaleY: 1 }}
                    transition={{ duration: reduceMotion ? 0 : 0.3 }}
                  />
                  <span className={styles.yearLabel}>{year.year}</span>
                </div>
              ))}
            </div>
          </aside>

          <aside className={styles.mapGuide} aria-label="Corpus expansion progress">
            <div className={styles.ledgerHeader}>
              <span>{korean ? "코퍼스 확장 진행" : "Corpus expansion"}</span>
              <small>{(coverage?.expansion_progress_pct ?? 0).toFixed(1)}%</small>
            </div>
            <div className={styles.expansionProgress}>
              <strong>
                {(coverage?.total_records ?? totalPapers).toLocaleString()}
                <small> / {(coverage?.expansion_target_total ?? 100000).toLocaleString()}</small>
              </strong>
              <div className={styles.progressTrack} aria-hidden="true">
                <span style={{ width: `${Math.min(coverage?.expansion_progress_pct ?? 0, 100)}%` }} />
              </div>
              <p>{korean ? "100,000편 초기 코퍼스를 향해 OpenAlex 기반 수집을 누적합니다." : "Accumulating OpenAlex discovery toward the initial 100,000-paper corpus."}</p>
            </div>
            <dl className={styles.expansionStats}>
              <div><dt>{korean ? "가져옴" : "Fetched"}</dt><dd>{(coverage?.expansion_fetched_total ?? 0).toLocaleString()}</dd></div>
              <div><dt>{korean ? "채택" : "Accepted"}</dt><dd>{(coverage?.expansion_accepted_total ?? 0).toLocaleString()}</dd></div>
              <div><dt>{korean ? "신규" : "Inserted"}</dt><dd>{(coverage?.expansion_inserted_total ?? 0).toLocaleString()}</dd></div>
              <div><dt>{korean ? "갱신" : "Updated"}</dt><dd>{(coverage?.expansion_updated_total ?? 0).toLocaleString()}</dd></div>
            </dl>
            <p className={styles.expansionNote}>{korean ? "수집량은 탐색 진행 상태이며 연구 중요도나 근거 강도를 뜻하지 않습니다." : "Acquisition volume describes pipeline progress, not scholarly importance or evidence strength."}</p>
          </aside>
        </div>
      </div>
    </section>
  );
}
