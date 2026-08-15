"use client";

import Link from "next/link";
import { scaleLinear } from "d3-scale";
import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";

import type { LandscapeAxis, LandscapeYear } from "@/lib/api";

import { localizeResearchLabel } from "./LocalizedText";
import { useLocalePreference } from "./LocalePreference";
import styles from "./CitationAtlas.module.css";

type CitationAtlasProps = {
  axes: LandscapeAxis[];
  subaxes: LandscapeAxis[];
  years: LandscapeYear[];
  totalPapers: number;
};

const DECOMPOSED_AXIS_SLUG = "ai-adoption-business-value";

export function CitationAtlas({ axes, subaxes, years, totalPapers }: CitationAtlasProps) {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  const reduceMotion = useReducedMotion();
  const [activeSlug, setActiveSlug] = useState<string | null>(() => {
    let largestAxis = axes[0];
    for (const axis of axes) {
      if (!largestAxis || axis.paper_count > largestAxis.paper_count) largestAxis = axis;
    }
    return largestAxis?.slug ?? null;
  });
  const maxAxisCount = Math.max(...axes.map((axis) => axis.paper_count), 1);
  const maxYearCount = Math.max(...years.map((year) => year.paper_count), 1);
  const radiusScale = useMemo(() => scaleLinear().domain([0, maxAxisCount]).range([38, 60]), [maxAxisCount]);
  const yearHeightScale = useMemo(() => scaleLinear().domain([0, maxYearCount]).range([14, 92]), [maxYearCount]);
  const activeAxis = axes.find((axis) => axis.slug === activeSlug) ?? axes[0];
  const activeSubaxes = activeAxis?.slug === DECOMPOSED_AXIS_SLUG ? subaxes : [];
  const maxSubaxisCount = Math.max(...activeSubaxes.map((subaxis) => subaxis.paper_count), 1);

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
          <div className={styles.axisNodes}>
            <div className={styles.fieldGrid} aria-hidden="true" />
            {axes.map((axis, index) => {
              const radius = radiusScale(axis.paper_count);
              const isActive = axis.slug === activeAxis?.slug;
              return (
                <motion.div
                  className={`${styles.axisNode}${isActive ? ` ${styles.axisNodeActive}` : ""}`}
                  key={axis.slug}
                  style={{ width: radius * 2, height: radius * 2 }}
                  initial={false}
                  animate={{ scale: isActive ? 1.06 : 1 }}
                  transition={{ duration: reduceMotion ? 0 : 0.26 }}
                >
                  <Link
                    href={`/library?view=browse&axis=${encodeURIComponent(axis.slug)}`}
                    aria-label={korean
                      ? `${localizeResearchLabel(axis.display_name, locale)}, 논문 ${axis.paper_count}편. 이 연구 영역 보기.`
                      : `${axis.display_name}, ${axis.paper_count} papers. Browse this research area.`}
                    onFocus={() => setActiveSlug(axis.slug)}
                    onMouseEnter={() => setActiveSlug(axis.slug)}
                  >
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{axis.paper_count}</strong>
                    {axis.slug === DECOMPOSED_AXIS_SLUG && subaxes.length > 0
                      ? <small>{korean ? `${subaxes.length}개 세부 영역` : `${subaxes.length} subareas`}</small>
                      : null}
                  </Link>
                </motion.div>
              );
            })}
          </div>
          <div className={styles.axisNarrative} aria-live="polite">
            <span>{korean ? "현재 연구 영역" : "Active territory"}</span>
            <strong>{activeAxis ? localizeResearchLabel(activeAxis.display_name, locale) : korean ? "연구 축" : "Research axis"}</strong>
            <p>{activeAxis
              ? korean
                ? `현재 로컬 코퍼스에 논문 ${activeAxis.paper_count.toLocaleString()}편이 있습니다. 밀도는 수집 범위이며 중요도의 증거가 아닙니다.`
                : `${activeAxis.paper_count.toLocaleString()} papers in the current local corpus. Density is coverage, not evidence of importance.`
              : korean ? "연구 축 커버리지 정보가 없습니다." : "No axis coverage is available."}</p>
            {activeSubaxes.length > 0 ? (
              <div className={styles.subaxisSection}>
                <div className={styles.subaxisHeading}>
                  <span>{korean ? "상위 영역 세분화" : "Parent territory breakdown"}</span>
                  <small>
                    {korean
                      ? "키워드 기반의 중복 가능한 세부 분류이며, 미분류 논문도 있어 합계는 상위 영역과 다를 수 있습니다."
                      : "Keyword-based subareas may overlap and exclude unclassified papers, so their total can differ from the parent territory."}
                  </small>
                </div>
                <div className={styles.subaxisGrid}>
                  {activeSubaxes.map((subaxis, index) => (
                    <Link
                      className={styles.subaxisItem}
                      href={`/library?view=browse&axis=${encodeURIComponent(subaxis.slug)}`}
                      key={subaxis.slug}
                    >
                      <span className={styles.subaxisIndex}>{String(index + 1).padStart(2, "0")}</span>
                      <strong>{localizeResearchLabel(subaxis.display_name, locale)}</strong>
                      <b>{subaxis.paper_count.toLocaleString()}</b>
                      <i className={styles.subaxisBar} aria-hidden="true">
                        <span style={{ width: `${(subaxis.paper_count / maxSubaxisCount) * 100}%` }} />
                      </i>
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>

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
      </div>
    </section>
  );
}
