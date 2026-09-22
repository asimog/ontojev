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
  gdc_cache_hits: number;
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
  mode: "FAKE" | "LIVE";
  fixture_id: string | null;
  fixture_version: string | null;
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

export type Availability =
  | "OBSERVED"
  | "MISSING"
  | "NOT_EXAMINED"
  | "NOT_ACQUIRED"
  | "NOT_OBSERVED"
  | "UNAVAILABLE_ACCESS"
  | "UNAVAILABLE_SOURCE"
  | "INSUFFICIENT"
  | "INCOMPATIBLE"
  | "FAILED"
  | "PARTIAL"
  | "UNSUPPORTED_IN_V1";

export type Metric = {
  name: string;
  value: number | null;
  unit: string;
  availability: Availability;
  reason_code: string | null;
  observation_ref: string | null;
};

export type StatisticalStateSummary = {
  entity: { gene_id: string; gene_symbol: string };
  mode: "LIVE";
  mutation_availability: string;
  expression_availability: string;
  projects_with_mutation_observation: number;
  projects_with_expression_observation: number;
  affected_case_total: Metric;
  top_project_share: Metric;
  coverage_imbalance: boolean;
  completeness: string;
  artifact_id: string;
  artifact_sha256: string;
};

export type JevProjectionRecord = {
  projection_id: string;
  state_id: string;
  projection_version: string;
  source_state_hash: string;
  projection_hash: string;
  artifact_id: string;
  fields_json: string;
  created_at: string;
};

export type WideRankingEntry = {
  state_id: string;
  state_hash: string;
  gene_symbol: string;
  rank: number;
  evaluation_id?: string;
  dimensions: Record<string, unknown>;
};

export type WideRanking = {
  policy_version: string;
  kind: "BASELINE" | "JEV";
  ordering: string;
  entries: WideRankingEntry[];
  admitted_state_ids: string[];
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
  budget_defaults: {
    gdc_requests: number | null;
    gdc_bytes: number | null;
    per_response_bytes?: number;
    max_case_ids?: number;
    max_gene_ids?: number;
    reason: string;
  };
  cursor: { present: boolean; reason: string };
  cache: { entries: number; bytes?: number; jev_entries?: number; reason: string | null };
};
