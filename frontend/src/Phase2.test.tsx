import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { App } from "./App";

const counts = { total: 6, pending: 0, running: 0, succeeded: 6, failed: 0, cancelled: 0, passed: 4 };
const exp = {
  id: "e1", name: "37x84 representations", research_question: "Does representation matter?", hypothesis: null,
  task_type: "arithmetic_representation", status: "completed", model_slug: "mock-deterministic-v1", model_version: "mock-1",
  is_demo_data: true, evaluator: "numeric_match", temperature: 0, max_tokens: 64, seed: 0, repetitions: 1,
  created_at: "2026-10-02T10:00:00Z", started_at: null, finished_at: null, error: null, counts,
};
const health = { status: "ok", version: "0.1.0", environment: "t", database: "ok", model_provider: "mock",
  model_name: "m", mock_mode: true, public_demo_mode: false, notice: "MOCK" };

function route(map: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const key = Object.keys(map).find((k) => url.endsWith(k));
    return key ? { ok: true, status: 200, json: async () => map[key] } : { ok: false, status: 404, json: async () => ({ detail: "nope" }) };
  }));
}
function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
}
afterEach(() => vi.restoreAllMocks());

test("experiments list shows status, demo tag and progress", async () => {
  route({ "/health": health, "/experiments": [exp], "/experiment-types": [] });
  renderAt("/experiments");
  expect(await screen.findByText("37x84 representations")).toBeInTheDocument();
  expect(screen.getAllByText("DEMO / MOCK").length).toBeGreaterThan(0);
  expect(screen.getByText(/6\/6 runs done/)).toBeInTheDocument();
});

test("detail shows evidence rows, evaluator label and the mock notice", async () => {
  const detail = { ...exp, config: {}, environment: { python: "3.12" }, software_version: "0.1.0",
    notice: "DEMO / MOCK DATA: produced by a deterministic mock model.",
    runs: [{ id: "r1", run_index: 0, variant_label: "37x84:a_x_b", variant_params: {}, status: "succeeded", attempt: 1, seed: 0,
      latency_ms: 2, prompt_tokens: 5, completion_tokens: 4, tokens_estimated: true, error: null, prompt: "What is 37 × 84?",
      expected_answer: "3108", response: "The answer is 3108.",
      evaluation: { kind: "deterministic", evaluator_name: "numeric_match", evaluator_version: "1", score: 1, passed: true, details: {} } }] };
  route({ "/health": health, "/experiments/e1": detail });
  renderAt("/experiments/e1");
  expect(await screen.findByText("The answer is 3108.")).toBeInTheDocument();
  expect(screen.getByText("numeric_match (deterministic)")).toBeInTheDocument();
  expect(screen.getByText(/produced by a deterministic mock model/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Clone experiment" })).toBeInTheDocument();
});

test("detail surfaces API errors", async () => {
  route({ "/health": health });
  renderAt("/experiments/missing");
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("nope"));
});

test("models page lists the active model", async () => {
  route({ "/health": health, "/models": [{ id: "m1", slug: "mock-deterministic-v1", display_name: "Mock (deterministic, not a real LLM)",
    provider: "mock", context_length: 4096, capabilities: {}, is_mock: true, versions: ["mock-1"], experiment_count: 1, configured: true }] });
  renderAt("/models");
  expect(await screen.findByText("active")).toBeInTheDocument();
  expect(screen.getByText(/1 experiment$/)).toBeInTheDocument();
});
