"use client";

import { usePolling } from "@/hooks/usePolling";
import { api } from "@/lib/api";
import { StatusBanner } from "@/components/StatusBanner";
import { RunFeed } from "@/components/RunFeed";

type Portfolio = {
  domain: string;
  revision: number;
  operational_state: string;
  evidence_ids: string[];
  interpretations: Array<{
    question_id: string;
    evidence_ids: string[];
    conclusion: string;
    uncertainty: string[];
  }>;
  questions: Array<{
    question_id: string;
    question: string;
    rationale: string;
    project_id: string;
    status: string;
    priority: number;
    uncertainty: string[];
    next_action: string;
  }>;
};

export function Laboratory() {
  const { data, error, updatedAt } = usePolling((signal) => api<Portfolio>("/api/lab", signal), 5000);
  return <>
    <StatusBanner error={error} updatedAt={updatedAt} />
    <header className="hero">
      <div>
        <span className="kicker">Laboratory Observatory</span>
        <h1>Research questions. Durable evidence.</h1>
        <p className="lede">OntoCodex directs bounded experiments. Jev provides typed judgments.
          Python validates and executes. Every block preserves its scientific record.</p>
        {data && <p className="mono">{data.operational_state} · revision {data.revision} · {data.evidence_ids.length} evidence artifacts</p>}
      </div>
    </header>
    <section aria-labelledby="portfolio-title">
      <div className="section-heading"><h2 id="portfolio-title">Research portfolio</h2></div>
      {data?.questions.length === 0 && <p className="panel empty">No research question has been recorded yet.</p>}
      {data?.questions.map((question) => <article className="panel" key={question.question_id}>
        <span className="badge">{question.project_id}</span> <span className="badge">{question.status}</span>
        <span className="mono muted"> Priority {question.priority} · control decision</span>
        <h3>{question.question}</h3>
        <p>{question.rationale}</p>
        <details><summary>Uncertainty and next action</summary>
          <ul>{question.uncertainty.map((item) => <li key={item}>{item}</li>)}</ul>
          <p><strong>Next:</strong> {question.next_action}</p>
        </details>
      </article>)}
    </section>
    {data && data.interpretations.length > 0 && <section aria-labelledby="interpretations-title">
      <div className="section-heading"><h2 id="interpretations-title">Latest interpretations</h2></div>
      {data.interpretations.slice(-5).reverse().map((interpretation, index) => <article className="panel" key={`${interpretation.question_id}-${index}`}>
        <span className="badge">Director judgment</span>
        <p className="fine">{interpretation.question_id} · {interpretation.evidence_ids.length} retained evidence references</p>
        <p>{interpretation.conclusion}</p>
        <details><summary>Uncertainty and evidence references</summary>
          <ul>{interpretation.uncertainty.map((item) => <li key={item}>{item}</li>)}</ul>
          <p className="mono" style={{ overflowWrap: "anywhere" }}>{interpretation.evidence_ids.join(" · ")}</p>
        </details>
      </article>)}
    </section>}
    <section><div className="section-heading"><h2>Research Run blocks</h2></div><RunFeed /></section>
  </>;
}

export function LaboratoryRun({ runId }: { runId: string }) {
  const { data, error, updatedAt } = usePolling((signal) => api<{
    documents: Array<{ purpose: string; artifact_id: string; sha256: string; document: unknown }>;
  }>(`/api/runs/${runId}/lab`, signal), 5000);
  return <section className="panel" aria-labelledby="lab-story">
    <h2 id="lab-story">Research block notebook</h2>
    <p className="fine">Immutable decision, preflight, Jev control judgments, provenance and portfolio revision.
      Control judgments and director interpretations are separate from measured evidence.</p>
    <StatusBanner error={error} updatedAt={updatedAt} />
    {data?.documents.filter((item) => item.purpose === "lab-scientific-stage").map((item) =>
      <ScientificResultSummary key={item.artifact_id} document={item.document} />)}
    {data?.documents.map((item) => <details key={item.artifact_id}>
      <summary>{item.purpose}</summary>
      {item.purpose === "jev-research-control" && <JevDecisionSummary document={item.document} />}
      <p className="fine mono">SHA-256 {item.sha256}</p>
      <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(item.document, null, 2)}</pre>
    </details>)}
  </section>;
}

function ScientificResultSummary({ document }: { document: unknown }) {
  if (!document || typeof document !== "object") return null;
  const record = document as Record<string, unknown>;
  const titles: Record<string, string> = {
    CAMPAIGN_CNV_MERGE_V1: "Complete CNV evidence assembled",
    CAMPAIGN_COMPOSE_V1: "Multimodal StatisticalState composed",
    CAMPAIGN_WIDE_V1: "Wide evaluation and Candidate admission",
    CAMPAIGN_INVESTIGATE_V1: "Candidate investigation and dossier",
  };
  const states = Array.isArray(record.state_ids) ? record.state_ids : [];
  const candidates = Array.isArray(record.candidate_ids) ? record.candidate_ids : [];
  const inputs = Array.isArray(record.inputs) ? record.inputs : [];
  const outputs = Array.isArray(record.outputs) ? record.outputs : [];
  return <article>
    <h3>{titles[String(record.method)] ?? "Scientific result"}</h3>
    <p>{String(record.project_id)} · {String(record.release)} · question {String(record.question_id)}</p>
    <p>{inputs.length} verified source artifacts · {outputs.length} canonical output artifacts
      {states.length > 0 && ` · ${states.length} StatisticalStates`}
      {candidates.length > 0 && ` · ${candidates.length} Candidates`}</p>
    <p className="fine">Measurements retain their scientific provenance. Jev judgments and director interpretations remain separately recorded.</p>
  </article>;
}

function JevDecisionSummary({ document }: { document: unknown }) {
  if (!document || typeof document !== "object") return null;
  const record = document as Record<string, unknown>;
  const contract = record.decision_contract as Record<string, unknown> | undefined;
  const questions = contract?.questions as Array<{ id: string; instructions: string }> | undefined;
  const answers = record.answers as Record<string, Record<string, unknown>> | undefined;
  return <div>
    <p><strong>Research control</strong> · {String(contract?.contract_id ?? record.question_set_version)}
      {contract && ` · ${String(contract.evaluation_status)}`}</p>
    <p>{record.execution_mode === "SHADOW"
      ? "Shadow evaluation: OntoCodex made its decision without these answers. This judgment supplies no biological support."
      : "Recorded acquisition relevance advice. This judgment supplies no biological support."}</p>
    {questions?.map((question) => <div key={question.id}>
      <p>{question.instructions}</p>
      <p className="mono">{JSON.stringify(answers?.[question.id] ?? { status: "ABSTAINED" })}</p>
    </div>)}
    {record.fallback != null && <p>Fallback: {String(record.fallback)}</p>}
  </div>;
}
