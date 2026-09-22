import type { ResearchRun } from "@/lib/types";
import { formatBytes, formatCost, formatCount } from "@/lib/format";

export function BudgetSummary({ run }: { run: ResearchRun }) {
  const usage = run.provider_usage;
  const live = run.mode === "LIVE";
  return (
    <section className="panel" data-testid="budget-summary">
      <div className="eyebrow">BUDGET / USAGE</div>
      <h2>Provider usage versus configured caps</h2>
      <div className="metrics">
        <div><strong>{formatCount(usage.gdc_requests)}</strong><span>GDC requests</span></div>
        <div><strong>{formatCount(usage.gdc_cache_hits ?? 0)}</strong><span>GDC cache hits</span></div>
        <div><strong>{formatBytes(usage.gdc_bytes)}</strong><span>GDC bytes</span></div>
        <div><strong>{formatCount(usage.jev_calls)}</strong><span>Jev provider calls</span></div>
        <div><strong>{formatCount(usage.llm_calls)}</strong><span>LLM calls</span></div>
        <div><strong>{formatCount(run.counts.jev_evaluations)}</strong><span>Jev evaluations</span></div>
        <div><strong>{formatCount(usage.jev_input_tokens ?? null)}</strong><span>Jev input tokens</span></div>
        <div><strong>{formatCost(usage.jev_cost)}</strong><span>Jev cost</span></div>
        <div><strong>{formatCost(usage.llm_cost)}</strong><span>LLM cost</span></div>
      </div>
      <p className="fine">
        {live
          ? "Live mode: GDC requests are anonymous, open-access and bounded by the transport; cached responses make no network call. A Jev cache hit counts as an evaluation, not a provider call."
          : "Fixture mode makes zero provider calls and zero provider bytes; simulated Jev evaluations are labeled FAKE and never count as provider calls."}
      </p>
    </section>
  );
}
