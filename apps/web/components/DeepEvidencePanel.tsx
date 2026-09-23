"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ChildRecord, DeepObservation, EvidenceRevision } from "@/lib/types";

const OUTCOME_CLASS: Record<string, string> = {
  VERIFIED: "ok",
  CONTRADICTED: "bad",
  NOT_OBSERVED: "muted",
};

function summaryValue(summary: Record<string, unknown>, key: string): string {
  const value = summary[key];
  return typeof value === "number" || typeof value === "string" ? String(value) : "—";
}

function observationLabel(observation: DeepObservation): string {
  if (observation.outcome) return observation.outcome;
  return String(observation.availability ?? "NOT_OBSERVED");
}

function observationDetail(observation: DeepObservation): string {
  if (observation.claim) return observation.claim;
  const value = observation.observed?.value;
  const unit = observation.observed?.unit ?? "";
  return value === null || value === undefined ? `recorded measurement unavailable (${unit})` : `recorded measurement ${value} ${unit}`;
}

function judgmentDimensions(judgment: ChildRecord | undefined): Array<[string, string]> {
  const answers = (judgment?.vector as Record<string, unknown> | undefined)?.answers;
  if (!answers || typeof answers !== "object") return [];
  return Object.entries(answers as Record<string, Record<string, unknown>>).map(([question, answer]) => {
    if (answer?.kind === "noul") return [question, `p=${Number(answer.probability_yes).toFixed(2)}`];
    if (answer?.kind === "choice") return [question, String(answer.choice)];
    if (answer?.kind === "score") return [question, `${String(answer.score)}/4`];
    return [question, "—"];
  });
}

function judgmentLabel(judgment: ChildRecord | undefined): string {
  if (!judgment) return "no deep judgment recorded";
  const vector = judgment.vector as Record<string, unknown> | undefined;
  const error = vector?.error as { code?: string } | undefined;
  if (error?.code) return `deep judgment failed: ${error.code} (the revision stands)`;
  const dimensions = judgmentDimensions(judgment);
  if (!dimensions.length) return "deep judgment recorded with no usable answers";
  return `deep judgment: ${dimensions.map(([question, value]) => `${question} ${value}`).join(" · ")}`;
}

export function DeepEvidencePanel({ revisions, executions, judgments }: {
  revisions: ChildRecord[];
  executions: ChildRecord[];
  judgments: ChildRecord[];
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [payload, setPayload] = useState<EvidenceRevision | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (evidenceStateId: string) => {
    setError(null);
    setPayload(null);
    try {
      setPayload(await api<EvidenceRevision>(`/api/evidence/${evidenceStateId}`));
    } catch {
      setError("evidence artifact unavailable");
    }
  }, []);

  useEffect(() => {
    if (openId) void load(openId);
  }, [load, openId]);

  if (!revisions.length) return null;
  const ordered = [...revisions].sort((a, b) => Number(a.iteration ?? 0) - Number(b.iteration ?? 0));
  return (
    <section className="panel">
      <div className="eyebrow violet">DEEP DETERMINISTIC EVIDENCE — PYTHON-CONTROLLED</div>
      <h2>{ordered.length} immutable evidence revision(s)</h2>
      <p className="fine">
        One explicitly selected registered deterministic action ran on the candidate&apos;s accepted
        evidence E0. Each revision is immutable and links to its parent; a follow-up never rewrites
        earlier evidence. The deep Jev judgment is displayed as an input to the Python next-move
        policy, never as a measurement or an executed decision.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr><th>Iteration</th><th>Parent</th><th>Action</th><th>Checks</th><th>Evidence hash</th><th /><th>Deep Jev judgment (input to Python policy)</th></tr>
          </thead>
          <tbody>
            {ordered.map((row) => {
              const summary = (row.summary ?? {}) as Record<string, unknown>;
              const evidenceStateId = String(row.evidence_state_id);
              const judgment = judgments.find((entry) => String(entry.input_ref_id) === evidenceStateId);
              return (
                <tr key={evidenceStateId}>
                  <td>{String(row.iteration)}</td>
                  <td className="mono">{row.previous_evidence_state_id ? String(row.previous_evidence_state_id).slice(0, 8) : "—"}</td>
                  <td>{summaryValue(summary, "action_id")}</td>
                  <td className="fine">
                    verified {summaryValue(summary, "checks_verified")} · contradicted {summaryValue(summary, "checks_contradicted")} · not observed {summaryValue(summary, "checks_not_observed")}
                  </td>
                  <td className="mono">{String(row.evidence_hash).slice(0, 12)}…</td>
                  <td>
                    <button type="button" className="button ghost" onClick={() => setOpenId(openId === evidenceStateId ? null : evidenceStateId)}>
                      {openId === evidenceStateId ? "Hide" : "Inspect"}
                    </button>
                  </td>
                  <td className="fine">{judgmentLabel(judgment)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {executions.length > 0 && (
        <p className="fine mono">
          {executions.map((row) => `${String(row.action_id)} v${String(row.action_version)} → ${String(row.status)}`).join(" · ")}
        </p>
      )}
      {error && <p className="fine">{error}</p>}
      {openId && payload && (
        <div data-testid="evidence-revision">
          <h3>{payload.action?.title ?? "Accepted baseline evidence (E0)"}</h3>
          {payload.research_puzzle?.question && <p className="fine">{payload.research_puzzle.question}</p>}
          {payload.research_puzzle?.interpretation && <p className="fine muted">{payload.research_puzzle.interpretation}</p>}
          <div className="candidate-grid">
            {(payload.deterministic_observations ?? []).map((observation) => (
              <article className="mini-card" key={observation.result_id}>
                <span className={`badge ${OUTCOME_CLASS[observationLabel(observation)] ?? ""}`}>{observationLabel(observation)}</span>
                <h3>{observation.check_id ?? observation.method_id}</h3>
                <p>{observationDetail(observation)}</p>
                {observation.notes && observation.notes.length > 0 && <p className="fine">{observation.notes.join("; ")}</p>}
                <p className="fine mono">
                  n {observation.n_effective ?? "—"} · availability {observation.availability} · {observation.method_id} v{observation.method_version}
                </p>
              </article>
            ))}
          </div>
          {(payload.missing_evidence ?? []).length > 0 && (
            <p className="fine">
              missing evidence: {payload.missing_evidence?.map((item) => `${item.needed_evidence} (${item.availability})`).join(", ")}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
