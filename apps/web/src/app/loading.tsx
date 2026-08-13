export default function Loading() {
  return (
    <div className="loadingShell" aria-live="polite" aria-busy="true">
      <div className="loadingHeaderSkeleton">
        <span className="loadingLine loadingLineShort" />
        <span className="loadingLine loadingLineTitle" />
        <span className="loadingLine loadingLineBody" />
      </div>
      <div className="loadingGrid">
        <span className="loadingCard" />
        <span className="loadingCard" />
        <span className="loadingCard" />
      </div>
      <span className="srOnly">Loading research workspace…</span>
    </div>
  );
}
