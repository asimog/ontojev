"use client";

import { StatusBanner } from "@/components/StatusBanner";
import { workerLabel } from "@/components/SystemStatusPanel";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { formatBytes, formatCount } from "@/lib/format";
import type { SystemStatus } from "@/lib/types";

export default function SystemPage() {
  const { data, error, updatedAt } = usePolling((signal) => api<SystemStatus>("/api/system", signal), 15000);
  return (
    <>
      <header className="page-title"><span className="eyebrow">LOCAL RUNTIME</span><h1>System</h1></header>
      <StatusBanner error={error} updatedAt={updatedAt} />
      {data && (
        <div className="system-grid">
          <section className="panel">
            <span className="badge live">{data.mode}</span>
            <h2>Phase {data.phase}</h2>
            <p>Single local research process, SQLite, immutable artifacts, FastAPI reads, and HTTP polling.</p>
            <p className="muted mono">API v{data.versions.api} · schema v{data.versions.schema} · worker {data.versions.worker ?? "not recorded"}</p>
          </section>
          <section className="panel">
            <div className="eyebrow">PROVIDER GUARDRAIL</div>
            <h2>Open-access GDC · semantic Jev · no LLM</h2>
            {Object.entries(data.providers).map(([name, enabled]) => <p key={name} className="row spread"><span>{name.toUpperCase()}</span><strong>{enabled ? "enabled" : "off"}</strong></p>)}
            <p className="fine">GDC transport is anonymous and open-access only: no token, no credential, no file download. Jev requires a server-side TYPESAFE_API_KEY and is used only for bounded semantic judgment.</p>
            <p className="fine">Configured live budget caps: GDC requests {formatCount(data.budget_defaults.gdc_requests)}, GDC bytes {formatBytes(data.budget_defaults.gdc_bytes)}. {data.budget_defaults.reason}</p>
          </section>
          <section className="panel">
            <div className="eyebrow">WORKER RECORD</div>
            <h2>{data.active_run_id ? "Run active" : "No active run"}</h2>
            <p>{workerLabel(data.worker)}</p>
            {data.active_run_id && <p className="mono muted">{data.active_run_id}</p>}
          </section>
          <section className="panel">
            <div className="eyebrow">LOCAL DATA</div>
            <h2>{data.data.directory}</h2>
            <p className="muted">Database {formatBytes(data.data.database_bytes)} · {data.data.artifact_files} immutable artifacts indexed.</p>
            <p className="fine">Cursor: {data.cursor.present ? "present" : "absent"}. {data.cursor.reason}</p>
            <p className="fine">GDC cache: {data.cache.entries} entries ({formatBytes(data.cache.bytes ?? 0)}). Jev cache: {data.cache.jev_entries ?? 0} entries.</p>
          </section>
        </div>
      )}
    </>
  );
}
