"use client";

import { StatusBanner } from "@/components/StatusBanner";
import { workerLabel } from "@/components/SystemStatusPanel";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { formatBytes, formatCount } from "@/lib/format";
import type { SystemStatus } from "@/lib/types";

const READINESS = [
  { title: "Canonical campaign spine", state: "production-wired", tone: "live",
    body: "Mutation, expression, CNV shards, modality union, canonical state persistence and the pre-Wide policy execute in one autonomous run." },
  { title: "Durable program worker", state: "production-wired", tone: "live",
    body: "Release observation, identity-bound redispatch guard, bounded retry, lock-free sleep and canonical heartbeat." },
  { title: "Wide / Deep Jev question sets", state: "live-verified", tone: "live",
    body: "Question sets were revalidated against the pinned model in a live capture; each new deployment still needs its own provider verification." },
  { title: "LUAD autonomous profile", state: "experimental", tone: "amber",
    body: "No full live campaign with real Jev has completed; readiness stays EXPERIMENTAL and the worker idles by default." },
  { title: "Arm Jev", state: "deferred", tone: "fake",
    body: "JEV_REVIEW entries are carried as typed pending review and can never be promoted by favorable answers." },
  { title: "Functional and therapeutic axes", state: "deferred", tone: "fake",
    body: "No external functional annotation, dependency map or therapeutic interpretation is part of this deployment." },
];

export default function SystemPage() {
  const { data, error, updatedAt } = usePolling((signal) => api<SystemStatus>("/api/system", signal), 15000);
  return (
    <>
      <header className="page-title">
        <span className="eyebrow">Deployment posture</span>
        <h1>System</h1>
        <p>
          One application architecture: a read-only API over a single persistent data directory, a
          production web front end, and an optional autonomous worker. This page reports what the
          running process can actually do — and what it deliberately cannot claim.
        </p>
      </header>
      <StatusBanner error={error} updatedAt={updatedAt} />
      {data && (
        <>
          <div className="system-grid">
            <section className="panel">
              <span className="badge live">{data.mode}</span>
              <h2>Runtime</h2>
              <p>Single research process, SQLite with sequential migrations, immutable artifacts, FastAPI reads, HTTP polling.</p>
              <p className="muted mono">API v{data.versions.api} · schema v{data.versions.schema} · worker {data.versions.worker ?? "not recorded"}</p>
              <p className="fine">{workerLabel(data.worker)}</p>
              {data.active_run_id && <p className="fine mono">active run {data.active_run_id}</p>}
            </section>
            <section className="panel">
              <div className="eyebrow">Provider guardrail</div>
              <h2>Open-access GDC · semantic Jev · optional text</h2>
              {Object.entries(data.providers).map(([name, enabled]) => (
                <p key={name} className="row spread"><span>{name.toUpperCase()}</span><strong>{enabled ? "configured" : "off"}</strong></p>
              ))}
              <p className="fine">GDC transport is anonymous and open-access only: no token, no credential, no controlled data. Jev requires a server-side TYPESAFE_API_KEY and is used only for bounded semantic judgment.</p>
              <p className="fine">Configured budget caps: GDC requests {formatCount(data.budget_defaults.gdc_requests)}, GDC bytes {formatBytes(data.budget_defaults.gdc_bytes)}. {data.budget_defaults.reason}</p>
            </section>
            <section className="panel">
              <div className="eyebrow">Persistent data</div>
              <h2>{data.data.directory}</h2>
              <p className="muted">Database {formatBytes(data.data.database_bytes)} · {data.data.artifact_files} immutable artifacts indexed.</p>
              <p className="fine">Cursor: {data.cursor.present ? "present" : "absent"}. {data.cursor.reason}</p>
              <p className="fine">GDC cache: {data.cache.entries} entries ({formatBytes(data.cache.bytes ?? 0)}). Jev cache: {data.cache.jev_entries ?? 0} entries.</p>
            </section>
            <section className="panel">
              <div className="eyebrow">Claim boundary</div>
              <h2>What green software does not mean</h2>
              <p className="fine">
                A candidate is not an experimentally validated, therapeutically validated, or clinical
                target. Jev output is semantic judgment, not statistical significance, a p-value, an
                effect size, or scientific confidence. Every run is retained as an immutable record
                precisely so these claims can be audited later.
              </p>
            </section>
          </div>

          <section>
            <div className="section-heading">
              <div>
                <span className="eyebrow">Autonomy readiness</span>
                <h2>Implemented, verified, and deliberately deferred</h2>
              </div>
            </div>
            <div className="readiness">
              {READINESS.map((item) => (
                <div className="readiness-row" key={item.title}>
                  <strong>{item.title}</strong>
                  <span className={`badge ${item.tone === "live" ? "live" : item.tone === "amber" ? "amber" : "fake"}`}>{item.state}</span>
                  <p>{item.body}</p>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  );
}
