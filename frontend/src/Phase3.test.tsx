import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./hooks/useAuth";

const health = { status: "ok", version: "0.1.0", environment: "t", database: "ok", model_provider: "mock", model_name: "m", mock_mode: true, public_demo_mode: false, notice: "MOCK" };
const metric = { id: "m1", experiment_id: "e1", name: "accuracy", dimension: "M", value: 0.8333, ci_low: 0.7, ci_high: 0.91, ci_level: 0.95, n: 72, method: "wilson-95", evidence_runs: 72, is_demo_data: true };
const run = { id: "r1", run_index: 0, variant_label: "x", variant_params: {}, status: "succeeded", attempt: 1, seed: 0, latency_ms: 1, prompt_tokens: 1, completion_tokens: 1, tokens_estimated: true, error: null, prompt: "What is 37 × 84?", expected_answer: "3108", response: "The answer is 3108.", evaluation: { kind: "deterministic", evaluator_name: "numeric_match", evaluator_version: "1", score: 1, passed: true, details: {} } };
const counts = { total: 72, pending: 0, running: 0, succeeded: 72, failed: 0, cancelled: 0, passed: 60 };
const exp = { id: "e1", name: "arith", research_question: "Q?", hypothesis: null, task_type: "arithmetic_representation", status: "completed", model_slug: "m", model_version: "v", is_demo_data: true, evaluator: "numeric_match", temperature: 0, max_tokens: 64, seed: 0, repetitions: 1, created_at: "2026-10-03T10:00:00Z", started_at: null, finished_at: null, error: null, counts };
const analysis = { experiment_id: "e1", is_demo_data: true, method: "wilson-95 per form; cochran-q across forms", groups: [{ group: "a_x_b", accuracy: 0.9, ci_low: 0.6, ci_high: 0.98, n: 12 }], n_blocks: 12, cochran_q: 3, cochran_df: 5, cochran_p: 0.7, best: "a_x_b", worst: "a_x_b", spread: 0, cohens_h: 0, statements: [{ text: "No reliable difference between forms was detected. This is not evidence that no difference exists.", evidence_level: "observation" }], limitations: ["Black-box observation only."] };

function route(map: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(map).find((k) => url.endsWith(k));
    return key ? { ok: true, status: 200, json: async () => map[key] } : { ok: false, status: 404, json: async () => ({ detail: "nope" }) };
  }));
}
function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AuthProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></AuthProvider></QueryClientProvider>);
}
afterEach(() => vi.restoreAllMocks());

test("metric shows interval, n and method, and evidence can be expanded", async () => {
  route({ "/health": health, "/experiments/e1": { ...exp, config: {}, environment: {}, software_version: "0.1.0", notice: null, runs: [run] },
    "/experiments/e1/metrics": [metric], "/experiments/e1/analysis": analysis, "/metrics/m1/evidence": { metric, runs: [run] } });
  renderAt("/experiments/e1");
  expect(await screen.findByText(/\[70\.0%, 91\.0%\] · n=72/)).toBeInTheDocument();
  expect(screen.getByText(/method: wilson-95/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Show evidence \(72 runs\)/ }));
  expect(await screen.findByText(/runs behind this number/)).toBeInTheDocument();
  expect(screen.getByText("(numeric_match)")).toBeInTheDocument();
});

test("analysis labels each statement with its evidence level", async () => {
  route({ "/health": health, "/experiments/e1": { ...exp, config: {}, environment: {}, software_version: "0.1.0", notice: null, runs: [run] },
    "/experiments/e1/metrics": [metric], "/experiments/e1/analysis": analysis });
  renderAt("/experiments/e1");
  expect(await screen.findByText("observation")).toBeInTheDocument();
  expect(screen.getByText(/not evidence that no difference exists/)).toBeInTheDocument();
});

test("dashboard shows real counts, demo warning and honest zeros", async () => {
  route({ "/health": health, "/dashboard": { experiments_total: 3, experiments_completed: 2, models_tested: 1, potential_anomalies: 0, failure_clusters: 0, recent: [exp], includes_demo_data: true, notes: [] } });
  renderAt("/dashboard");
  expect(await screen.findByText("Experiments completed")).toBeInTheDocument();
  expect(screen.getByText("3 created")).toBeInTheDocument();
  expect(screen.getByText(/Distinct flagged runs, not confirmed failures/)).toBeInTheDocument();
  expect(screen.getAllByText(/DEMO \/ MOCK/).length).toBeGreaterThan(0);
});
