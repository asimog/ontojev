"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { EventFeed } from "@/components/EventFeed";
import { JudgmentVector } from "@/components/JudgmentVector";
import { StatusBanner } from "@/components/StatusBanner";
import { api } from "@/lib/api";
import type { ChildRecord, Envelope, ResearchRun, RunEvent } from "@/lib/types";

type DetailData = {
  run: ResearchRun;
  candidates: ChildRecord[];
  states: ChildRecord[];
  evaluations: ChildRecord[];
  hypotheses: ChildRecord[];
  dossiers: ChildRecord[];
};

export function RunDetail({ runId }: { runId: string }) {
  const [detail, setDetail] = useState<DetailData | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const cursor = useRef(0);

  const poll = useCallback(async (signal: AbortSignal) => {
    try {
      const [run, candidates, states, evaluations, hypotheses, dossiers] = await Promise.all([
        api<ResearchRun>(`/api/runs/${runId}`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/candidates`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/states`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/evaluations`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/hypotheses`, signal),
        api<Envelope<ChildRecord>>(`/api/runs/${runId}/dossiers`, signal),
      ]);
      let hasMore = true;
      const incoming: RunEvent[] = [];
      while (hasMore) {
        const page = await api<{ items: RunEvent[]; next_after_sequence: number; has_more: boolean }>(`/api/runs/${runId}/events?after_sequence=${cursor.current}&limit=20`, signal);
        incoming.push(...page.items);
        cursor.current = page.next_after_sequence;
        hasMore = page.has_more;
      }
      if (incoming.length) setEvents((current) => [...new Map([...current, ...incoming].map((item) => [item.event_id, item])).values()].sort((a, b) => a.sequence - b.sequence));
      setDetail({ run, candidates: candidates.items, states: states.items, evaluations: evaluations.items, hypotheses: hypotheses.items, dossiers: dossiers.items });
      setError(null);
      setUpdatedAt(new Date().toISOString());
      return run.status;
    } catch (reason) {
      if ((reason as Error).name !== "AbortError") setError("API unavailable");
      return detail?.run.status;
    }
  }, [detail?.run.status, runId]);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let stopped = false;
    const loop = async () => {
      const status = await poll(controller.signal);
      if (!stopped && !["COMPLETED", "FAILED", "STOPPED"].includes(status ?? "")) timer = setTimeout(loop, 2000);
    };
    void loop();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [poll]);

  if (!detail) return <><StatusBanner error={error} updatedAt={updatedAt} /><div className="panel empty">Loading durable run…</div></>;
  const run = detail.run;
  const vectors = detail.evaluations.map((entry) => entry.vector as Record<string, unknown>).filter(Boolean);
  return (
    <>
      <StatusBanner error={error} updatedAt={updatedAt} />
      <header className="detail-hero panel">
        <div><span className="badge fake">FAKE · SYNTHETIC</span><span className={`badge status ${run.status.toLowerCase()}`}>{run.status}</span></div>
        <div className="eyebrow">RESEARCH RUN</div><h1>{run.current_stage ?? "Bounded fixture run"}</h1>
        <p className="mono muted">{run.run_id}</p>
        <div className="metrics"><Metric label="Projects simulated" value={run.counts.projects_completed} /><Metric label="States generated" value={run.counts.states_generated} /><Metric label="States evaluated" value={run.counts.states_evaluated} /><Metric label="Deep candidates" value={run.counts.candidates_promoted} /><Metric label="Jev calls" value={run.provider_usage.jev_calls} /><Metric label="LLM calls" value={run.provider_usage.llm_calls} /></div>
      </header>
      <section className="panel"><div className="eyebrow">PIPELINE</div><div className="pipeline">{run.stage_occurrences.filter((item) => item.type === "STAGE_COMPLETED").map((item) => <span key={`${item.stage}-${item.sequence}`}>{item.stage}</span>)}{run.current_stage && <span className="active">{run.current_stage} · live</span>}</div></section>
      <section className="panel"><div className="eyebrow amber">DETERMINISTIC / FIXTURE EVIDENCE</div><h2>{detail.states.length} synthetic statistical states</h2><div className="candidate-grid">{detail.candidates.map((item) => <article className="mini-card" key={String(item.candidate_id)}><span className="badge">{String(item.status)}</span><h3>{String((item.entity as Record<string, unknown>)?.gene_symbol ?? "Synthetic candidate")}</h3><p>{String((item.summary as Record<string, unknown>)?.promotion_reason ?? "Fixture branch")}</p></article>)}</div></section>
      {vectors.map((vector, index) => <JudgmentVector key={String(detail.evaluations[index]?.evaluation_id)} vector={vector as Parameters<typeof JudgmentVector>[0]["vector"]} />)}
      <section className="panel hypotheses"><div className="eyebrow coral">GENERATED FIXTURE HYPOTHESES</div><h2>Competing explanations, not measured evidence</h2>{detail.hypotheses.map((record) => { const hypothesis = record.hypothesis as Record<string, unknown>; return <article className="hypothesis" key={String(record.hypothesis_id)}><span>{String(hypothesis.label)}</span><h3>{String(hypothesis.statement)}</h3><p>{String(hypothesis.proposed_mechanism)}</p></article>; })}</section>
      <section className="panel"><div className="eyebrow">REGISTERED FOLLOW-UP</div><p>Baseline and revised EvidenceState IDs are preserved in the canonical events below. The deterministic fixture action changes the descriptive value without overwriting baseline evidence.</p></section>
      {detail.dossiers.length > 0 && <section className="panel callout"><div><div className="eyebrow">DOSSIER READY</div><h2>Synthetic research dossier</h2></div><Link className="button" href={`/dossiers/${String(detail.dossiers[0].dossier_id)}`}>Open dossier</Link></section>}
      <EventFeed events={events} />
    </>
  );
}

function Metric({ label, value }: { label: string; value: number }) { return <div><strong>{value}</strong><span>{label}</span></div>; }

