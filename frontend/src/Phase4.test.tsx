import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./hooks/useAuth";

const health = { status: "ok", version: "0.1.0", environment: "t", database: "ok", model_provider: "mock", model_name: "m", mock_mode: true, public_demo_mode: false, notice: "MOCK" };
const failure = { id: "f1", run_id: "r1", experiment_id: "e1", experiment_name: "arith", label: "representation_sensitivity", detector: "paired_discordance", status: "potential_anomaly", details: { block: "37x84#0", failed_group: "b_star_a" }, prompt: "84 * 37 = ?", response: "The answer is 3103.", expected_answer: "3108", is_demo_data: true, can_follow_up: true };
const explain = { failure, observed: "For the problem 37×84, the form 'b_star_a' was answered 'The answer is 3103.'", controlled_variables: ["temperature 0"], changed_variable: "The surface form of the prompt.",
  follow_ups: [{ experiment_id: "e2", name: "Follow-up: 37×84", status: "completed", summary: "The failing form failed in 5/6 follow-up runs." }],
  evidence: { level: "correlation", strength: "moderate", status: "reproduced", summary: "Reproduced: an association, not an identified cause." },
  possible_explanations: [{ text: "Less reliable in form b_star_a.", evidence_level: "hypothesis" }], alternative_explanations: [{ text: "Sampling variability.", evidence_level: "hypothesis" }],
  limitations: ["Black-box experiment: cannot show why inside the model."], demo_notice: "DEMO / MOCK DATA: the mock injects wrong answers." };

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

test("explain page walks observation to limitations with labelled evidence", async () => {
  route({ "/health": health, "/failures/f1/explain": explain });
  renderAt("/failures/f1");
  expect(await screen.findByText(/Observed behavior/)).toBeInTheDocument();
  for (const t of ["Controlled variables", "Changed variable", "Follow-up experiments", "Evidence", "Possible explanations", "Limitations"]) {
    expect(screen.getByText(new RegExp(t))).toBeInTheDocument();
  }
  expect(screen.getByText("Moderate")).toBeInTheDocument();
  expect(screen.getByText(/not an identified cause/)).toBeInTheDocument();
  expect(screen.getByText(/DEMO \/ MOCK DATA: the mock/)).toBeInTheDocument();
  expect(screen.getByText("Sampling variability.")).toBeInTheDocument();
});

test("failure list shows POTENTIAL ANOMALY, never 'failure', as the status", async () => {
  route({ "/health": health, "/failures": [failure] });
  renderAt("/failures");
  expect(await screen.findByText("POTENTIAL ANOMALY")).toBeInTheDocument();
  expect(screen.getAllByText("DEMO / MOCK").length).toBeGreaterThan(0);
});
