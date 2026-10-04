import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { Markdown } from "../components/Markdown";
import { DemoTag } from "../components/Status";
import { api, downloadFile } from "../services/api";

export function Reports() {
  const { data, error } = useQuery({ queryKey: ["reports"], queryFn: api.reports });
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Research reports</h1>
      <p className="max-w-prose text-sm text-ink-soft">Generated from stored results with fixed sections, every number with its interval, and no claims beyond the evidence. Create one from an experiment page.</p>
      {error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>}
      {data?.length === 0 && <EmptyState title="No reports yet">Open an experiment and choose “Generate research report”.</EmptyState>}
      <ul className="divide-y divide-rule border-y border-rule">
        {data?.map((r) => (
          <li key={r.id} className="py-3 text-sm">
            <Link className="font-medium text-lens underline" to={`/reports/${r.id}`}>{r.title}</Link>{" "}
            {r.includes_demo_data && <DemoTag />} <span className="text-xs text-ink-faint">{new Date(r.created_at).toLocaleString()}{r.owned_by_me ? " · yours" : ""}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ReportView() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [dlError, setDlError] = useState<string | null>(null);
  const { data, error } = useQuery({ queryKey: ["report", id], queryFn: () => api.report(id) });
  const del = useMutation({ mutationFn: () => api.deleteReport(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ["reports"] }); nav("/reports"); } });
  if (error) return <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(error as Error).message}</p>;
  if (!data) return <p className="text-sm text-ink-soft">Loading…</p>;
  const btn = "rounded border border-rule px-3 py-1.5 text-sm hover:bg-panel";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <button className={btn} onClick={() => downloadFile(`/reports/${id}/download`, `${data.title.replace(/[^A-Za-z0-9._-]+/g, "_")}.md`).catch((e) => setDlError(e.message))}>Download Markdown</button>
        {data.experiment_id && <Link className={btn} to={`/experiments/${data.experiment_id}`}>Open experiment</Link>}
        {data.owned_by_me && <button className={btn} onClick={() => del.mutate()}>Delete report</button>}
      </div>
      {dlError && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{dlError}</p>}
      <Markdown source={data.content} />
    </div>
  );
}
