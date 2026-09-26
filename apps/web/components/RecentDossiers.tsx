"use client";

import Link from "next/link";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import type { ChildRecord, Envelope } from "@/lib/types";

export function RecentDossiers() {
  const { data } = usePolling((signal) => api<Envelope<ChildRecord>>("/api/dossiers?limit=3", signal), 15000);
  if (!data || data.items.length === 0) return null;
  return (
    <section>
      <div className="section-heading"><div><span className="eyebrow">RECENT DOSSIERS</span><h2>Research output</h2></div><Link href="/dossiers">Archive →</Link></div>
      <div className="archive">
        {data.items.map((item) => {
          const summary = item.summary as Record<string, unknown>;
          const entity = summary.entity as Record<string, unknown>;
          const liveDossier = String(summary.mode ?? "FAKE") === "LIVE";
          return (
            <article className="panel mini-card" key={String(item.dossier_id)}>
              <span className={`badge ${liveDossier ? "live" : "fake"}`}>{liveDossier ? "LIVE DOSSIER" : "SYNTHETIC DOSSIER"}</span>
              <h3>{String(entity?.gene_symbol ?? (liveDossier ? "Candidate" : "Fixture candidate"))}</h3>
              <Link className="button secondary" href={`/dossiers/${String(item.dossier_id)}`}>Read dossier</Link>
            </article>
          );
        })}
      </div>
    </section>
  );
}
