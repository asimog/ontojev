"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ChildRecord, Metric } from "@/lib/types";

function metricText(metric: Metric | undefined): string {
  if (!metric) return "—";
  if (metric.availability === "OBSERVED" && metric.value !== null) {
    return metric.unit === "cases" ? String(metric.value) : `${metric.value} ${metric.unit}`;
  }
  if (metric.availability === "NOT_OBSERVED") return "not observed";
  if (metric.availability === "NOT_ACQUIRED") return "not acquired";
  if (metric.availability === "INSUFFICIENT") return "insufficient";
  if (metric.availability === "PARTIAL") return "partial";
  return metric.availability.toLowerCase().replace(/_/g, " ");
}

export function DeterministicStatePanel({ states }: { states: ChildRecord[] }) {
  const [openStateId, setOpenStateId] = useState<string | null>(null);
  const [fullState, setFullState] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!states.length) return null;

  const toggle = async (stateId: string) => {
    if (openStateId === stateId) {
      setOpenStateId(null);
      setFullState(null);
      return;
    }
    setOpenStateId(stateId);
    setFullState(null);
    setError(null);
    try {
      setFullState(await api<Record<string, unknown>>(`/api/states/${stateId}`));
    } catch {
      setError("state artifact unavailable");
    }
  };

  return (
    <section className="panel" data-testid="deterministic-states">
      <div className="eyebrow amber">DETERMINISTIC — MEASURED</div>
      <h2>{states.length} statistical states from open GDC evidence</h2>
      <p className="fine">
        Counts are provider-defined case counts with no matched denominator; an absent bucket is not observed,
        never zero. Expression summaries are local log2(UQFPKM+1) statistics on the examined case set.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Gene</th><th>Mutation</th><th>Expression</th><th>Projects</th><th>Top share</th>
              <th>Coverage imbalance</th><th>Completeness</th><th />
            </tr>
          </thead>
          <tbody>
            {states.map((record) => {
              const summary = record.summary as Record<string, unknown>;
              const entity = summary.entity as { gene_symbol?: string; gene_id?: string };
              const stateId = String(record.state_id);
              const topShare = summary.top_project_share as Metric | undefined;
              return (
                <tr key={stateId}>
                  <td><strong>{entity?.gene_symbol ?? "—"}</strong><br /><span className="fine mono">{entity?.gene_id}</span></td>
                  <td>
                    {metricText(summary.affected_case_total as Metric)} cases
                    <br /><span className="fine">{String(summary.mutation_availability)}</span>
                  </td>
                  <td>
                    {String(summary.expression_availability)}
                    <br /><span className="fine">{summary.projects_with_expression_observation as number} project(s) with local summary</span>
                  </td>
                  <td>{String(summary.projects_with_mutation_observation)} mutation · {String(summary.projects_with_expression_observation)} expression</td>
                  <td>{topShare?.availability === "OBSERVED" && topShare.value !== null ? topShare.value.toFixed(2) : "n/a"}</td>
                  <td>{summary.coverage_imbalance ? "flagged" : "no"}</td>
                  <td>{String(summary.completeness)}</td>
                  <td><button type="button" className="button ghost" onClick={() => void toggle(stateId)}>{openStateId === stateId ? "Hide" : "Inspect"}</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {openStateId && (
        <div className="state-detail">
          {error && <p className="fine coral">{error}</p>}
          {!fullState && !error && <p className="fine">Loading state artifact…</p>}
          {fullState && <pre className="artifact">{JSON.stringify(fullState, null, 2)}</pre>}
        </div>
      )}
    </section>
  );
}
