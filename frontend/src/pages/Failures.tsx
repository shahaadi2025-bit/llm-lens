import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { FailureStatus } from "../components/FailureStatus";
import { DemoTag } from "../components/Status";
import { api } from "../services/api";

export function Failures() {
  const { data, error } = useQuery({ queryKey: ["failures", "all"], queryFn: () => api.failures() });
  const paired = data?.filter((f) => f.label === "representation_sensitivity") ?? [];
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Failure analysis</h1>
      <p className="max-w-prose text-sm text-ink-soft">Form-sensitivity anomalies across experiments. Clustering of similar failures arrives in Phase 5.</p>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {data && paired.length === 0 && <EmptyState title="No form-sensitivity anomalies">They appear when the same problem is answered correctly in some prompt forms and incorrectly in others.</EmptyState>}
      <ul className="divide-y divide-rule border-y border-rule">
        {paired.map((f) => (
          <li key={f.id} className="py-3 text-sm">
            <p className="flex flex-wrap items-center gap-2"><FailureStatus value={f.status} /> {f.is_demo_data && <DemoTag />}
              <Link className="font-medium text-lens underline" to={`/failures/${f.id}`}>{f.details.block as string} · {f.details.failed_group as string}</Link></p>
            <p className="mt-1 text-ink-soft">{f.experiment_name}: “{f.prompt}” → {f.response}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
