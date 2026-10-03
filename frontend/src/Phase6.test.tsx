import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, vi } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./hooks/useAuth";
import { getToken, setToken } from "./services/api";

const health = { status: "ok", version: "0.1.0", environment: "t", database: "ok", model_provider: "mock", model_name: "m", mock_mode: false, public_demo_mode: false, notice: null };
const user = { id: "u1", email: "ada@example.com", display_name: "Ada" };
const counts = { total: 6, pending: 0, running: 0, succeeded: 6, failed: 0, cancelled: 0, passed: 5 };
const exp = (over: object) => ({ id: "e1", name: "arith", research_question: "Q?", hypothesis: null, task_type: "arithmetic_representation", status: "completed", model_slug: "m", model_version: "v", is_demo_data: false, is_public: false, owned_by_me: true, evaluator: "numeric_match", temperature: 0, max_tokens: 64, seed: 0, repetitions: 1, created_at: "2026-10-04T10:00:00Z", started_at: null, finished_at: null, error: null, counts, config: {}, environment: {}, software_version: "0.1.0", notice: null, runs: [], ...over });

type Handler = (url: string, init?: RequestInit) => { status: number; body: unknown };
function mockFetch(handler: Handler) {
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const r = handler(url, init);
    return { ok: r.status < 400, status: r.status, json: async () => r.body };
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AuthProvider><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></AuthProvider></QueryClientProvider>);
}
beforeEach(() => { localStorage.clear(); setToken(null); });
afterEach(() => vi.restoreAllMocks());

test("anonymous visitors see 'Sign in' and send no credentials", async () => {
  const f = mockFetch((u) => (u.endsWith("/health") ? { status: 200, body: health } : { status: 200, body: [] }));
  renderAt("/experiments");
  expect((await screen.findAllByText("Sign in")).length).toBeGreaterThan(0);
  await waitFor(() => expect(f).toHaveBeenCalled());
  for (const call of f.mock.calls) expect((call[1]?.headers as Record<string, string>)?.Authorization).toBeUndefined();
});

test("signing in stores the token, sends it on later requests, and shows the user", async () => {
  const f = mockFetch((u) => {
    if (u.endsWith("/auth/login")) return { status: 200, body: { token: "tok123", token_type: "bearer", user } };
    if (u.endsWith("/health")) return { status: 200, body: health };
    if (u.endsWith("/configs")) return { status: 200, body: [] };
    return { status: 200, body: [] };
  });
  renderAt("/account");
  fireEvent.change(await screen.findByLabelText(/Email/), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "correct horse battery" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText(/Your experiments are private until you make them public/)).toBeInTheDocument();
  expect(getToken()).toBe("tok123");
  await waitFor(() => {
    const authed = f.mock.calls.filter((c) => (c[1]?.headers as Record<string, string>)?.Authorization === "Bearer tok123");
    expect(authed.length).toBeGreaterThan(0);
  });
});

test("a failed sign-in shows the server's message and stores nothing", async () => {
  mockFetch((u) => (u.endsWith("/auth/login") ? { status: 401, body: { detail: "incorrect email or password" } } : { status: 200, body: health }));
  renderAt("/account");
  fireEvent.change(await screen.findByLabelText(/Email/), { target: { value: "x@example.com" } });
  fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "wrong" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("incorrect email or password");
  expect(getToken()).toBeNull();
});

test("an expired token (401) signs the user out instead of leaving a broken session", async () => {
  setToken("stale");
  mockFetch((u) => (u.endsWith("/auth/me") ? { status: 401, body: { detail: "invalid or expired token" } } : { status: 200, body: health }));
  renderAt("/");
  await waitFor(() => expect(getToken()).toBeNull());
  expect((await screen.findAllByText("Sign in")).length).toBeGreaterThan(0);
});

test("owner sees their private experiment with a visibility toggle; others get read-only public ones", async () => {
  mockFetch((u) => {
    if (u.endsWith("/health")) return { status: 200, body: health };
    if (u.endsWith("/experiments/e1")) return { status: 200, body: exp({ owned_by_me: true, is_public: false }) };
    if (u.endsWith("/experiments/e2")) return { status: 200, body: exp({ id: "e2", owned_by_me: false, is_public: true }) };
    return { status: 200, body: [] };
  });
  const { unmount } = renderAt("/experiments/e1");
  expect(await screen.findByText("Private")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Make public" })).toBeInTheDocument();
  unmount();
  renderAt("/experiments/e2");
  expect(await screen.findByText("Public (read-only)")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Make (public|private)/ })).toBeNull();
  expect(screen.getByRole("button", { name: "Rerun" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Clone experiment" })).toBeEnabled();  // anyone who can see it may clone it
});
