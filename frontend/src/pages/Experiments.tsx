import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { NewExperimentForm } from "../components/NewExperimentForm";
import { DemoTag, Status } from "../components/Status";
import { api } from "../services/api";

const STATUSES = ["", "pending", "running", "completed", "failed", "cancelled"];

export function Experiments() {
  const [status, setStatus] = useState("");
  const [showForm, setShowForm] = useState(false);
  const { data, error, isLoading } = useQuery({
    queryKey: ["experiments", status], queryFn: () => api.experiments(status || undefined),
    refetchInterval: (q) => (q.state.data?.some((e) => e.status === "running") ? 1500 : false),
  });
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold">Experiments</h1>
        <button onClick={() => setShowForm((v) => !v)} className="rounded bg-lens px-4 py-2 text-sm font-medium text-white hover:bg-lens-deep">
          {showForm ? "Close" : "Run experiment"}
        </button>
      </div>
      {showForm && <NewExperimentForm />}
      <label className="block text-sm">Status
        <select className="ml-2 rounded border border-rule bg-white px-2 py-1" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => <option key={s} value={s}>{s || "all"}</option>)}
        </select>
      </label>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {isLoading && <p className="text-sm text-ink-soft">Loading…</p>}
      {data?.length === 0 && <EmptyState title="No experiments yet">Choose “Run experiment” to create the first one.</EmptyState>}
      <ul className="divide-y divide-rule border-y border-rule">
        {data?.map((e) => (
          <li key={e.id} className="py-4">
            <Link to={`/experiments/${e.id}`} className="block hover:bg-panel">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {e.name} <Status value={e.status} /> {e.is_demo_data && <DemoTag />}
              </p>
              <p className="mt-1 text-sm text-ink-soft">{e.research_question}</p>
              <p className="mt-1 text-xs text-ink-faint">
                {e.task_type} · {e.model_slug} · {e.counts.succeeded}/{e.counts.total} runs done · {new Date(e.created_at).toLocaleString()}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
