import { useQuery } from "@tanstack/react-query";
import { EmptyState } from "../components/EmptyState";
import { DemoTag } from "../components/Status";
import { api } from "../services/api";

export function Models() {
  const { data, error, isLoading } = useQuery({ queryKey: ["models"], queryFn: api.models });
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Models</h1>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {isLoading && <p className="text-sm text-ink-soft">Loading…</p>}
      {data && data.length === 0 && <EmptyState title="No models registered">Configure MODEL_PROVIDER in .env.</EmptyState>}
      <ul className="divide-y divide-rule border-y border-rule">
        {data?.map((m) => (
          <li key={m.id} className="grid gap-2 py-4 sm:grid-cols-[1fr_auto] sm:items-center">
            <div>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {m.display_name} {m.is_mock && <DemoTag />}
                {m.configured && <span className="rounded bg-lens-wash px-2 py-0.5 text-xs text-lens-deep">active</span>}
              </p>
              <p className="mt-1 text-sm text-ink-soft">
                {m.provider} · context {m.context_length.toLocaleString()} tokens · versions: {m.versions.join(", ")}
              </p>
              <p className="text-xs text-ink-faint">{m.slug}</p>
            </div>
            <p className="text-sm text-ink-soft">{m.experiment_count} experiment{m.experiment_count === 1 ? "" : "s"}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
