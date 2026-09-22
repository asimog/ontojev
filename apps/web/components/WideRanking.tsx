"use client";

import type { WideRanking } from "@/lib/types";

const DIMENSION_LABELS: Record<string, string> = {
  affected_cases: "affected cases",
  mutation_observed: "mutation observed",
  coverage_imbalance: "imbalance",
  evidence_quality_adequate: "quality",
  mutation_evidence_coherent: "mutation coherent",
  expression_evidence_coherent: "expression coherent",
  signal_explained_by_coverage: "coverage confound",
  unresolved_uncertainty_material: "uncertainty",
  warrants_deeper_investigation: "warrants",
  dominant_limitation: "limitation",
  dominant_limitation_confidence: "limitation conf.",
};

function formatDimension(key: string, value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return value.toFixed(key === "affected_cases" ? 0 : 2);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function policyResult(ranking: WideRanking, stateId: string, entry: WideRanking["entries"][number],
  admitted: Set<string>, baselineTop: Set<string>): string {
  if (ranking.kind === "BASELINE") return baselineTop.has(stateId) ? "top 3 for comparison" : "";
  if (admitted.has(stateId)) return "admitted";
  if (entry.qualified) return "qualified; over limit";
  return entry.excluded_reason ?? "not admitted";
}

function RankingTable({ ranking, admitted, baselineTop }: {
  ranking: WideRanking;
  admitted: Set<string>;
  baselineTop: Set<string>;
}) {
  return (
    <article className="ranking">
      <h3>
        {ranking.kind === "BASELINE" ? "Deterministic baseline" : "Jev policy"}
        <span className="fine mono"> · {ranking.policy_version}</span>
      </h3>
      <p className="fine">{ranking.ordering}</p>
      <table>
<thead>
          <tr><th>#</th><th>Gene</th><th>State / evaluation</th><th>Dimensions</th><th>Policy result</th></tr>
        </thead>
        <tbody>
          {ranking.entries.map((entry) => (
            <tr key={`${ranking.kind}-${entry.state_id}`}>
              <td>{entry.rank}</td>
              <td><strong>{entry.gene_symbol}</strong></td>
              <td className="fine mono">
                <code title={entry.state_id}>{entry.state_id.slice(0, 8)}…</code>
                <br />
                <small className="mono">{entry.evaluation_id ? `${entry.evaluation_id.slice(0, 8)}…` : "no evaluation"}</small>
              </td>
              <td>
                <div className="dimension-list">
                  {Object.entries(entry.dimensions)
                    .filter(([key]) => key in DIMENSION_LABELS)
                    .map(([key, value]) => (
                      <span key={key}>{DIMENSION_LABELS[key]} {formatDimension(key, value)}</span>
                    ))}
                </div>
              </td>
              <td>{policyResult(ranking, entry.state_id, entry, admitted, baselineTop)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

export function WideRankingPanel({ baseline, jev }: { baseline: WideRanking | null; jev: WideRanking | null }) {
  if (!baseline && !jev) return null;
  const admitted = new Set(jev?.admitted_state_ids ?? []);
  const baselineTop = new Set(baseline?.top_state_ids ?? []);
  const decision = jev?.admission;
  return (
    <section className="panel" data-testid="wide-ranking">
      <div className="eyebrow violet">JEV JUDGMENT — POLICY RANKING, NOT A MEASUREMENT</div>
      <h2>Baseline vs Jev wide ranking</h2>
      <p className="fine">
        Both rankings are retained for the same states. The baseline is deterministic; the Jev ranking uses raw
        judgment dimensions with an explicit policy. Baseline top-3 is for comparison only and never promotes a
        candidate. No merged opaque score exists.
      </p>
      {decision && (
        <p className="callout" data-testid="wide-admission-decision">
          Admission: <strong>{decision.decision}</strong> · {jev?.admitted_state_ids.length ?? 0} admitted ·
          maximum {decision.promotion_limit}. Thresholds: warrants &gt;= {decision.thresholds.warrants_deeper_investigation_min},
          uncertainty &gt;= {decision.thresholds.unresolved_uncertainty_material_min},
          quality &gt;= {decision.thresholds.evidence_quality_adequate_min},
          coverage confound &lt;= {decision.thresholds.signal_explained_by_coverage_max}.
        </p>
      )}
      <div className="ranking-grid">
        {baseline && <RankingTable ranking={baseline} admitted={admitted} baselineTop={baselineTop} />}
        {jev && <RankingTable ranking={jev} admitted={admitted} baselineTop={baselineTop} />}
      </div>
    </section>
  );
}
