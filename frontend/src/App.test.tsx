import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, vi } from "vitest";
import { App } from "./App";

const health = {
  status: "ok", version: "0.1.0", environment: "test", database: "ok", model_provider: "mock",
  model_name: "mock-deterministic-v1", mock_mode: true, public_demo_mode: false, notice: "MOCK",
};

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("home renders the evidence ladder and the four primary actions", () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => health }));
  renderAt("/");
  expect(screen.getByText("Supported conclusion")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Run experiment" })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Dashboard" }).length).toBeGreaterThan(0);
});

test("mock mode shows the DEMO / MOCK DATA banner", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => health }));
  renderAt("/");
  await waitFor(() => expect(screen.getByText(/DEMO \/ MOCK DATA/)).toBeInTheDocument());
});

test("backend failure surfaces a clear error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
  renderAt("/dashboard");
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Cannot reach the LLM Lens backend/));
});

test("unknown route shows not found", () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => health }));
  renderAt("/nope");
  expect(screen.getByText("Page not found")).toBeInTheDocument();
});
