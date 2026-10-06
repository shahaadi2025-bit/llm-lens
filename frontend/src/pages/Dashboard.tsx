import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { DemoTag, Status } from "../components/Status";
import { api } from "../services/api";

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="border-t border-rule pt-3">
      <dt className="text-sm text-ink-soft">{label}</dt>
      <dd className="font-display text-4xl font-semibold text-lens-deep">{value}</dd>
      {note && <p className="mt-1 text-xs text-ink-faint">{note}</p>}
    </div>
  );
}

export function Dashboard() {
  const { data, error } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-semibold">Dashboard</h1>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {data && (
        <>
          <dl className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Experiments completed" value={data.experiments_completed} note={`${data.experiments_total} created`} />
            <Stat label="Models tested" value={data.models_tested} />
            <Stat label="Potential anomalies" value={data.potential_anomalies} note="Distinct flagged runs, not confirmed failures" />
            <Stat label="Failure clusters" value={data.failure_clusters} note="Groups of similar incorrect answers" />
          </dl>
          {data.includes_demo_data && (
            <p className="rounded bg-demo-wash p-3 text-sm text-demo">
              <strong>DEMO / MOCK DATA</strong> is included in these counts. It comes from a deterministic mock model and is not evidence about any real LLM.
            </p>
          )}
          <section aria-labelledby="recent">
            <h2 id="recent" className="mb-2 text-xl font-semibold">Recent experiments</h2>
            {data.recent.length === 0 ? (
              <EmptyState title="No experiments yet">Run the first one from the Experiments page.</EmptyState>
            ) : (
              <ul className="divide-y divide-rule border-y border-rule">
                {data.recent.map((e) => (
                  <li key={e.id} className="py-3">
                    <Link to={`/experiments/${e.id}`} className="flex flex-wrap items-center gap-2 hover:underline">
                      <span className="font-medium">{e.name}</span> <Status value={e.status} /> {e.is_demo_data && <DemoTag />}
                      <span className="text-xs text-ink-faint">{e.counts.passed}/{e.counts.succeeded} correct</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
