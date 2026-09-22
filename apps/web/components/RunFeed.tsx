"use client";

import { api } from "@/lib/api";
import type { Envelope, ResearchRun } from "@/lib/types";
import { usePolling } from "@/hooks/usePolling";
import { RunCard } from "@/components/RunCard";
import { StatusBanner } from "@/components/StatusBanner";

export function RunFeed({ compact = false }: { compact?: boolean }) {
  const { data, error, updatedAt } = usePolling((signal) => api<Envelope<ResearchRun>>("/api/runs?limit=20", signal), 8000);
  const items = compact ? data?.items.slice(0, 2) : data?.items;
  return (
    <>
      <StatusBanner error={error} updatedAt={updatedAt} />
      {!data && !error && <div className="panel empty">Connecting to the local research record…</div>}
      {data && data.items.length === 0 && <div className="panel empty"><h2>No runs yet</h2><p>Start <code>python -m cancerjev run --fixture demo</code> in a separate terminal.</p></div>}
      <div className="run-grid">{items?.map((run) => <RunCard key={run.run_id} run={run} />)}</div>
    </>
  );
}

