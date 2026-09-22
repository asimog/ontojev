export type RunCounts = {
  projects_attempted: number;
  projects_completed: number;
  states_generated: number;
  states_valid: number;
  states_selected: number;
  states_evaluated: number;
  candidates_promoted: number;
  hypotheses_created: number;
  followups_started: number;
  dossiers_created: number;
  candidates_failed: number;
  candidates_deferred: number;
  jev_evaluations: number;
};

export type ResearchRun = {
  run_id: string;
  mode: "FAKE";
  fixture_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "STOPPED";
  current_stage: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  last_sequence: number;
  selected_project_ids: string[];
  counts: RunCounts;
  provider_usage: { gdc_requests: number; gdc_bytes: number; jev_calls: number; llm_calls: number };
  stage_occurrences: Array<{ stage: string; type: string; sequence: number }>;
};

export type RunEvent = {
  event_id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  stage: string | null;
  type: string;
  message: string;
  data: Record<string, unknown>;
  candidate_id: string | null;
};

export type Envelope<T> = { items: T[]; next_cursor: string | null; has_more: boolean };
export type ChildRecord = Record<string, unknown>;
