import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { AnomaliesPanel } from "../components/AnomaliesPanel";
import { LineageView } from "../components/LineageView";
import { AnalysisPanel } from "../components/AnalysisPanel";
import { MetricsPanel } from "../components/MetricsPanel";
import { DemoTag, Status } from "../components/Status";
import { api } from "../services/api";

export function ExperimentDetail() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: d, error } = useQuery({
    queryKey: ["experiment", id], queryFn: () => api.experiment(id),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 1000 : false),
  });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["experiment", id] }); qc.invalidateQueries({ queryKey: ["experiments"] }); };
  const run = useMutation({ mutationFn: () => api.runExperiment(id), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: () => api.cancelExperiment(id), onSuccess: refresh });
  const clone = useMutation({ mutationFn: () => api.cloneExperiment(id), onSuccess: (c) => nav(`/experiments/${c.id}`) });

  if (error) return <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>;
  if (!d) return <p className="text-sm text-ink-soft">Loading…</p>;
  const btn = "rounded border border-rule px-3 py-1.5 text-sm hover:bg-panel disabled:opacity-50";
  const actionError = (run.error ?? cancel.error ?? clone.error) as Error | null;

  return (
    <div className="space-y-8">
      <header>
        <p className="flex flex-wrap items-center gap-2"><Status value={d.status} /> {d.is_demo_data && <DemoTag />}</p>
        <h1 className="mt-2 text-3xl font-semibold">{d.name}</h1>
        <p className="mt-3 max-w-prose"><span className="text-ink-faint">Research question. </span>{d.research_question}</p>
        {d.notice && <p className="mt-3 rounded bg-demo-wash p-3 text-sm text-demo">{d.notice}</p>}
        {d.error && <p className="mt-3 rounded bg-signal-wash p-3 text-sm text-signal">{d.error}</p>}
        {actionError && <p role="alert" className="mt-3 rounded bg-signal-wash p-3 text-sm text-signal">{actionError.message}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          <button className={btn} disabled={d.status === "running" || run.isPending} onClick={() => run.mutate()}>
            {d.status === "completed" ? "Rerun" : d.status === "pending" ? "Run" : "Resume"}
          </button>
          <button className={btn} disabled={d.status !== "running" && d.status !== "pending"} onClick={() => cancel.mutate()}>Cancel</button>
          <button className={btn} onClick={() => clone.mutate()}>Clone experiment</button>
        </div>
      </header>

      <section aria-labelledby="cfg">
        <h2 id="cfg" className="mb-2 text-xl font-semibold">Configuration</h2>
        <dl className="grid gap-x-8 gap-y-2 border-y border-rule py-3 text-sm sm:grid-cols-2">
          {[["Model", `${d.model_slug} (${d.model_version})`], ["Evaluator", d.evaluator], ["Temperature", d.temperature],
            ["Max tokens", d.max_tokens], ["Seed", d.seed], ["Repetitions", d.repetitions], ["Software", d.software_version],
            ["Python", String(d.environment.python ?? "")]].map(([k, v]) => (
            <div key={String(k)}><dt className="text-ink-faint">{k}</dt><dd>{String(v)}</dd></div>
          ))}
        </dl>
      </section>

      {d.counts.succeeded > 0 && (
        <section aria-labelledby="metrics">
          <h2 id="metrics" className="mb-2 text-xl font-semibold">Metrics</h2>
          <MetricsPanel experimentId={d.id} status={d.status} />
        </section>
      )}
      {d.counts.succeeded > 0 && d.status !== "running" && <AnalysisPanel experimentId={d.id} status={d.status} />}

      {d.counts.succeeded > 0 && d.status !== "running" && <AnomaliesPanel experimentId={d.id} status={d.status} />}
      <LineageView experimentId={d.id} />

      <section aria-labelledby="runs">
        <h2 id="runs" className="mb-1 text-xl font-semibold">Runs</h2>
        <p className="mb-3 text-sm text-ink-soft">
          {d.counts.succeeded} of {d.counts.total} finished; {d.counts.passed} judged correct by the deterministic evaluator.
          Intervals and evidence links are in Metrics above.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="border-b border-rule text-ink-faint">
              <tr><th className="py-2 pr-3">Variant</th><th className="pr-3">Prompt</th><th className="pr-3">Response</th><th className="pr-3">Expected</th><th className="pr-3">Result</th><th>ms</th></tr>
            </thead>
            <tbody className="divide-y divide-rule align-top">
              {d.runs.map((r) => (
                <tr key={r.id}>
                  <td className="py-2 pr-3 text-xs text-ink-soft">{r.variant_label}</td>
                  <td className="pr-3">{r.prompt}</td>
                  <td className="pr-3">{r.response ?? (r.error ? <span className="text-signal">{r.error}</span> : "—")}</td>
                  <td className="pr-3">{r.expected_answer}</td>
                  <td className="pr-3">{r.evaluation ? (r.evaluation.passed ? "correct" : "incorrect") : r.status}
                    {r.evaluation && <span className="block text-xs text-ink-faint">{r.evaluation.evaluator_name} (deterministic)</span>}</td>
                  <td>{r.latency_ms?.toFixed(0) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
