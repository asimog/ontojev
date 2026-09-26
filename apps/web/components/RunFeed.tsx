"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Envelope, ResearchRun } from "@/lib/types";
import { usePolling } from "@/hooks/usePolling";
import { RunCard } from "@/components/RunCard";
import { StatusBanner } from "@/components/StatusBanner";
import { chainCursor, mergeUniqueById } from "@/lib/pagination";

export function RunFeed({ compact = false }: { compact?: boolean }) {
  const { data, error, updatedAt } = usePolling((signal) => api<Envelope<ResearchRun>>("/api/runs?limit=20", signal), 8000);
  const [extra, setExtra] = useState<ResearchRun[]>([]);
  const [pageCursor, setPageCursor] = useState<string | null | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);

  const firstPage = data?.items ?? [];
  const items = compact ? firstPage.slice(0, 2) : mergeUniqueById(firstPage, extra, (run) => run.run_id);
  const nextCursor = chainCursor(pageCursor, data?.next_cursor);

  const loadMore = async () => {
    if (!nextCursor) return;
    setLoading(true);
    setMoreError(null);
    try {
      const page = await api<Envelope<ResearchRun>>(`/api/runs?limit=20&cursor=${encodeURIComponent(nextCursor)}`);
      setExtra((current) => mergeUniqueById(current, page.items, (run) => run.run_id));
      setPageCursor(page.next_cursor);
    } catch {
      setMoreError("Could not load more runs.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <StatusBanner error={error} updatedAt={updatedAt} />
      {!data && !error && <div className="panel empty">Connecting to the local research record…</div>}
      {data && data.items.length === 0 && <div className="panel empty"><h2>No runs yet</h2><p>Start <code>python -m cancerjev program</code> for one durable autonomous cycle, or <code>python -m cancerjev run --fixture demo</code> for a synthetic record.</p></div>}
      <div className="run-grid">{items.map((run) => <RunCard key={run.run_id} run={run} />)}</div>
      {moreError && <div className="api-warning">{moreError}</div>}
      {!compact && nextCursor && <div className="row center"><button onClick={loadMore} disabled={loading}>{loading ? "Loading…" : "Load more runs"}</button></div>}
    </>
  );
}
