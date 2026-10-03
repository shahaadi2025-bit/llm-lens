import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { FailureStatus } from "./FailureStatus";

export function AnomaliesPanel({ experimentId, status }: { experimentId: string; status: string }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["failures", experimentId, status], queryFn: () => api.failures(experimentId) });
  const followUp = useMutation({
    mutationFn: (failureId: string) => api.followUp(experimentId, failureId),
    onSuccess: (c) => { qc.invalidateQueries({ queryKey: ["experiments"] }); nav(`/experiments/${c.id}`); },
  });
  const paired = data?.filter((f) => f.label === "representation_sensitivity") ?? [];
  const outliers = data?.filter((f) => f.label === "statistical_outlier") ?? [];
  if (!data || paired.length + outliers.length === 0) return null;
  return (
    <section aria-labelledby="anomalies" className="space-y-3">
      <h2 id="anomalies" className="text-xl font-semibold">Potential anomalies</h2>
      <p className="text-sm text-ink-soft">
        Flags are questions, not verdicts. A follow-up re-asks the same problem in every form with new seeds to see whether the behavior reproduces.
      </p>
      {followUp.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(followUp.error as Error).message}</p>}
      <ul className="divide-y divide-rule border-y border-rule">
        {paired.map((f) => (
          <li key={f.id} className="py-3 text-sm">
            <p className="flex flex-wrap items-center gap-2"><FailureStatus value={f.status} />
              <span className="font-medium">form-sensitivity</span> <span className="text-ink-soft">{f.details.block as string} · failed form {f.details.failed_group as string}</span></p>
            <p className="mt-1 text-ink-soft">“{f.prompt}” → {f.response} (expected {f.expected_answer})</p>
            <div className="mt-2 flex flex-wrap gap-3">
              <Link className="text-lens underline" to={`/failures/${f.id}`}>Explain this failure</Link>
              <button type="button" className="text-lens underline disabled:opacity-50" disabled={followUp.isPending}
                onClick={() => followUp.mutate(f.id)}>Generate follow-up experiment</button>
            </div>
          </li>
        ))}
      </ul>
      {outliers.length > 0 && (
        <details className="text-sm text-ink-soft">
          <summary className="cursor-pointer">{outliers.length} statistical outlier flags (latency / response length)</summary>
          <ul className="mt-2 space-y-1 text-xs">
            {outliers.slice(0, 30).map((f) => (
              <li key={f.id}><Link className="text-lens underline" to={`/failures/${f.id}`}>{f.detector}</Link>: {(f.details.features as string[]).join(", ")}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
