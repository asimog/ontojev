"use client";

import type { WideRanking } from "@/lib/types";

const DIMENSION_LABELS: Record<string, string> = {
  projects_with_mutation_observation: "projects",
  affected_case_total: "affected total",
  top_project_share: "top share",
  coverage_imbalance: "imbalance",
  warrants_deeper_investigation: "warrants",
  likely_fragile: "fragile",
  pattern_type: "pattern",
  pattern_type_confidence: "pattern conf.",
};

function formatDimension(key: string, value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value === "number") return value.toFixed(key.includes("confidence") || key.includes("share") || key.startsWith("warrants") || key === "likely_fragile" ? 2 : 0);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return String(value);
}

function RankingTable({ ranking, admitted }: { ranking: WideRanking; admitted: Set<string> }) {
  return (
    <article className="ranking">
      <h3>
        {ranking.kind === "BASELINE" ? "Deterministic baseline" : "Jev policy"}
        <span className="fine mono"> · {ranking.policy_version}</span>
      </h3>
      <p className="fine">{ranking.ordering}</p>
      <table>
        <thead>
          <tr><th>#</th><th>Gene</th><th>Dimensions</th><th>Admitted</th></tr>
        </thead>
        <tbody>
          {ranking.entries.map((entry) => (
            <tr key={`${ranking.kind}-${entry.state_id}`}>
              <td>{entry.rank}</td>
              <td><strong>{entry.gene_symbol}</strong></td>
              <td>
                <div className="dimension-list">
                  {Object.entries(entry.dimensions)
                    .filter(([key]) => key in DIMENSION_LABELS)
                    .map(([key, value]) => (
                      <span key={key}>{DIMENSION_LABELS[key]} {formatDimension(key, value)}</span>
                    ))}
                </div>
              </td>
              <td>{admitted.has(entry.state_id) ? "yes" : ""}</td>
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
  return (
    <section className="panel" data-testid="wide-ranking">
      <div className="eyebrow violet">JEV JUDGMENT — POLICY RANKING, NOT A MEASUREMENT</div>
      <h2>Baseline vs Jev wide ranking</h2>
      <p className="fine">
        Both rankings are retained for the same states. The baseline is deterministic; the Jev ranking uses raw
        judgment dimensions with an explicit policy. No merged opaque score exists.
      </p>
      <div className="ranking-grid">
        {baseline && <RankingTable ranking={baseline} admitted={admitted} />}
        {jev && <RankingTable ranking={jev} admitted={admitted} />}
      </div>
    </section>
  );
}
