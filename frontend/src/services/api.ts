import type {
  Analysis, Cluster, ClusterDetail, Compare, Dashboard, Fingerprint, ModelVersion, Experiment, Explain, Failure, Lineage, ExperimentCreate, ExperimentDetail, ExperimentType, Health, Metric,
  MetricEvidence, ModelInfo,
} from "../types/api";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { headers: { Accept: "application/json" } });
  } catch {
    throw new ApiError("Cannot reach the LLM Lens backend. Is it running?");
  }
  return parse<T>(res);
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch { /* keep generic message */ }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the LLM Lens backend. Is it running?");
  }
  return parse<T>(res);
}

export const api = {
  health: () => get<Health>("/health"),
  dashboard: () => get<Dashboard>("/dashboard"),
  clusters: () => get<Cluster[]>("/failure-clusters"),
  cluster: (id: string) => get<ClusterDetail>(`/failure-clusters/${id}`),
  recomputeClusters: () => post<Cluster[]>("/failure-clusters/recompute"),
  fingerprint: (modelId: string) => get<Fingerprint>(`/fingerprints/${modelId}`),
  modelVersions: () => get<ModelVersion[]>("/model-versions"),
  compare: (a: string, b: string) => get<Compare>(`/compare?a=${a}&b=${b}`),
  failures: (experimentId?: string) => get<Failure[]>(`/failures${experimentId ? `?experiment_id=${experimentId}` : ""}`),
  explain: (failureId: string) => get<Explain>(`/failures/${failureId}/explain`),
  lineage: (experimentId: string) => get<Lineage>(`/experiments/${experimentId}/lineage`),
  followUp: (experimentId: string, failureId: string) =>
    post<Experiment>(`/experiments/${experimentId}/follow-up`, { failure_id: failureId }),
  metrics: (id: string) => get<Metric[]>(`/experiments/${id}/metrics`),
  analysis: (id: string) => get<Analysis>(`/experiments/${id}/analysis`),
  evidence: (metricId: string) => get<MetricEvidence>(`/metrics/${metricId}/evidence`),
  models: () => get<ModelInfo[]>("/models"),
  experimentTypes: () => get<ExperimentType[]>("/experiment-types"),
  experiments: (status?: string) => get<Experiment[]>(`/experiments${status ? `?status=${status}` : ""}`),
  experiment: (id: string) => get<ExperimentDetail>(`/experiments/${id}`),
  createExperiment: (body: ExperimentCreate) => post<Experiment>("/experiments", body),
  runExperiment: (id: string) => post<Experiment>(`/experiments/${id}/run`),
  cancelExperiment: (id: string) => post<Experiment>(`/experiments/${id}/cancel`),
  cloneExperiment: (id: string) => post<Experiment>(`/experiments/${id}/clone`),
};
