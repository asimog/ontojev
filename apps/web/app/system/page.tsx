"use client";

import { StatusBanner } from "@/components/StatusBanner";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";

type System = { phase: number; mode: string; providers: Record<string, boolean>; active_run_id: string | null; worker: { heartbeat_at: string } | null };
export default function SystemPage() { const { data, error, updatedAt } = usePolling((signal) => api<System>("/api/system", signal), 5000); return <><header className="page-title"><span className="eyebrow">LOCAL RUNTIME</span><h1>System</h1></header><StatusBanner error={error} updatedAt={updatedAt} />{data && <div className="system-grid"><section className="panel"><span className="badge fake">{data.mode}</span><h2>Phase {data.phase}</h2><p>Single local research process, SQLite, immutable artifacts, FastAPI reads, and HTTP polling.</p></section><section className="panel"><div className="eyebrow">PROVIDER GUARDRAIL</div><h2>External integrations disabled</h2>{Object.entries(data.providers).map(([name, enabled]) => <p key={name} className="row spread"><span>{name.toUpperCase()}</span><strong>{enabled ? "enabled" : "0 calls · disabled"}</strong></p>)}</section><section className="panel"><div className="eyebrow">WORKER RECORD</div><h2>{data.active_run_id ? "Run active" : "No active run"}</h2><p>{data.worker?.heartbeat_at ? `Last canonical write ${new Date(data.worker.heartbeat_at).toLocaleString()}` : "Worker has not written yet."}</p></section></div>}</>; }

