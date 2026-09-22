import Link from "next/link";
import type { ResearchRun } from "@/lib/types";
import { formatBytes, formatCost, formatDuration, formatTime } from "@/lib/format";

export function RunCard({ run }: { run: ResearchRun }) {
  const c = run.counts;
  const u = run.provider_usage;
  return (
    <article className="panel run-card" data-testid={`run-${run.run_id}`}>
      <div className="row spread">
        <div><span className="badge fake">FAKE · SYNTHETIC</span><span className={`badge status ${run.status.toLowerCase()}`}>{run.status}</span></div>
        <span className="mono muted">{run.run_id.slice(0, 8)}</span>
      </div>
      <h2>{run.current_stage ?? (run.status === "COMPLETED" ? "Research run complete" : "Awaiting stage")}</h2>
      <p className="muted">Fixture {run.fixture_id} v{run.fixture_version} · {run.selected_project_ids.length} simulated projects · sequence {run.last_sequence}</p>
      <p className="muted mono">started {formatTime(run.started_at ?? run.created_at)} · elapsed {formatDuration(run.started_at, run.ended_at)}</p>
      <div className="metrics">
        <Metric label="States" value={c.states_generated} />
        <Metric label="Evaluated" value={c.states_evaluated} />
        <Metric label="Candidates" value={c.candidates_promoted} />
        <Metric label="Jev evaluations" value={c.jev_evaluations} />
        <Metric label="Hypotheses" value={c.hypotheses_created} />
        <Metric label="Follow-ups" value={c.followups_started} />
        <Metric label="Dossiers" value={c.dossiers_created} />
      </div>
      <details className="counter-more">
        <summary>More counters</summary>
        <div className="metrics secondary">
          <Metric label="Projects simulated" value={c.projects_completed} />
          <Metric label="Valid states" value={c.states_valid} />
          <Metric label="GDC requests" value={u.gdc_requests} />
          <Metric label="GDC bytes" value={formatBytes(u.gdc_bytes)} />
          <Metric label="Jev calls" value={u.jev_calls} />
          <Metric label="LLM calls" value={u.llm_calls} />
          <Metric label="Jev cost" value={formatCost(u.jev_cost)} />
          <Metric label="LLM cost" value={formatCost(u.llm_cost)} />
        </div>
      </details>
      <Link className="button" href={`/runs/${run.run_id}`}>Open live run</Link>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return <div><strong>{value}</strong><span>{label}</span></div>;
}
