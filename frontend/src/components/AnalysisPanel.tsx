import { useQuery } from "@tanstack/react-query";
import { AccuracyByFormChart } from "../charts/AccuracyByFormChart";
import { api } from "../services/api";

const LEVEL_STYLE: Record<string, string> = {
  observation: "bg-bench text-ink-soft", correlation: "bg-lens-wash text-lens-deep",
  hypothesis: "bg-signal-wash text-signal", supported_conclusion: "bg-[#DDEBDD] text-ok",
};

export function AnalysisPanel({ experimentId, status }: { experimentId: string; status: string }) {
  const { data } = useQuery({ queryKey: ["analysis", experimentId, status], queryFn: () => api.analysis(experimentId) });
  if (!data || data.groups.length === 0) return null;
  return (
    <section aria-labelledby="analysis" className="space-y-4">
      <h2 id="analysis" className="text-xl font-semibold">Sensitivity analysis</h2>
      <AccuracyByFormChart groups={data.groups} />
      <ul className="space-y-2">
        {data.statements.map((s, i) => (
          <li key={i} className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
            <span className={`w-fit shrink-0 rounded px-2 py-0.5 text-xs font-medium ${LEVEL_STYLE[s.evidence_level] ?? ""}`}>{s.evidence_level.replace("_", " ")}</span>
            <span className="text-sm leading-relaxed">{s.text}</span>
          </li>
        ))}
      </ul>
      <details className="text-sm text-ink-soft">
        <summary className="cursor-pointer">Methodology and limitations</summary>
        <p className="mt-2 text-xs">{data.method}; {data.n_blocks} complete problem sets.</p>
        <ul className="mt-1 list-disc pl-5 text-xs">{data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </details>
    </section>
  );
}
