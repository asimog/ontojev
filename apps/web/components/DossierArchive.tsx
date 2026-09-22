"use client";

import Link from "next/link";
import { useState } from "react";
import { StatusBanner } from "@/components/StatusBanner";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { formatTime } from "@/lib/format";
import { chainCursor, mergeUniqueById } from "@/lib/pagination";
import type { ChildRecord, Envelope } from "@/lib/types";

export function DossierArchive() {
  const { data, error, updatedAt } = usePolling((signal) => api<Envelope<ChildRecord>>("/api/dossiers?limit=20", signal), 5000);
  const [extra, setExtra] = useState<ChildRecord[]>([]);
  const [pageCursor, setPageCursor] = useState<string | null | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);

  const items = mergeUniqueById(data?.items ?? [], extra, (item) => String(item.dossier_id));
  const nextCursor = chainCursor(pageCursor, data?.next_cursor);

  const loadMore = async () => {
    if (!nextCursor) return;
    setLoading(true);
    setMoreError(null);
    try {
      const page = await api<Envelope<ChildRecord>>(`/api/dossiers?limit=20&cursor=${encodeURIComponent(nextCursor)}`);
      setExtra((current) => mergeUniqueById(current, page.items, (item) => String(item.dossier_id)));
      setPageCursor(page.next_cursor);
    } catch {
      setMoreError("Could not load more dossiers.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <StatusBanner error={error} updatedAt={updatedAt} />
      <div className="archive">
        {items.map((item) => {
          const summary = item.summary as Record<string, unknown>;
          const entity = summary.entity as Record<string, unknown>;
          return (
            <article className="panel" key={String(item.dossier_id)}>
              <span className="badge fake">SYNTHETIC DOSSIER</span>
              <h2>{String(entity?.gene_symbol ?? "Fixture candidate")}</h2>
              <p className="muted">{String(summary.puzzle ?? "Puzzle section available in the dossier.")}</p>
              <p className="muted mono">created {formatTime(String(item.created_at))} · run {String(item.run_id).slice(0, 8)} · candidate {String(item.candidate_id).slice(0, 8)} · {String(summary.mode ?? "FAKE")}</p>
              <Link className="button" href={`/dossiers/${String(item.dossier_id)}`}>Read dossier</Link>
            </article>
          );
        })}
      </div>
      {data?.items.length === 0 && extra.length === 0 && <div className="panel empty">No dossiers yet.</div>}
      {moreError && <div className="api-warning">{moreError}</div>}
      {nextCursor && <div className="row center"><button onClick={loadMore} disabled={loading}>{loading ? "Loading…" : "Load more dossiers"}</button></div>}
    </>
  );
}
