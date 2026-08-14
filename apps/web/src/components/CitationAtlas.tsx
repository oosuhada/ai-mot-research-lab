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
  years: LandscapeYear[];
  totalPapers: number;
};

export function CitationAtlas({ axes, years, totalPapers }: CitationAtlasProps) {
  const { locale } = useLocalePreference();
  const korean = locale === "ko";
  const reduceMotion = useReducedMotion();
  const [activeSlug, setActiveSlug] = useState<string | null>(axes[0]?.slug ?? null);
  const maxAxisCount = Math.max(...axes.map((axis) => axis.paper_count), 1);
  const maxYearCount = Math.max(...years.map((year) => year.paper_count), 1);
  const radiusScale = useMemo(() => scaleLinear().domain([0, maxAxisCount]).range([38, 60]), [maxAxisCount]);
  const yearHeightScale = useMemo(() => scaleLinear().domain([0, maxYearCount]).range([14, 92]), [maxYearCount]);
  const activeAxis = axes.find((axis) => axis.slug === activeSlug) ?? axes[0];

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
