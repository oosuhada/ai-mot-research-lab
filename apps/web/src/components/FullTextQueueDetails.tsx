"use client";

import { useEffect, useRef, useState } from "react";

import { useLocalePreference } from "./LocalePreference";

type QueueDetails = {
  claimable: number;
  deferred: number;
  processing: number;
  completed24h: number;
  boosterEligible: number;
  boosterCooldown: number;
  boosterWaiting: number;
};

export function FullTextQueueDetails({ details }: { details: QueueDetails }) {
  const { locale } = useLocalePreference();
  const [open, setOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const korean = locale === "ko";

  useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  const rows = korean
    ? [
        ["즉시 처리", details.claimable],
        ["재시도 대기", details.deferred],
        ["처리 중", details.processing],
        ["24시간 완료", details.completed24h],
        ["fallback 가능", details.boosterEligible],
        ["fallback cooldown", details.boosterCooldown],
        ["fallback 시도 대기", details.boosterWaiting],
      ]
    : [
        ["Ready", details.claimable],
        ["retry delay", details.deferred],
        ["processing", details.processing],
        ["completed 24h", details.completed24h],
        ["fallback ready", details.boosterEligible],
        ["fallback cooldown", details.boosterCooldown],
        ["fallback waiting", details.boosterWaiting],
      ];

  return (
    <>
      <button
        aria-expanded={open}
        aria-haspopup="dialog"
        className="queueDetailsButton"
        onClick={() => setOpen(true)}
        type="button"
      >
        {korean ? "상세" : "Details"}
      </button>
      {open ? (
        <div className="queueDetailsBackdrop" onClick={() => setOpen(false)}>
          <section
            aria-labelledby="queue-details-title"
            aria-modal="true"
            className="queueDetailsModal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <header>
              <div>
                <span>{korean ? "대기열" : "Queue"}</span>
                <h2 id="queue-details-title">{korean ? "전문 보강 상세 분류" : "Full-text queue details"}</h2>
              </div>
              <button
                aria-label={korean ? "상세 창 닫기" : "Close queue details"}
                className="queueDetailsClose"
                onClick={() => setOpen(false)}
                ref={closeButtonRef}
                type="button"
              >
                ×
              </button>
            </header>
            <dl>
              {rows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{Number(value).toLocaleString()}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      ) : null}
    </>
  );
}
