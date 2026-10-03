import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { FailureStatus } from "../components/FailureStatus";
import { DemoTag } from "../components/Status";
import { api } from "../services/api";

function ClusterCard({ id, label, size, method, embedding_model, error_types, demo }: {
  id: string; label: string; size: number; method: string; embedding_model: string | null; error_types: Record<string, number>; demo: boolean;
}) {
  const [open, setOpen] = useState(false);
  const detail = useQuery({ queryKey: ["cluster", id], queryFn: () => api.cluster(id), enabled: open });
  return (
    <li className="py-3 text-sm">
      <p className="flex flex-wrap items-center gap-2"><span className="font-medium">{label}</span> <span className="text-ink-soft">{size} failures</span> {demo && <DemoTag />}</p>
      <p className="text-xs text-ink-faint">{Object.entries(error_types).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`).join(" · ")}</p>
      <p className="text-xs text-ink-faint">{method} · embedding: {embedding_model}</p>
      <button type="button" className="mt-1 text-lens underline" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide failures" : "Inspect failures"}</button>
      {open && detail.data && (
        <ul className="mt-2 space-y-1 rounded bg-bench p-3 text-xs">
          {detail.data.members.map((m) => (
            <li key={m.id}><Link className="text-lens underline" to={`/failures/${m.id}`}>{m.details.group as string ?? "n/a"}</Link>: “{m.prompt.slice(0, 70)}” → {m.response}</li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function Failures() {
  const qc = useQueryClient();
  const clusters = useQuery({ queryKey: ["clusters"], queryFn: api.clusters });
  const recompute = useMutation({ mutationFn: api.recomputeClusters, onSuccess: () => { qc.invalidateQueries({ queryKey: ["clusters"] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); } });
  const { data, error } = useQuery({ queryKey: ["failures", "all"], queryFn: () => api.failures() });
  const paired = data?.filter((f) => f.label === "representation_sensitivity") ?? [];
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Failure analysis</h1>
      <p className="max-w-prose text-sm text-ink-soft">Form-sensitivity anomalies across experiments. Clusters group similar incorrect answers; they describe the outputs, not their cause.</p>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {data && paired.length === 0 && <EmptyState title="No form-sensitivity anomalies">They appear when the same problem is answered correctly in some prompt forms and incorrectly in others.</EmptyState>}
      <section aria-labelledby="clusters" className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="clusters" className="text-xl font-semibold">Failure clusters</h2>
          <button type="button" disabled={recompute.isPending} onClick={() => recompute.mutate()} className="rounded border border-rule px-3 py-1.5 text-sm hover:bg-panel disabled:opacity-50">
            {recompute.isPending ? "Clustering…" : "Recompute clusters"}</button>
        </div>
        {recompute.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(recompute.error as Error).message}</p>}
        {clusters.data?.length === 0 && <p className="text-sm text-ink-soft">No clusters yet. Run experiments, then click Recompute clusters.</p>}
        <ul className="divide-y divide-rule border-y border-rule">
          {clusters.data?.map((c) => <ClusterCard key={c.id} id={c.id} label={c.label} size={c.size} method={c.method} embedding_model={c.embedding_model} error_types={c.error_types} demo={c.includes_demo_data} />)}
        </ul>
      </section>
      <h2 className="text-xl font-semibold">Form-sensitivity anomalies</h2>
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
