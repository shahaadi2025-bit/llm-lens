import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { FingerprintChart } from "../charts/FingerprintChart";
import { Evidence } from "../components/MetricsPanel";
import { DemoTag } from "../components/Status";
import { api } from "../services/api";
import { interval, pct } from "../utils/format";

export function Fingerprint() {
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const [picked, setPicked] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const modelId = picked || models.data?.find((m) => m.experiment_count > 0)?.id || models.data?.[0]?.id || "";
  const fp = useQuery({ queryKey: ["fingerprint", modelId], queryFn: () => api.fingerprint(modelId), enabled: !!modelId });
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Behavioral fingerprint</h1>
      <p className="max-w-prose text-sm text-ink-soft">One axis per behavior, each with its interval and the experiments behind it. There is no single AI score.</p>
      {models.data && (
        <label className="block text-sm">Model
          <select className="ml-2 rounded border border-rule bg-white px-2 py-1" value={modelId} onChange={(e) => setPicked(e.target.value)}>
            {models.data.map((m) => <option key={m.id} value={m.id}>{m.display_name}</option>)}
          </select>
        </label>
      )}
      {fp.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(fp.error as Error).message}</p>}
      {fp.data && (
        <>
          {fp.data.includes_demo_data && <p className="rounded bg-demo-wash p-3 text-sm text-demo"><strong>DEMO / MOCK DATA</strong>: this fingerprint describes a mock model, not a real LLM.</p>}
          <FingerprintChart dims={fp.data.dimensions} />
          <ul className="divide-y divide-rule border-y border-rule">
            {fp.data.dimensions.map((d) => (
              <li key={d.code} className="py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-medium">{d.code} · {d.name} {fp.data!.includes_demo_data && d.measured && <DemoTag />}</p>
                  {d.measured
                    ? <p>{pct(d.value!)} <span className="text-sm text-ink-soft">{interval(d.ci_low, d.ci_high)} · n={d.n}</span></p>
                    : <p className="text-sm text-ink-faint">not measured</p>}
                </div>
                <p className="text-xs text-ink-faint">{d.how_measured}{d.method && ` · ${d.method}`}</p>
                {d.measured && (
                  <details className="mt-1 text-sm">
                    <summary className="cursor-pointer text-lens">Experiments behind this ({d.metrics.length})</summary>
                    <ul className="mt-2 space-y-2">
                      {d.metrics.map((m) => (
                        <li key={m.metric_id}>
                          <Link className="text-lens underline" to={`/experiments/${m.experiment_id}`}>{m.experiment_name}</Link>{" "}
                          {pct(m.value)} {interval(m.ci_low, m.ci_high)} n={m.n}{" "}
                          <button type="button" className="text-lens underline" onClick={() => setOpen(open === m.metric_id ? null : m.metric_id)}>
                            {open === m.metric_id ? "hide evidence" : "show evidence"}
                          </button>
                          {open === m.metric_id && <Evidence metricId={m.metric_id} />}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </li>
            ))}
          </ul>
          <ul className="list-disc pl-5 text-xs text-ink-faint">{fp.data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}
    </div>
  );
}
