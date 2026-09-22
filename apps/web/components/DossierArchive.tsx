"use client";

import Link from "next/link";
import { StatusBanner } from "@/components/StatusBanner";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import type { ChildRecord, Envelope } from "@/lib/types";

export function DossierArchive() {
  const { data, error, updatedAt } = usePolling((signal) => api<Envelope<ChildRecord>>("/api/dossiers", signal), 5000);
  return <><StatusBanner error={error} updatedAt={updatedAt} /><div className="archive">{data?.items.map((item) => { const summary = item.summary as Record<string, unknown>; const entity = summary.entity as Record<string, unknown>; return <article className="panel" key={String(item.dossier_id)}><span className="badge fake">SYNTHETIC DOSSIER</span><h2>{String(entity?.gene_symbol ?? "Fixture candidate")}</h2><p className="muted">{String(summary.warning)}</p><Link className="button" href={`/dossiers/${String(item.dossier_id)}`}>Read dossier</Link></article>; })}</div>{data?.items.length === 0 && <div className="panel empty">No dossiers yet.</div>}</>;
}

