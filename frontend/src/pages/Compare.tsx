import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { api } from "../services/api";
import { pct } from "../utils/format";

export function Compare() {
  const versions = useQuery({ queryKey: ["versions"], queryFn: api.modelVersions });
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [go, setGo] = useState<[string, string] | null>(null);
  const res = useQuery({ queryKey: ["compare", go], queryFn: () => api.compare(go![0], go![1]), enabled: !!go });
  const sel = "ml-2 rounded border border-rule bg-white px-2 py-1";
  const label = (v: { model_slug: string; version_label: string; experiment_count: number }) => `${v.model_slug} ${v.version_label} (${v.experiment_count} exp.)`;
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Model version comparison</h1>
      <p className="max-w-prose text-sm text-ink-soft">Compares two versions only on experiments with an identical design, so differences are not artefacts of different questions. It never says what changed inside the model.</p>
      {versions.data && (
        <form className="flex flex-wrap items-end gap-4" onSubmit={(e) => { e.preventDefault(); if (a && b) setGo([a, b]); }}>
          <label className="text-sm">Version A
            <select className={sel} value={a} onChange={(e) => setA(e.target.value)}><option value="">choose…</option>{versions.data.map((v) => <option key={v.id} value={v.id}>{label(v)}</option>)}</select></label>
          <label className="text-sm">Version B
            <select className={sel} value={b} onChange={(e) => setB(e.target.value)}><option value="">choose…</option>{versions.data.map((v) => <option key={v.id} value={v.id}>{label(v)}</option>)}</select></label>
          <button disabled={!a || !b || a === b} className="rounded bg-lens px-4 py-2 text-sm font-medium text-white hover:bg-lens-deep disabled:opacity-50">Compare</button>
        </form>
      )}
      {res.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(res.error as Error).message}</p>}
      {res.data && (
        <>
          {res.data.includes_demo_data && <p className="rounded bg-demo-wash p-3 text-sm text-demo"><strong>DEMO / MOCK DATA</strong>: the mock versions differ by an injected error rate, by construction.</p>}
          {!res.data.comparable ? (
            <EmptyState title="No matched experiments">Run the same experiment (same type, config, seed and settings) on both versions, then compare. Experiments run so far have different designs.</EmptyState>
          ) : (
            <>
              <p className="text-sm text-ink-soft">{res.data.matched.length} matched experiment pair(s):{" "}
                {res.data.matched.map((m) => <span key={m.a.id}><Link className="text-lens underline" to={`/experiments/${m.a.id}`}>A</Link>/<Link className="text-lens underline" to={`/experiments/${m.b.id}`}>B</Link>{" "}</span>)}</p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[34rem] text-left text-sm">
                  <thead className="border-b border-rule text-ink-faint"><tr><th className="py-2 pr-3">Metric</th><th className="pr-3">A</th><th className="pr-3">B</th><th className="pr-3">B − A (95% CI)</th><th>Paired test</th></tr></thead>
                  <tbody className="divide-y divide-rule align-top">
                    {res.data.differences.map((d) => (
                      <tr key={`${d.metric}-${d.dimension}`}>
                        <td className="py-2 pr-3">{d.metric}{d.dimension && ` (${d.dimension})`}</td>
                        <td className="pr-3">{pct(d.a_value)} <span className="text-ink-faint">n={d.a_n}</span></td>
                        <td className="pr-3">{pct(d.b_value)} <span className="text-ink-faint">n={d.b_n}</span></td>
                        <td className="pr-3">{(d.difference * 100).toFixed(1)} pts [{(d.diff_ci_low * 100).toFixed(1)}, {(d.diff_ci_high * 100).toFixed(1)}]<span className="block text-xs text-ink-faint">Cohen's h {d.cohens_h.toFixed(2)}</span></td>
                        <td>{d.mcnemar_p !== null ? <>exact McNemar p={d.mcnemar_p.toPrecision(2)}<span className="block text-xs text-ink-faint">only A right: {d.paired_only_a}, only B right: {d.paired_only_b} (exploratory)</span></> : "n/a"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul className="space-y-2 text-sm">{res.data.differences.map((d) => <li key={d.statement}>{d.statement}</li>)}</ul>
            </>
          )}
          <ul className="list-disc pl-5 text-xs text-ink-faint">{res.data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}
    </div>
  );
}
