import type {
  Experiment, ExperimentCreate, ExperimentDetail, ExperimentType, Health, ModelInfo,
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
  models: () => get<ModelInfo[]>("/models"),
  experimentTypes: () => get<ExperimentType[]>("/experiment-types"),
  experiments: (status?: string) => get<Experiment[]>(`/experiments${status ? `?status=${status}` : ""}`),
  experiment: (id: string) => get<ExperimentDetail>(`/experiments/${id}`),
  createExperiment: (body: ExperimentCreate) => post<Experiment>("/experiments", body),
  runExperiment: (id: string) => post<Experiment>(`/experiments/${id}/run`),
  cancelExperiment: (id: string) => post<Experiment>(`/experiments/${id}/cancel`),
  cloneExperiment: (id: string) => post<Experiment>(`/experiments/${id}/clone`),
};
