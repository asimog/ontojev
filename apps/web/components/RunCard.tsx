import Link from "next/link";
import type { ResearchRun } from "@/lib/types";

export function RunCard({ run }: { run: ResearchRun }) {
  const c = run.counts;
  return (
    <article className="panel run-card" data-testid={`run-${run.run_id}`}>
      <div className="row spread">
        <div><span className="badge fake">FAKE · SYNTHETIC</span><span className={`badge status ${run.status.toLowerCase()}`}>{run.status}</span></div>
        <span className="mono muted">{run.run_id.slice(0, 8)}</span>
      </div>
      <h2>{run.current_stage ?? (run.status === "COMPLETED" ? "Research run complete" : "Awaiting stage")}</h2>
      <p className="muted">Fixture {run.fixture_id} · {run.selected_project_ids.length} simulated projects · sequence {run.last_sequence}</p>
      <div className="metrics">
        <Metric label="States" value={c.states_generated} />
        <Metric label="Evaluated" value={c.states_evaluated} />
        <Metric label="Candidates" value={c.candidates_promoted} />
        <Metric label="Jev judgments" value={c.jev_evaluations} />
        <Metric label="Hypotheses" value={c.hypotheses_created} />
        <Metric label="Follow-ups" value={c.followups_started} />
        <Metric label="Dossiers" value={c.dossiers_created} />
      </div>
      <Link className="button" href={`/runs/${run.run_id}`}>Open live run</Link>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><strong>{value}</strong><span>{label}</span></div>;
}
