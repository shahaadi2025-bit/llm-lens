export interface Health {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  database: "ok" | "unreachable";
  model_provider: string;
  model_name: string;
  mock_mode: boolean;
  public_demo_mode: boolean;
  notice: string | null;
}

export interface RunCounts {
  total: number; pending: number; running: number; succeeded: number; failed: number; cancelled: number; passed: number;
}
export interface Experiment {
  id: string; name: string; research_question: string; hypothesis: string | null; task_type: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled"; model_slug: string; model_version: string;
  is_demo_data: boolean; evaluator: string; temperature: number; max_tokens: number; seed: number;
  repetitions: number; created_at: string; started_at: string | null; finished_at: string | null;
  error: string | null; counts: RunCounts;
}
export interface Evaluation {
  kind: string; evaluator_name: string; evaluator_version: string; score: number; passed: boolean | null;
  details: Record<string, unknown>;
}
export interface Run {
  id: string; run_index: number; variant_label: string; variant_params: Record<string, unknown>; status: string;
  attempt: number; seed: number; latency_ms: number | null; prompt_tokens: number | null;
  completion_tokens: number | null; tokens_estimated: boolean; error: string | null; prompt: string;
  expected_answer: string | null; response: string | null; evaluation: Evaluation | null;
}
export interface ExperimentDetail extends Experiment {
  config: Record<string, unknown>; environment: Record<string, unknown>; software_version: string;
  runs: Run[]; notice: string | null;
}
export interface ExperimentType {
  task_type: string; title: string; research_question: string; description: string;
  default_evaluator: string; default_config: Record<string, unknown>;
}
export interface ModelInfo {
  id: string; slug: string; display_name: string; provider: string; context_length: number;
  capabilities: Record<string, unknown>; is_mock: boolean; versions: string[]; experiment_count: number;
  configured: boolean;
}
export interface ExperimentCreate {
  name: string; task_type: string; seed: number; repetitions: number; research_question?: string;
}

export interface Metric {
  id: string; experiment_id: string; name: string; dimension: string | null; value: number;
  ci_low: number | null; ci_high: number | null; ci_level: number; n: number; method: string;
  evidence_runs: number; is_demo_data: boolean;
}
export interface MetricEvidence { metric: Metric; runs: Run[]; }
export interface GroupStat { group: string; accuracy: number; ci_low: number; ci_high: number; n: number; }
export interface Statement { text: string; evidence_level: string; }
export interface Analysis {
  experiment_id: string; is_demo_data: boolean; method: string; groups: GroupStat[]; n_blocks: number;
  cochran_q: number | null; cochran_df: number | null; cochran_p: number | null; best: string | null;
  worst: string | null; spread: number | null; cohens_h: number | null; statements: Statement[];
  limitations: string[];
}
export interface Dashboard {
  experiments_total: number; experiments_completed: number; models_tested: number; potential_anomalies: number;
  failure_clusters: number; recent: Experiment[]; includes_demo_data: boolean; notes: string[];
}
