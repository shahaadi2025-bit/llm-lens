import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Status } from "./Status";
import { api } from "../services/api";

/** Investigation chain: experiment -> anomaly -> follow-up -> ... shown as an ordered, linked list. */
export function LineageView({ experimentId }: { experimentId: string }) {
  const { data } = useQuery({ queryKey: ["lineage", experimentId], queryFn: () => api.lineage(experimentId) });
  if (!data || data.nodes.length < 2) return null;
  const byId = new Map(data.nodes.map((n) => [n.id, n]));
  const children = new Map<string, typeof data.edges>();
  data.edges.forEach((e) => children.set(e.parent, [...(children.get(e.parent) ?? []), e]));
  const childIds = new Set(data.edges.map((e) => e.child));
  const roots = data.nodes.filter((n) => !childIds.has(n.id));

  const render = (id: string, relation?: string, depth = 0): JSX.Element => {
    const n = byId.get(id)!;
    return (
      <li key={`${id}-${relation}`} style={{ marginLeft: `${depth * 1.25}rem` }} className="border-l-2 border-rule py-2 pl-3">
        {relation && <p className="text-xs uppercase tracking-wide text-ink-faint">↳ {relation.replace("_", " ")}</p>}
        <p className="flex flex-wrap items-center gap-2 text-sm">
          {n.is_current ? <strong>{n.name} (this experiment)</strong> : <Link className="text-lens underline" to={`/experiments/${n.id}`}>{n.name}</Link>}
          <Status value={n.status} />
          {n.anomalies > 0 && <span className="text-xs text-signal">{n.anomalies} flagged</span>}
        </p>
        <ul>{(children.get(id) ?? []).map((e) => render(e.child, e.relation, depth + 1))}</ul>
      </li>
    );
  };
  return (
    <section aria-labelledby="lineage">
      <h2 id="lineage" className="mb-2 text-xl font-semibold">Experiment lineage</h2>
      <ul>{roots.map((r) => render(r.id))}</ul>
    </section>
  );
}
