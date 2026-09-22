"use client";

type Answer = {
  kind: "noul" | "choice" | "score";
  probability_yes?: number;
  choice?: string;
  confidence?: number;
  probabilities?: Record<string, number>;
  score?: number;
  legend?: Record<string, string>;
};

type Applicability = { applicable: boolean; reason: string; rule: string };

export type LiveEvaluationVector = {
  evaluation_id: string;
  mode: "LIVE";
  error: { code: string; detail: string } | null;
  answers: Record<string, Answer>;
  applicability: Record<string, Applicability>;
  requested_model: string;
  resolved_model: string | null;
  usage: { input_tokens?: number | null; output_tokens?: number | null };
  latency_ms: number | null;
  cache_source_evaluation_id: string | null;
  question_set_version: string;
};

const QUESTION_LABELS: Record<string, string> = {
  evidence_quality_adequate: "Evidence quality adequate",
  mutation_evidence_coherent: "Mutation evidence coherent",
  expression_evidence_coherent: "Expression evidence coherent",
  signal_explained_by_coverage: "Signal explained by coverage",
  unresolved_uncertainty_material: "Material uncertainty remains",
  warrants_deeper_investigation: "Warrants deeper investigation",
  dominant_limitation: "Dominant limitation",
};

function percent(value?: number | null): string {
  return value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`;
}

function NoulRow({ id, answer, applicable }: { id: string; answer: Answer; applicable?: Applicability }) {
  const probability = answer.probability_yes ?? null;
  return (
    <article className={applicable?.applicable === false ? "judgment-row inapplicable" : "judgment-row"}>
      <span>{QUESTION_LABELS[id] ?? id}</span>
      <strong>{percent(probability)}</strong>
      <small>
        probability the proposition is true · {applicable?.applicable === false ? `inapplicable (${applicable.reason})` : "applicable"}
      </small>
    </article>
  );
}

function ChoiceRow({ id, answer, applicable }: { id: string; answer: Answer; applicable?: Applicability }) {
  return (
    <article className={applicable?.applicable === false ? "judgment-row inapplicable" : "judgment-row"}>
      <span>{QUESTION_LABELS[id] ?? id}</span>
      <strong>{answer.choice}</strong>
      <div className="distribution">
        {Object.entries(answer.probabilities ?? {}).map(([key, value]) => (
          <span key={key}>{key} {percent(value)}</span>
        ))}
      </div>
      <small>confidence {percent(answer.confidence)} · {applicable?.applicable === false ? `inapplicable (${applicable.reason})` : "applicable"}</small>
    </article>
  );
}

export function WideJudgment({ vector }: { vector: LiveEvaluationVector }) {
  if (vector.error) {
    return (
      <section className="judgment" data-testid="wide-judgment">
        <div className="eyebrow coral">JEV JUDGMENT — FAILED CLOSED</div>
        <p className="fine">Evaluation {vector.evaluation_id} recorded no judgment: {vector.error.code}.</p>
      </section>
    );
  }
  return (
    <section className="judgment" data-testid="wide-judgment">
      <div className="eyebrow violet">JEV JUDGMENT — NOT A MEASUREMENT</div>
      <p className="fine mono">
        {vector.resolved_model ?? vector.requested_model} · question set {vector.question_set_version} ·
        tokens {vector.usage.input_tokens ?? "—"}/{vector.usage.output_tokens ?? "—"} ·
        latency {vector.latency_ms ?? "—"} ms · {vector.cache_source_evaluation_id ? "cache hit" : "fresh call"}
      </p>
      <div className="judgment-grid">
        {Object.entries(vector.answers).map(([id, answer]) =>
          answer.kind === "choice" ? (
            <ChoiceRow key={id} id={id} answer={answer} applicable={vector.applicability[id]} />
          ) : (
            <NoulRow key={id} id={id} answer={answer} applicable={vector.applicability[id]} />
          ),
        )}
      </div>
      <p className="fine">
        Semantic model output — not statistical significance, a p-value, an effect size, or scientific
        confidence. Applicability is decided by deterministic code from the evidence.
      </p>
    </section>
  );
}
