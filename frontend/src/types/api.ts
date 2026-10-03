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
  name: string; task_type: string; seed: number; repetitions: number; research_question?: string; model_slug?: string;
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

export interface Failure {
  id: string; run_id: string; experiment_id: string; experiment_name: string; label: string; detector: string;
  status: "potential_anomaly" | "reproduced" | "not_reproduced" | "dismissed"; details: Record<string, unknown>;
  prompt: string; response: string | null; expected_answer: string | null; is_demo_data: boolean; can_follow_up: boolean;
}
export interface ExplainStep { text: string; evidence_level: string | null; }
export interface Explain {
  failure: Failure; observed: string; controlled_variables: string[]; changed_variable: string;
  follow_ups: { experiment_id: string; name: string; status: string; summary: string | null }[];
  evidence: { level: string; strength: string; status: string; summary: string };
  possible_explanations: ExplainStep[]; alternative_explanations: ExplainStep[]; limitations: string[];
  demo_notice: string | null;
}
export interface Lineage {
  nodes: { id: string; name: string; status: string; is_current: boolean; is_demo_data: boolean; anomalies: number }[];
  edges: { parent: string; child: string; relation: string; trigger_run_id: string | null; note: string | null }[];
}

export interface Cluster {
  id: string; label: string; size: number; method: string; embedding_model: string | null;
  error_types: Record<string, number>; forms: Record<string, number>; includes_demo_data: boolean; note: string;
}
export interface ClusterDetail extends Cluster { members: Failure[]; }
export interface DimensionMetric {
  metric_id: string; experiment_id: string; experiment_name: string; version: string; value: number;
  ci_low: number | null; ci_high: number | null; n: number;
}
export interface Dimension {
  code: string; name: string; measured: boolean; value: number | null; ci_low: number | null; ci_high: number | null;
  n: number; n_experiments: number; method: string | null; metrics: DimensionMetric[]; how_measured: string;
}
export interface Fingerprint {
  model_id: string; model_slug: string; display_name: string; version: string | null; includes_demo_data: boolean;
  dimensions: Dimension[]; notes: string[];
}
export interface ModelVersion {
  id: string; model_id: string; model_slug: string; display_name: string; version_label: string; is_mock: boolean;
  experiment_count: number;
}
export interface Diff {
  metric: string; dimension: string | null; a_value: number; a_n: number; b_value: number; b_n: number; difference: number;
  diff_ci_low: number; diff_ci_high: number; cohens_h: number; mcnemar_p: number | null; paired_only_a: number | null;
  paired_only_b: number | null; statement: string;
}
export interface Compare {
  a_label: string; b_label: string; includes_demo_data: boolean; comparable: boolean;
  matched: { task_type: string; a: { id: string; name: string }; b: { id: string; name: string } }[];
  unmatched_a: { id: string; name: string }[]; unmatched_b: { id: string; name: string }[];
  differences: Diff[]; latency_ms: Record<string, number | null>; notes: string[];
}
