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

export type ProviderUsage = {
  gdc_requests: number;
  gdc_bytes: number;
  jev_calls: number;
  llm_calls: number;
  jev_input_tokens?: number | null;
  jev_output_tokens?: number | null;
  jev_cost?: number | null;
  llm_input_tokens?: number | null;
  llm_output_tokens?: number | null;
  llm_cost?: number | null;
};

export type ResearchRun = {
  run_id: string;
  mode: "FAKE";
  fixture_id: string;
  fixture_version: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "STOPPED";
  current_stage: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  last_sequence: number;
  worker_id: string;
  coverage: string;
  outcome_reason: string | null;
  selected_project_ids: string[];
  counts: RunCounts;
  provider_usage: ProviderUsage;
  stage_occurrences: Array<{ stage: string; type: string; sequence: number; candidate_id: string | null; iteration: number | null }>;
};

export type RunEvent = {
  event_id: string;
  run_id: string;
  sequence: number;
  timestamp: string;
  stage: string | null;
  type: string;
  level: string;
  message: string;
  data: Record<string, unknown>;
  candidate_id: string | null;
  iteration: number | null;
};

export type Envelope<T> = { items: T[]; next_cursor: string | null; has_more: boolean };
export type ChildRecord = Record<string, unknown>;

export type SystemStatus = {
  schema_version: number;
  phase: number;
  mode: string;
  providers: Record<string, boolean>;
  worker: { owner_id: string; heartbeat_at: string; version: string; fresh: boolean | null } | null;
  active_run_id: string | null;
  data: { directory: string; database_bytes: number; artifact_files: number };
  versions: { api: string; schema: number; worker: string | null };
  budget_defaults: { gdc_requests: number | null; gdc_bytes: number | null; reason: string };
  cursor: { present: boolean; reason: string };
  cache: { entries: number; reason: string };
};
