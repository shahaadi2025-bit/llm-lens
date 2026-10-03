import { EmptyState } from "../components/EmptyState";
import { useHealth } from "../hooks/useHealth";

export function Dashboard() {
  const { data, error } = useHealth();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Dashboard</h1>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {data && (
        <dl className="grid gap-x-8 gap-y-3 border-y border-rule py-4 text-sm sm:grid-cols-2">
          <div><dt className="text-ink-faint">Model provider</dt><dd>{data.model_provider}</dd></div>
          <div><dt className="text-ink-faint">Model</dt><dd>{data.model_name}</dd></div>
          <div><dt className="text-ink-faint">Database</dt><dd>{data.database}</dd></div>
          <div><dt className="text-ink-faint">Version</dt><dd>{data.version} ({data.environment})</dd></div>
        </dl>
      )}
      <EmptyState title="No experiments yet">
        Experiment counts, potential anomalies and failure clusters will appear here once the experiment engine
        lands (Phase 2) and statistics are wired in (Phase 3). Nothing on this page is placeholder data.
      </EmptyState>
    </div>
  );
}
