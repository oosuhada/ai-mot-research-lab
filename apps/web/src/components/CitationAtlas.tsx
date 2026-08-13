"use client";

import Link from "next/link";
import { scaleLinear } from "d3-scale";
import { motion, useReducedMotion } from "motion/react";
import { useMemo, useState } from "react";

import type { LandscapeAxis, LandscapeYear } from "@/lib/api";

import styles from "./CitationAtlas.module.css";

type CitationAtlasProps = {
  axes: LandscapeAxis[];
  years: LandscapeYear[];
  totalPapers: number;
};

export function CitationAtlas({ axes, years, totalPapers }: CitationAtlasProps) {
  const reduceMotion = useReducedMotion();
  const [activeSlug, setActiveSlug] = useState<string | null>(axes[0]?.slug ?? null);
  const maxAxisCount = Math.max(...axes.map((axis) => axis.paper_count), 1);
  const maxYearCount = Math.max(...years.map((year) => year.paper_count), 1);
  const radiusScale = useMemo(() => scaleLinear().domain([0, maxAxisCount]).range([26, 58]), [maxAxisCount]);
  const yearHeightScale = useMemo(() => scaleLinear().domain([0, maxYearCount]).range([14, 92]), [maxYearCount]);
  const activeAxis = axes.find((axis) => axis.slug === activeSlug) ?? axes[0];

  return (
    <section className={styles.atlas} aria-labelledby="citation-atlas-title">
      <div className={styles.atlasHeader}>
        <div>
          <p className={styles.kicker}>Citation Atlas · live corpus</p>
          <h2 id="citation-atlas-title">Read the landscape as connected research territory.</h2>
        </div>
        <div className={styles.corpusStamp}>
          <strong>{totalPapers.toLocaleString()}</strong>
          <span>live research records</span>
        </div>
      </div>

      <div className={styles.atlasBody}>
        <div className={styles.axisField} aria-label="Research axis atlas">
          <div className={styles.fieldGrid} aria-hidden="true" />
          {axes.map((axis, index) => {
            const radius = radiusScale(axis.paper_count);
            const isActive = axis.slug === activeAxis?.slug;
            return (
              <motion.div
                className={`${styles.axisNode}${isActive ? ` ${styles.axisNodeActive}` : ""}`}
                key={axis.slug}
                style={{
                  left: `${14 + (index % 3) * 34}%`,
                  top: `${18 + Math.floor(index / 3) * 48 + (index % 2) * 7}%`,
                  width: radius * 2,
                  height: radius * 2,
                }}
                initial={false}
                animate={{ scale: isActive ? 1.06 : 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.26 }}
              >
                <Link
                  href={`/library?view=browse&axis=${encodeURIComponent(axis.slug)}`}
                  aria-label={`${axis.display_name}, ${axis.paper_count} papers. Browse this research area.`}
                  onFocus={() => setActiveSlug(axis.slug)}
                  onMouseEnter={() => setActiveSlug(axis.slug)}
                >
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{axis.paper_count}</strong>
                </Link>
              </motion.div>
            );
          })}
          <div className={styles.axisNarrative} aria-live="polite">
            <span>Active territory</span>
            <strong>{activeAxis?.display_name ?? "Research axis"}</strong>
            <p>{activeAxis ? `${activeAxis.paper_count.toLocaleString()} papers in the current local corpus. Density is coverage, not evidence of importance.` : "No axis coverage is available."}</p>
          </div>
        </div>

        <aside className={styles.timeLedger} aria-label="Publication-year coverage">
          <div className={styles.ledgerHeader}>
            <span>Publication ledger</span>
            <small>corpus coverage · not field trend</small>
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
