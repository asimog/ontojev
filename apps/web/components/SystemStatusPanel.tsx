"use client";

import Link from "next/link";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { SystemStatus } from "@/lib/types";

export function workerLabel(worker: SystemStatus["worker"]): string {
  if (!worker) return "No worker heartbeat recorded yet.";
  if (worker.fresh === true) return `Worker active · heartbeat ${new Date(worker.heartbeat_at).toLocaleTimeString()}`;
  if (worker.fresh === false) return `Worker heartbeat stale since ${new Date(worker.heartbeat_at).toLocaleTimeString()}. Persisted run status is authoritative.`;
  return `Worker idle · last write ${new Date(worker.heartbeat_at).toLocaleTimeString()}`;
}

export function SystemStatusPanel() {
  const { data, error } = usePolling((signal) => api<SystemStatus>("/api/system", signal), 15000);
  return (
    <section className="panel system-strip" data-testid="system-status">
      <div className="row spread">
        <div>
          <div className="eyebrow">Runtime posture</div>
          <h2>{data ? `${data.mode} · schema v${data.versions.schema}` : "System status"}</h2>
        </div>
        <Link href="/system">Inspect system →</Link>
      </div>
      {error && !data && <p className="muted">System status unavailable.</p>}
      {data && <>
        <p className="muted">{workerLabel(data.worker)}</p>
        <div className="metrics secondary">
          {Object.entries(data.providers).map(([name, enabled]) => (
            <div key={name}><strong>{enabled ? "enabled" : "off"}</strong><span>{name.toUpperCase()}</span></div>
          ))}
          <div><strong>v{data.versions.api}</strong><span>Read API</span></div>
          <div><strong>{data.data.artifact_files}</strong><span>Immutable artifacts</span></div>
          <div><strong>{formatBytes(data.data.database_bytes)}</strong><span>Database</span></div>
          <div><strong>{data.cache.entries}</strong><span>GDC cache</span></div>
          <div><strong>{data.cache.jev_entries ?? 0}</strong><span>Jev cache</span></div>
        </div>
        <p className="fine">
          LUAD campaign profile: <span className="badge amber">EXPERIMENTAL</span> — software-verified,
          awaiting a reviewed live campaign before autonomous promotion.
        </p>
      </>}
    </section>
  );
}
