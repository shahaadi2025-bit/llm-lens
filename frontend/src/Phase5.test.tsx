import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./hooks/useAuth";

const health = { status: "ok", version: "0.1.0", environment: "t", database: "ok", model_provider: "mock", model_name: "m", mock_mode: true, public_demo_mode: false, notice: "MOCK" };
const model = { id: "m1", slug: "mock-deterministic-v1", display_name: "Mock v1", provider: "mock", context_length: 4096, capabilities: {}, is_mock: true, versions: ["mock-1"], experiment_count: 1, configured: true };
const dim = (code: string, name: string, measured: boolean) => ({ code, name, measured, value: measured ? 0.8 : null, ci_low: measured ? 0.7 : null, ci_high: measured ? 0.9 : null, n: measured ? 72 : 0, n_experiments: measured ? 1 : 0, method: measured ? "pooled wilson-95" : null, metrics: measured ? [{ metric_id: "x1", experiment_id: "e1", experiment_name: "arith", version: "mock-1", value: 0.8, ci_low: 0.7, ci_high: 0.9, n: 72 }] : [], how_measured: measured ? "Accuracy on multiplication." : "No experiment type for this dimension is implemented yet." });
const fp = { model_id: "m1", model_slug: model.slug, display_name: "Mock v1", version: null, includes_demo_data: true, dimensions: [dim("R", "Reasoning", false), dim("M", "Mathematics", true)], notes: ["1 of 8 dimensions measured; unmeasured dimensions are shown as such, not as zero."] };
const diff = { metric: "accuracy", dimension: "M", a_value: 0.85, a_n: 72, b_value: 0.65, b_n: 72, difference: -0.2, diff_ci_low: -0.34, diff_ci_high: -0.05, cohens_h: -0.45, mcnemar_p: 0.01, paired_only_a: 15, paired_only_b: 3, statement: "accuracy (M): version B scored 20.0 percentage points lower. This describes outcomes on these experiments; it does not say what changed between the versions." };

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

test("fingerprint shows unmeasured dimensions as 'not measured', never as zero, and lists evidence", async () => {
  route({ "/health": health, "/models": [model], "/fingerprints/m1": fp });
  renderAt("/fingerprint");
  expect(await screen.findByText("not measured")).toBeInTheDocument();
  expect(screen.getByText(/dimensions measured; unmeasured dimensions are shown as such/)).toBeInTheDocument();
  expect(screen.getAllByText(/DEMO \/ MOCK DATA/).length).toBeGreaterThan(1); // global banner + this page's own warning
  expect(screen.getByText(/no single AI score/)).toBeInTheDocument();
  expect(screen.getByText(/Experiments behind this \(1\)/)).toBeInTheDocument();
});

test("compare shows the difference interval and a statement that avoids causes", async () => {
  const versions = [{ id: "v1", model_id: "m1", model_slug: "mock-deterministic-v1", display_name: "Mock v1", version_label: "mock-1", is_mock: true, experiment_count: 1 },
    { id: "v2", model_id: "m2", model_slug: "mock-deterministic-v2", display_name: "Mock v2", version_label: "mock-2", is_mock: true, experiment_count: 1 }];
  const res = { a_label: "a", b_label: "b", includes_demo_data: true, comparable: true, matched: [{ task_type: "t", a: { id: "e1", name: "A" }, b: { id: "e2", name: "B" } }], unmatched_a: [], unmatched_b: [], differences: [diff], latency_ms: {}, notes: ["Only experiments with identical design are compared."] };
  route({ "/health": health, "/model-versions": versions, "/compare?a=v1&b=v2": res });
  renderAt("/compare");
  const selects = await screen.findAllByRole("combobox");
  fireEvent.change(selects[0], { target: { value: "v1" } });
  fireEvent.change(selects[1], { target: { value: "v2" } });
  fireEvent.click(screen.getByRole("button", { name: "Compare" }));
  expect(await screen.findByText(/-20\.0 pts \[-34\.0, -5\.0\]/)).toBeInTheDocument();
  expect(screen.getByText(/does not say what changed between the versions/)).toBeInTheDocument();
  expect(screen.getAllByText(/DEMO \/ MOCK DATA/).length).toBeGreaterThan(1);
});

test("failures page lists clusters with an honest description", async () => {
  const cluster = { id: "c1", label: "Numeric near miss (within 1%): mostly form 'b_star_a' (60%)", size: 5, method: "kmeans(k=2, silhouette=0.4)", embedding_model: "tfidf-char_wb-2-4", error_types: { numeric_near_miss: 5 }, forms: { b_star_a: 3 }, includes_demo_data: true, note: "n" };
  route({ "/health": health, "/failures": [], "/failure-clusters": [cluster] });
  renderAt("/failures");
  expect(await screen.findByText(/mostly form 'b_star_a'/)).toBeInTheDocument();
  expect(screen.getByText(/describe the outputs, not their cause/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Recompute clusters" })).toBeInTheDocument();
});
