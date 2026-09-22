"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BudgetSummary } from "@/components/BudgetSummary";
import { DeterministicStatePanel } from "@/components/DeterministicStatePanel";
import { EventFeed } from "@/components/EventFeed";
import { JudgmentVector } from "@/components/JudgmentVector";
import { StatusBanner } from "@/components/StatusBanner";
import { WideJudgment, type LiveEvaluationVector } from "@/components/WideJudgment";
import { WideRankingPanel } from "@/components/WideRanking";
import { api } from "@/lib/api";
import { formatDuration, formatTime } from "@/lib/format";
import type { ChildRecord, Envelope, ResearchRun, RunEvent, WideRanking } from "@/lib/types";

const MAX_BACKOFF_MS = 30_000;

type DetailData = {
  run: ResearchRun;
  candidates: ChildRecord[];
  states: ChildRecord[];
  evaluations: ChildRecord[];
  projections: ChildRecord[];
  hypotheses: ChildRecord[];
  dossiers: ChildRecord[];
  rankings: { baseline: WideRanking | null; jev: WideRanking | null };
};

function isLiveVector(vector: Record<string, unknown>): vector is LiveEvaluationVector {
  return vector.mode === "LIVE" && typeof vector.answers === "object" && vector.answers !== null;
}

export function RunDetail({ runId }: { runId: string }) {
  const [detail, setDetail] = useState<DetailData | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [candidateFilter, setCandidateFilter] = useState("all");
  const [iterationFilter, setIterationFilter] = useState("all");
  const cursor = useRef(0);
  const failures = useRef(0);

  const poll = useCallback(async (signal: AbortSignal) => {
    try {
      const [run, candidates, states, evaluations, projections, hypotheses, dossiers, rankings] = await Promise.all([
        api<ResearchRun>(`/api/runs/${runId}`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/candidates`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/states`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/evaluations`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/projections`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/hypotheses`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/dossiers`, signal),
        api<{ baseline: WideRanking | null; jev: WideRanking | null }>(`/api/runs/${runId}/rankings`, signal),
      ]);
      let hasMore = true;
      while (hasMore) {
        const page = await api<{ items: RunEvent[]; next_after_sequence: number; has_more: boolean }>(`/api/runs/${runId}/events?after_sequence=${cursor.current}&limit=20`, signal);
        if (page.items.length) {
          setEvents((current) => [...new Map([...current, ...page.items].map((item) => [item.event_id, item])).values()]
            .sort((a, b) => a.sequence - b.sequence));
        }
        cursor.current = page.next_after_sequence;
        hasMore = page.has_more;
      }
      setDetail({ run, candidates: candidates.items, states: states.items, evaluations: evaluations.items, projections: projections.items, hypotheses: hypotheses.items, dossiers: dossiers.items, rankings });
      failures.current = 0;
      setError(null);
      setUpdatedAt(new Date().toISOString());
      return run.status;
    } catch (reason) {
      if ((reason as Error).name !== "AbortError") {
        failures.current += 1;
        setError("API unavailable");
      }
      return detail?.run.status;
    }
  }, [detail?.run.status, runId]);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    let inFlight = false;
    const loop = async () => {
      if (inFlight) return;
      inFlight = true;
      let status: string | undefined;
      try {
        if (document.visibilityState === "visible") status = await poll(controller.signal);
      } finally {
        inFlight = false;
      }
      if (stopped || ["COMPLETED", "FAILED", "STOPPED"].includes(status ?? "")) return;
      const backoff = Math.min(2000 * 2 ** failures.current, MAX_BACKOFF_MS);
      timer = setTimeout(loop, document.visibilityState === "visible" ? backoff : 2000);
    };
    const onVisibility = () => {
      if (document.visibilityState !== "visible" || stopped) return;
      clearTimeout(timer);
      void loop();
    };
    document.addEventListener("visibilitychange", onVisibility);
    void loop();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); document.removeEventListener("visibilitychange", onVisibility); };
  }, [poll]);

  const visibleEvents = useMemo(() => events.filter((event) =>
    (candidateFilter === "all" || event.candidate_id === candidateFilter) &&
    (iterationFilter === "all" || String(event.iteration ?? 0) === iterationFilter),
  ), [events, candidateFilter, iterationFilter]);

  if (!detail) return <><StatusBanner error={error} updatedAt={updatedAt} /><div className="panel empty">Loading durable run…</div></>;
  const run = detail.run;
  const live = run.mode === "LIVE";
  const fixtureVectors = detail.evaluations
    .map((entry) => entry.vector as Record<string, unknown>)
    .filter((vector) => vector && !isLiveVector(vector));
  const statesById = new Map(detail.states.map((state) => [String(state.state_id), state]));
  const liveVectors = detail.evaluations.flatMap((evaluation) => {
    const vector = evaluation.vector as Record<string, unknown> | null;
    if (!vector || !isLiveVector(vector)) return [];
    const stateId = String(evaluation.input_ref_id ?? "unknown");
    const state = statesById.get(stateId);
    const geneSymbol = String((state?.entity as Record<string, unknown> | undefined)?.gene_symbol ?? "Unknown gene");
    return [{ vector, stateId, geneSymbol }];
  });
  return (
    <>
      <StatusBanner error={error} updatedAt={updatedAt} />
      <header className="detail-hero panel">
        <div>
          <span className={`badge ${live ? "live" : "fake"}`}>{live ? "LIVE · OPEN GDC" : "FAKE · SYNTHETIC"}</span>
          <span className={`badge status ${run.status.toLowerCase()}`}>{run.status}</span>
        </div>
        <div className="eyebrow">RESEARCH RUN</div><h1>{run.current_stage ?? (live ? "Bounded open-access sweep" : "Bounded fixture run")}</h1>
        <p className="mono muted">{run.run_id}</p>
        <p className="muted mono">
          mode {run.mode}
          {live
            ? ` · ${(run.selected_project_ids ?? []).length} project(s) · coverage ${run.coverage}`
            : ` · fixture ${run.fixture_id} v${run.fixture_version} · schema v1`}
          {" "}· worker {run.worker_id.slice(0, 8)}
        </p>
        <p className="muted mono">created {formatTime(run.created_at)} · started {formatTime(run.started_at)} · ended {formatTime(run.ended_at)} · elapsed {formatDuration(run.started_at, run.ended_at)}</p>
        <div className="metrics">
          <Metric label={live ? "Projects examined" : "Projects simulated"} value={run.counts.projects_completed} />
          <Metric label="States generated" value={run.counts.states_generated} />
          <Metric label="States evaluated" value={run.counts.states_evaluated} />
          <Metric label="Wide candidates" value={run.counts.candidates_promoted} />
          <Metric label="Jev provider calls" value={run.provider_usage.jev_calls} />
          <Metric label="LLM calls" value={run.provider_usage.llm_calls} />
        </div>
      </header>
       <section className="panel"><div className="eyebrow">PIPELINE</div><div className="pipeline">{run.stage_occurrences.filter((item) => item.type === "STAGE_COMPLETED").map((item) => <span key={`${item.stage}-${item.sequence}`}>{item.stage}{item.candidate_id ? ` · c${item.candidate_id.slice(0, 4)}` : ""}{item.iteration ? ` · i${item.iteration}` : ""}</span>)}{run.current_stage && <span className="active">{run.current_stage} · live</span>}</div><p className="fine">Repeated stages are distinct per-candidate or per-iteration occurrences. Only admitted states become candidates; exclusions and reasons remain in the Jev ranking.</p></section>
      <BudgetSummary run={run} />
      {live ? (
        <>
          <DeterministicStatePanel states={detail.states} />
          {detail.candidates.length > 0 && (
            <section className="panel">
              <div className="eyebrow violet">WIDE ADMISSION — JEV POLICY, BOUNDED</div>
              <h2>{detail.candidates.length} candidate(s) admitted for later deep analysis</h2>
              <div className="candidate-grid">
                {detail.candidates.map((item) => {
                  const summary = item.summary as Record<string, unknown>;
                  const dimensions = (summary.dimensions ?? {}) as Record<string, unknown>;
                  return (
                    <article className="mini-card" key={String(item.candidate_id)}>
                      <span className="badge">{String(item.status)}</span>
                      <h3>{String((item.entity as Record<string, unknown>)?.gene_symbol ?? "Candidate")}</h3>
                      <p>{String(summary.promotion_reason ?? "")}</p>
                      <p className="fine mono">quality {formatDimensionValue(dimensions.evidence_quality_adequate)} · warrants {formatDimensionValue(dimensions.warrants_deeper_investigation)} · uncertainty {formatDimensionValue(dimensions.unresolved_uncertainty_material)} · coverage {formatDimensionValue(dimensions.signal_explained_by_coverage)} · {String(dimensions.dominant_limitation ?? "n/a")}</p>
                    </article>
                  );
                })}
              </div>
              <p className="fine">Deep analysis, evidence states and follow-ups are Phase 4 and are not implemented; these candidates stop here.</p>
            </section>
          )}
          <WideRankingPanel baseline={detail.rankings.baseline} jev={detail.rankings.jev} />
          {detail.projections.length > 0 && (
            <section className="panel">
              <div className="eyebrow">JEV PROJECTIONS</div>
              <h2>{detail.projections.length} versioned projection(s)</h2>
              <p className="fine">Projections contain only deterministic state fields; the projection hash is the inference identity.</p>
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Projection</th><th>Version</th><th>Source state hash</th><th>Projection hash</th></tr></thead>
                  <tbody>
                    {detail.projections.map((row) => (
                      <tr key={String(row.projection_id)}>
                        <td className="mono">{String(row.projection_id).slice(0, 8)}</td>
                        <td>{String(row.projection_version)}</td>
                        <td className="mono">{String(row.source_state_hash).slice(0, 12)}…</td>
                        <td className="mono">{String(row.projection_hash).slice(0, 12)}…</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {liveVectors.map(({ vector, stateId, geneSymbol }) => (
            <WideJudgment key={vector.evaluation_id} vector={vector} stateId={stateId} geneSymbol={geneSymbol} />
          ))}
        </>
      ) : (
        <>
          <section className="panel"><div className="eyebrow amber">DETERMINISTIC / FIXTURE EVIDENCE</div><h2>{detail.states.length} synthetic statistical states</h2><div className="candidate-grid">{detail.candidates.map((item) => <article className="mini-card" key={String(item.candidate_id)}><span className="badge">{String(item.status)}</span><h3>{String((item.entity as Record<string, unknown>)?.gene_symbol ?? "Synthetic candidate")}</h3><p>{String((item.summary as Record<string, unknown>)?.promotion_reason ?? "Fixture branch")}</p></article>)}</div></section>
          {fixtureVectors.length > 0 && (
            <div data-testid="fixture-judgment-vector">
              {fixtureVectors.map((vector, index) => <JudgmentVector key={String(detail.evaluations[index]?.evaluation_id)} vector={vector as Parameters<typeof JudgmentVector>[0]["vector"]} />)}
            </div>
          )}
          <section className="panel hypotheses"><div className="eyebrow coral">GENERATED FIXTURE HYPOTHESES</div><h2>Competing explanations, not measured evidence</h2>{detail.hypotheses.map((record) => { const hypothesis = record.hypothesis as Record<string, unknown>; return <article className="hypothesis" key={String(record.hypothesis_id)}><span>{String(hypothesis.label)}</span><h3>{String(hypothesis.statement)}</h3><p>{String(hypothesis.proposed_mechanism)}</p></article>; })}</section>
          <section className="panel"><div className="eyebrow">REGISTERED FOLLOW-UP</div><p>Baseline and revised EvidenceState IDs are preserved in the canonical events below. The deterministic fixture action changes the descriptive value without overwriting baseline evidence.</p></section>
        </>
      )}
      {detail.dossiers.length > 0 && <section className="panel callout"><div><div className="eyebrow">DOSSIER READY</div><h2>{live ? "Research dossier" : "Synthetic research dossier"}</h2></div><Link className="button" href={`/dossiers/${String(detail.dossiers[0].dossier_id)}`}>Open dossier</Link></section>}
      <section className="panel filter-row">
        <label>Candidate <select value={candidateFilter} onChange={(event) => setCandidateFilter(event.target.value)}><option value="all">All candidates</option>{detail.candidates.map((item) => <option key={String(item.candidate_id)} value={String(item.candidate_id)}>{String((item.entity as Record<string, unknown>)?.gene_symbol ?? String(item.candidate_id).slice(0, 8))}</option>)}</select></label>
        <label>Iteration <select value={iterationFilter} onChange={(event) => setIterationFilter(event.target.value)}><option value="all">All iterations</option><option value="0">0</option><option value="1">1</option><option value="2">2</option></select></label>
        <span className="muted">showing {visibleEvents.length} of {events.length} events</span>
      </section>
      <EventFeed events={visibleEvents} />
    </>
  );
}

function Metric({ label, value }: { label: string; value: number }) { return <div><strong>{value}</strong><span>{label}</span></div>; }

function formatDimensionValue(value: unknown): string {
  return typeof value === "number" ? value.toFixed(2) : "n/a";
}
