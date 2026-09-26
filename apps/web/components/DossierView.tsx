"use client";

import { useEffect, useState } from "react";
import { apiUrl, apiWithMeta } from "@/lib/api";
import { formatLabel } from "@/lib/format";

type Section = { availability: string; reason: string | null; narrative: string | null };
type Dossier = {
  dossier_id: string;
  run_id: string;
  candidate_id: string;
  mode: string;
  warning: string;
  evidence_state_ids: string[];
  hypothesis_ids: string[];
  sections: Record<string, Section>;
};

const GROUPS: Array<{ title: string; keys: string[] }> = [
  { title: "OBSERVED DETERMINISTIC FACTS", keys: ["research_puzzle", "candidate_entity", "investigation_rationale", "initial_broad_evidence", "deterministic_deep_evidence", "project_evidence", "cross_project_evidence", "cross_modal_evidence", "contradictory_evidence", "missing_unavailable_evidence"] },
  { title: "JEV JUDGMENTS", keys: ["jev_wide_judgments", "jev_deep_judgments", "hypothesis_jev_reviews"] },
  { title: "GENERATED FIXTURE HYPOTHESES", keys: ["competing_hypotheses", "proposed_wet_lab_experiment", "predictions_by_hypothesis", "falsification_criteria"] },
  { title: "FOLLOW-UP AND REMAINING UNCERTAINTY", keys: ["deterministic_followups_performed", "followup_results", "remaining_uncertainty"] },
  { title: "PROVENANCE AND METHODS", keys: ["gdc_provenance", "method_versions", "jev_model_question_versions", "llm_provider_model_metadata", "research_only_notice"] },
];

export function DossierView({ dossierId }: { dossierId: string }) {
  const [data, setData] = useState<Dossier | null>(null);
  const [sha256, setSha256] = useState<string | null>(null);
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    apiWithMeta<Dossier>(`/api/dossiers/${dossierId}`, controller.signal)
      .then((result) => {
        setData(result.data);
        setSha256(result.sha256);
        setArtifactId(result.artifactId);
        setError(null);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setError("Dossier unavailable");
      });
    return () => controller.abort();
  }, [dossierId]);

  if (error) return <div className="api-warning">{error}</div>;
  if (!data) return <div className="panel empty">Loading dossier…</div>;
  const live = data.mode === "LIVE";
  const groups = GROUPS.map((group) =>
    live && group.title === "GENERATED FIXTURE HYPOTHESES"
      ? { ...group, title: "GENERATED HYPOTHESES — LLM TEXT, NOT EVIDENCE" }
      : group);
  const grouped = new Set(groups.flatMap((group) => group.keys));
  const leftovers = Object.keys(data.sections).filter((key) => !grouped.has(key));
  return (
    <article className="dossier">
      <header className={`warning-panel${live ? " live" : ""}`}>
        <span>{live ? "RESEARCH ONLY · NOT CLINICAL" : "RESEARCH ONLY · FAKE"}</span>
        <h1>{live ? "LIVE CANDIDATE DOSSIER" : "SYNTHETIC DEMONSTRATION"}</h1>
        <p>{data.warning}</p>
        <div className="row">
          <a className="button secondary" href={apiUrl(`/api/dossiers/${dossierId}?format=json`)}>Download authoritative JSON</a>
          <a className="button secondary" href={apiUrl(`/api/dossiers/${dossierId}?format=markdown`)}>Download derived Markdown</a>
        </div>
      </header>
      <section className="panel provenance" data-testid="dossier-provenance">
        <div className="eyebrow">PROVENANCE</div>
        <h2>Deterministic references</h2>
        <p className="muted mono">run {data.run_id.slice(0, 8)} · candidate {data.candidate_id.slice(0, 8)} · artifact {artifactId?.slice(0, 8) ?? "—"}</p>
        <p className="muted mono">sha256 {sha256 ?? "unavailable"}</p>
        <p className="muted">Evidence states: {data.evidence_state_ids.length ? data.evidence_state_ids.map((id) => id.slice(0, 8)).join(", ") : "none"}</p>
        <p className="muted">Hypotheses: {data.hypothesis_ids.length ? data.hypothesis_ids.map((id) => id.slice(0, 8)).join(", ") : "none"}</p>
      </section>
      {groups.map((group) => (
        <section className="dossier-group" key={group.title}>
          <div className="eyebrow">{group.title}</div>
          {group.keys.filter((key) => key in data.sections).map((key) => <SectionPanel key={key} name={key} section={data.sections[key]} />)}
        </section>
      ))}
      {leftovers.length > 0 && (
        <section className="dossier-group">
          <div className="eyebrow">OTHER SECTIONS</div>
          {leftovers.map((key) => <SectionPanel key={key} name={key} section={data.sections[key]} />)}
        </section>
      )}
    </article>
  );
}

function SectionPanel({ name, section }: { name: string; section: Section }) {
  return (
    <section className="panel">
      <div className="row spread"><h2>{formatLabel(name)}</h2><span className="availability">{section.availability}</span></div>
      <p>{section.narrative ?? section.reason}</p>
    </section>
  );
}
