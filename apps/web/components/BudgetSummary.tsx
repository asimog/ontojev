import type { ResearchRun } from "@/lib/types";
import { formatBytes, formatCost, formatCount } from "@/lib/format";

export function BudgetSummary({ run }: { run: ResearchRun }) {
  const usage = run.provider_usage;
  return (
    <section className="panel" data-testid="budget-summary">
      <div className="eyebrow">BUDGET / USAGE</div>
      <h2>Provider usage versus configured caps</h2>
      <div className="metrics">
        <div><strong>{formatCount(usage.gdc_requests)}</strong><span>GDC requests</span></div>
        <div><strong>{formatBytes(usage.gdc_bytes)}</strong><span>GDC bytes</span></div>
        <div><strong>{formatCount(usage.jev_calls)}</strong><span>Jev calls</span></div>
        <div><strong>{formatCount(usage.llm_calls)}</strong><span>LLM calls</span></div>
        <div><strong>{formatCount(run.counts.jev_evaluations)}</strong><span>Simulated Jev evaluations</span></div>
        <div><strong>{formatCost(usage.jev_cost)}</strong><span>Jev cost</span></div>
        <div><strong>{formatCost(usage.llm_cost)}</strong><span>LLM cost</span></div>
      </div>
      <p className="fine">Fixture mode makes zero provider calls and zero provider bytes. Live GDC/Jev/LLM caps are Phase 2; token and cost usage stays unknown until real calls exist.</p>
    </section>
  );
}
