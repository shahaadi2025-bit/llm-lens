import type {
  Analysis, Cluster, ClusterDetail, Compare, Dashboard, Fingerprint, ModelVersion, Experiment, Explain, Failure, Lineage, ExperimentCreate, ExperimentDetail, ExperimentType, Health, Metric,
  MetricEvidence, ModelInfo, SavedConfig, TokenResponse, User,
} from "../types/api";

const TOKEN_KEY = "lens_token";
let token: string | null = typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;

/** The token is the user's own session credential. It is never logged and lives only in this tab's storage. */
export function setToken(t: string | null) {
  token = t;
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}
export const getToken = () => token;
const authHeader = (): Record<string, string> => (token ? { Authorization: `Bearer ${token}` } : {});

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function get<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { headers: { Accept: "application/json", ...authHeader() } });
  } catch {
    throw new ApiError("Cannot reach the LLM Lens backend. Is it running?");
  }
  return parse<T>(res);
}

async function parse<T>(res: Response): Promise<T> {
  if (res.status === 401 && token) {  // expired or revoked: drop it so the UI falls back to signed-out
    setToken(null);
    window.dispatchEvent(new Event("lens-auth-changed"));
  }
  if (res.status === 204) return undefined as T;
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

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method, headers: { "Content-Type": "application/json", Accept: "application/json", ...authHeader() },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the LLM Lens backend. Is it running?");
  }
  return parse<T>(res);
}
const post = <T,>(path: string, body?: unknown) => send<T>("POST", path, body);

export const api = {
  health: () => get<Health>("/health"),
  register: (email: string, password: string, display_name: string) =>
    post<TokenResponse>("/auth/register", { email, password, display_name }),
  login: (email: string, password: string) => post<TokenResponse>("/auth/login", { email, password }),
  me: () => get<User>("/auth/me"),
  setVisibility: (id: string, is_public: boolean) => send<Experiment>("PATCH", `/experiments/${id}`, { is_public }),
  configs: () => get<SavedConfig[]>("/configs"),
  saveConfig: (c: Omit<SavedConfig, "id" | "created_at" | "is_public">) => post<SavedConfig>("/configs", c),
  deleteConfig: (id: string) => send<void>("DELETE", `/configs/${id}`),
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
