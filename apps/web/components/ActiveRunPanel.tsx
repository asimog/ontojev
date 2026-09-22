"use client";

import { BudgetSummary } from "@/components/BudgetSummary";
import { RunCard } from "@/components/RunCard";
import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import type { Envelope, ResearchRun } from "@/lib/types";

export function ActiveRunPanel() {
  const { data } = usePolling((signal) => api<Envelope<ResearchRun>>("/api/runs?limit=5", signal), 8000);
  const active = data?.items.find((run) => run.status === "PENDING" || run.status === "RUNNING");
  const latest = data?.items[0];
  if (!active && !latest) return null;
  return (
    <>
      <section>
        <div className="section-heading"><div><span className="eyebrow">{active ? "ACTIVE RUN" : "MOST RECENT RUN"}</span><h2>{active ? "Research in progress" : "Latest durable record"}</h2></div></div>
        {active ? <div className="run-grid single"><RunCard run={active} /></div> : latest ? <div className="run-grid single"><RunCard run={latest} /></div> : null}
      </section>
      {latest && <BudgetSummary run={active ?? latest} />}
    </>
  );
}
