import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../services/api";
import { interval, pct } from "../utils/format";

function Evidence({ metricId }: { metricId: string }) {
  const { data, error } = useQuery({ queryKey: ["evidence", metricId], queryFn: () => api.evidence(metricId) });
  if (error) return <p role="alert" className="text-sm text-signal">{(error as Error).message}</p>;
  if (!data) return <p className="text-sm text-ink-soft">Loading evidence…</p>;
  return (
    <div className="mt-2 overflow-x-auto rounded bg-bench p-3">
      <p className="mb-2 text-xs text-ink-soft">
        {data.runs.length} runs behind this number: prompt, response, then the deterministic evaluator's verdict.
      </p>
      <table className="w-full min-w-[32rem] text-left text-xs">
        <thead className="text-ink-faint"><tr><th className="pr-2">Prompt</th><th className="pr-2">Response</th><th className="pr-2">Expected</th><th>Verdict</th></tr></thead>
        <tbody className="divide-y divide-rule align-top">
          {data.runs.map((r) => (
            <tr key={r.id}>
              <td className="py-1 pr-2">{r.prompt}</td><td className="pr-2">{r.response}</td><td className="pr-2">{r.expected_answer}</td>
              <td>{r.evaluation?.passed ? "correct" : "incorrect"} <span className="text-ink-faint">({r.evaluation?.evaluator_name})</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MetricsPanel({ experimentId, status }: { experimentId: string; status: string }) {
  const { data, error } = useQuery({
    queryKey: ["metrics", experimentId, status], queryFn: () => api.metrics(experimentId),
  });
  const [open, setOpen] = useState<string | null>(null);
  if (error) return <p role="alert" className="text-sm text-signal">{(error as Error).message}</p>;
  if (!data) return null;
  if (data.length === 0) return <p className="text-sm text-ink-soft">No metrics yet: they appear once runs have finished.</p>;
  const main = data.filter((m) => !m.name.includes("[") && m.name !== "latency_ms_mean");
  return (
    <ul className="divide-y divide-rule border-y border-rule">
      {main.map((m) => {
        const isRate = m.name === "accuracy" || m.name.endsWith("_rate");
        return (
          <li key={m.id} className="py-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-medium">{m.name.replace(/_/g, " ")}</p>
              <p className="text-lg">
                {isRate ? pct(m.value) : m.value.toFixed(2)}{" "}
                <span className="text-sm text-ink-soft">{interval(m.ci_low, m.ci_high, isRate)} · n={m.n}</span>
              </p>
            </div>
            <p className="text-xs text-ink-faint">{Math.round(m.ci_level * 100)}% interval · method: {m.method}</p>
            <button type="button" className="mt-1 text-sm text-lens underline" aria-expanded={open === m.id}
              onClick={() => setOpen(open === m.id ? null : m.id)}>
              {open === m.id ? "Hide evidence" : `Show evidence (${m.evidence_runs} runs)`}
            </button>
            {open === m.id && <Evidence metricId={m.id} />}
          </li>
        );
      })}
    </ul>
  );
}
