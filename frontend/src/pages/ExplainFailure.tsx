import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { FailureStatus } from "../components/FailureStatus";
import { api } from "../services/api";

const STRENGTH: Record<string, string> = { none: "None", weak: "Weak", moderate: "Moderate", strong: "Strong" };

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="grid gap-1 border-t border-rule py-4 sm:grid-cols-[11rem_1fr] sm:gap-6">
      <p className="font-display text-lg font-semibold text-lens-deep">{n}. {title}</p>
      <div className="text-sm leading-relaxed">{children}</div>
    </li>
  );
}

export function ExplainFailure() {
  const { id = "" } = useParams();
  const { data: e, error } = useQuery({ queryKey: ["explain", id], queryFn: () => api.explain(id) });
  if (error) return <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>;
  if (!e) return <p className="text-sm text-ink-soft">Loading…</p>;
  return (
    <div className="space-y-6">
      <header>
        <p className="text-sm"><Link className="text-lens underline" to={`/experiments/${e.failure.experiment_id}`}>← {e.failure.experiment_name}</Link></p>
        <h1 className="mt-2 text-3xl font-semibold">Explain this failure</h1>
        <p className="mt-2"><FailureStatus value={e.failure.status} /></p>
        {e.demo_notice && <p className="mt-3 rounded bg-demo-wash p-3 text-sm text-demo">{e.demo_notice}</p>}
      </header>
      <ol>
        <Step n={1} title="Observed behavior">{e.observed}
          <p className="mt-2 rounded bg-bench p-2 text-xs">Prompt: {e.failure.prompt}<br />Response: {e.failure.response}<br />Expected: {e.failure.expected_answer}</p></Step>
        <Step n={2} title="Controlled variables"><ul className="list-disc pl-5">{e.controlled_variables.map((c) => <li key={c}>{c}</li>)}</ul></Step>
        <Step n={3} title="Changed variable">{e.changed_variable}</Step>
        <Step n={4} title="Follow-up experiments">
          {e.follow_ups.length === 0 ? "None yet. Generate one from the experiment page." : (
            <ul className="space-y-2">{e.follow_ups.map((f) => (
              <li key={f.experiment_id}><Link className="text-lens underline" to={`/experiments/${f.experiment_id}`}>{f.name}</Link> ({f.status}){f.summary && <span className="block text-ink-soft">{f.summary}</span>}</li>
            ))}</ul>)}
        </Step>
        <Step n={5} title="Evidence">
          <p><span className="rounded bg-lens-wash px-2 py-0.5 text-xs font-medium text-lens-deep">{e.evidence.level}</span>{" "}
            Strength: <strong>{STRENGTH[e.evidence.strength]}</strong></p>
          <p className="mt-1">{e.evidence.summary}</p>
        </Step>
        <Step n={6} title="Possible explanations (hypotheses)">
          <ul className="list-disc pl-5">{e.possible_explanations.map((s) => <li key={s.text}>{s.text}</li>)}</ul>
          <p className="mt-2 font-medium">Alternatives that also fit</p>
          <ul className="list-disc pl-5">{e.alternative_explanations.map((s) => <li key={s.text}>{s.text}</li>)}</ul>
        </Step>
        <Step n={7} title="Limitations"><ul className="list-disc pl-5">{e.limitations.map((l) => <li key={l}>{l}</li>)}</ul></Step>
      </ol>
    </div>
  );
}
