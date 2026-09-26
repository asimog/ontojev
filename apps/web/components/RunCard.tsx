import Link from "next/link";
import type { ResearchRun } from "@/lib/types";
import { formatBytes, formatCost, formatDuration, formatTime, plural } from "@/lib/format";

export function RunCard({ run }: { run: ResearchRun }) {
  const c = run.counts;
  const u = run.provider_usage;
  const live = run.mode === "LIVE";
  const projectCount = (run.selected_project_ids ?? []).length;
  const title = run.status === "COMPLETED"
    ? (live ? "Campaign complete" : "Synthetic campaign complete")
    : run.current_stage ?? "Awaiting stage";
  return (
    <article className={`panel run-card status-${run.status.toLowerCase()}`} data-testid={`run-${run.run_id}`}>
      <div className="row spread">
        <div>
          <span className={`badge ${live ? "live" : "fake"}`}>{live ? "LIVE · OPEN GDC" : "FAKE · SYNTHETIC"}</span>
          <span className={`badge status ${run.status.toLowerCase()}`}>{run.status}</span>
        </div>
        <span className="mono muted">{run.run_id.slice(0, 8)}</span>
      </div>
      <h2>{title}</h2>
      <p className="muted">
        {live
          ? `${plural(projectCount, "project")} · coverage ${run.coverage} · sequence ${run.last_sequence}`
          : `Fixture ${run.fixture_id} v${run.fixture_version} · ${plural(projectCount, "simulated project")} · sequence ${run.last_sequence}`}
      </p>
      <p className="muted mono">started {formatTime(run.started_at ?? run.created_at)} · elapsed {formatDuration(run.started_at, run.ended_at)}</p>
      <div className="metrics">
        <Metric label="States" value={c.states_generated} />
        <Metric label="Evaluated" value={c.states_evaluated} />
        <Metric label="Candidates" value={c.candidates_promoted} />
        <Metric label="Jev evaluations" value={c.jev_evaluations} />
        <Metric label="Hypotheses" value={c.hypotheses_created} />
        <Metric label="Follow-ups" value={c.followups_started} />
        <Metric label="Evidence revisions" value={c.evidence_revisions ?? 0} />
        <Metric label="Dossiers" value={c.dossiers_created} />
      </div>
      <details className="counter-more">
        <summary>Provider usage and more counters</summary>
        <div className="metrics secondary">
          <Metric label="Projects examined" value={c.projects_completed} />
          <Metric label="Valid states" value={c.states_valid} />
          <Metric label="GDC requests" value={u.gdc_requests} />
          <Metric label="GDC cache hits" value={u.gdc_cache_hits ?? 0} />
          <Metric label="GDC bytes" value={formatBytes(u.gdc_bytes)} />
          <Metric label="Jev provider calls" value={u.jev_calls} />
          <Metric label="LLM calls" value={u.llm_calls} />
          <Metric label="Jev cost" value={formatCost(u.jev_cost)} />
          <Metric label="LLM cost" value={formatCost(u.llm_cost)} />
        </div>
      </details>
      <div className="card-actions">
        <Link className="button" href={`/runs/${run.run_id}`}>Open run →</Link>
        <span className="fine mono">worker {run.worker_id}</span>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return <div><strong>{value}</strong><span>{label}</span></div>;
}
