"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <section className="errorPanel" role="alert">
      <p className="eyebrow">Research workspace error</p>
      <h2 className="sectionTitle">This view could not be loaded safely.</h2>
      <p>Nothing was silently inferred or saved. Retry the request, or return to the Library and choose a broader evidence scope.</p>
      <div className="headerActionRow">
        <button className="button" type="button" onClick={() => retry()}>Try again</button>
        <Link className="secondaryButton" href="/library">Open Library</Link>
      </div>
      {error.digest ? <small>Error reference: {error.digest}</small> : null}
    </section>
  );
}
