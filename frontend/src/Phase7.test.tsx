import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, vi } from "vitest";
import { App } from "./App";
import { Markdown } from "./components/Markdown";
import { AuthProvider } from "./hooks/useAuth";
import { setToken } from "./services/api";

const health = { status: "ok", version: "0.1.0", environment: "t", database: "ok", model_provider: "mock", model_name: "m", mock_mode: false, public_demo_mode: false, notice: null };
const user = { id: "u1", email: "ada@example.com", display_name: "Ada" };

type Handler = (url: string, init?: RequestInit) => { status: number; body: unknown };
function mockFetch(h: Handler) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => { const r = h(url, init); return { ok: r.status < 400, status: r.status, json: async () => r.body }; });
  vi.stubGlobal("fetch", fn);
  return fn;
}
function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AuthProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></AuthProvider></QueryClientProvider>);
}
beforeEach(() => { localStorage.clear(); setToken(null); });
afterEach(() => vi.restoreAllMocks());

test("markdown renders headings, tables, lists and quotes as elements", () => {
  const md = "# Title\n\n> **DEMO / MOCK DATA.** note\n\n## 1. Section\n\n| a | b |\n|---|---|\n| 1 | `x` |\n\n- item one\n- item **two**\n\n```json\n{\"k\": 1}\n```";
  render(<Markdown source={md} />);
  expect(screen.getByRole("heading", { level: 1, name: "Title" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: "1. Section" })).toBeInTheDocument();
  expect(screen.getByRole("table")).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
  expect(screen.getByText(/DEMO \/ MOCK DATA\./)).toBeInTheDocument();
  expect(screen.getByText(/"k": 1/)).toBeInTheDocument();
});

test("hostile text in a report cannot inject HTML or run script", () => {
  const evil = "# t\n\n<img src=x onerror=alert(1)> and <script>window.__pwned=1</script>\n\n| a |\n|---|\n| <b onmouseover=alert(2)>x</b> |";
  const { container } = render(<Markdown source={evil} />);
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("b")).toBeNull();
  expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  expect(container.textContent).toContain("<img src=x onerror=alert(1)>");  // shown as literal text
});

test("report page renders the generated report and offers download", async () => {
  mockFetch((u) => {
    if (u.endsWith("/health")) return { status: 200, body: health };
    if (u.endsWith("/reports/r1")) return { status: 200, body: { id: "r1", title: "Research report: arith", experiment_id: "e1", investigation_id: null, includes_demo_data: true, owned_by_me: false, created_at: "2026-10-04T10:00:00Z",
      content: "# Research report: arith\n\n## 14. Conclusion\n\nNo supported conclusion about the model's internal mechanisms is possible from black-box experiments." } };
    return { status: 200, body: [] };
  });
  renderAt("/reports/r1");
  expect(await screen.findByRole("heading", { name: "14. Conclusion" })).toBeInTheDocument();
  expect(screen.getByText(/internal mechanisms is possible/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Download Markdown" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Delete report" })).toBeNull();  // not the owner
});

test("notebook asks anonymous visitors to sign in and sends nothing private", async () => {
  const f = mockFetch((u) => (u.endsWith("/health") ? { status: 200, body: health } : { status: 200, body: [] }));
  renderAt("/notebook");
  expect(await screen.findByText(/Sign in to use the notebook/)).toBeInTheDocument();
  expect(f.mock.calls.some((c) => String(c[0]).includes("/investigations"))).toBe(false);
});

test("a conclusion saved without limitations shows the server's refusal", async () => {
  setToken("tok");
  const inv = { id: "i1", title: "Does form matter?", research_question: "Q?", hypothesis: "H", conclusion: "", limitations: "", experiments: [], hidden_experiments: 0, notes: [], created_at: "2026-10-04T10:00:00Z", updated_at: "2026-10-04T10:00:00Z" };
  mockFetch((u, init) => {
    if (u.endsWith("/health")) return { status: 200, body: health };
    if (u.endsWith("/auth/me")) return { status: 200, body: user };
    if (u.endsWith("/investigations/i1") && init?.method === "PATCH") return { status: 422, body: { detail: "State the limitations before recording a conclusion." } };
    if (u.endsWith("/investigations/i1")) return { status: 200, body: inv };
    return { status: 200, body: [] };
  });
  renderAt("/notebook/i1");
  fireEvent.change(await screen.findByLabelText(/^Conclusion/), { target: { value: "Form matters." } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("State the limitations before recording a conclusion."));
});

test("experiment page offers report and export actions once runs have finished", async () => {
  const counts = { total: 6, pending: 0, running: 0, succeeded: 6, failed: 0, cancelled: 0, passed: 5 };
  const exp = { id: "e1", name: "arith", research_question: "Q?", hypothesis: null, task_type: "t", status: "completed", model_slug: "m", model_version: "v", is_demo_data: false, is_public: false, owned_by_me: true, evaluator: "numeric_match", temperature: 0, max_tokens: 64, seed: 0, repetitions: 1, created_at: "2026-10-04T10:00:00Z", started_at: null, finished_at: null, error: null, counts, config: {}, environment: {}, software_version: "0.1.0", notice: null, runs: [] };
  mockFetch((u) => (u.endsWith("/health") ? { status: 200, body: health } : u.endsWith("/experiments/e1") ? { status: 200, body: exp } : { status: 200, body: [] }));
  renderAt("/experiments/e1");
  expect(await screen.findByRole("button", { name: "Generate research report" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Export JSON" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Export CSV" })).toBeInTheDocument();
});
