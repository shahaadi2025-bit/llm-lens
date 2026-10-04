import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";
import { DemoTag, Status } from "../components/Status";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";

const field = "mt-1 w-full rounded border border-rule bg-white px-3 py-2 text-sm";

function SignInNeeded() {
  return <EmptyState title="Sign in to use the notebook">The research notebook is private to your account. <Link className="text-lens underline" to="/account">Sign in or create an account</Link>.</EmptyState>;
}

export function Notebook() {
  const { user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [question, setQuestion] = useState("");
  const list = useQuery({ queryKey: ["investigations"], queryFn: api.investigations, enabled: !!user });
  const create = useMutation({
    mutationFn: () => api.createInvestigation({ title, research_question: question, hypothesis: "" }),
    onSuccess: (inv) => { qc.invalidateQueries({ queryKey: ["investigations"] }); nav(`/notebook/${inv.id}`); },
  });
  if (!user) return <SignInNeeded />;
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Research notebook</h1>
      <form className="space-y-3 rounded border border-rule bg-panel p-4" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
        <h2 className="text-lg font-semibold">New investigation</h2>
        <label className="block text-sm">Title<input required maxLength={300} className={field} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <label className="block text-sm">Research question<textarea className={field} rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} /></label>
        {create.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(create.error as Error).message}</p>}
        <button disabled={create.isPending} className="rounded bg-lens px-4 py-2 text-sm font-medium text-white hover:bg-lens-deep disabled:opacity-50">Create</button>
      </form>
      {list.data?.length === 0 && <EmptyState title="No investigations yet">An investigation groups a question, a hypothesis, experiments, notes, a conclusion and its limitations.</EmptyState>}
      <ul className="divide-y divide-rule border-y border-rule">
        {list.data?.map((i) => (
          <li key={i.id} className="py-3 text-sm">
            <Link className="font-medium text-lens underline" to={`/notebook/${i.id}`}>{i.title}</Link>
            <p className="text-ink-soft">{i.research_question || "No question yet"}</p>
            <p className="text-xs text-ink-faint">{i.n_experiments} experiments · {i.n_notes} notes · {i.has_conclusion ? "conclusion recorded" : "no conclusion yet"}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function InvestigationView() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["investigation", id], queryFn: () => api.investigation(id), enabled: !!user });
  const exps = useQuery({ queryKey: ["experiments", ""], queryFn: () => api.experiments(), enabled: !!user });
  const [draft, setDraft] = useState({ research_question: "", hypothesis: "", conclusion: "", limitations: "" });
  const [kind, setKind] = useState("observation");
  const [text, setText] = useState("");
  const [pick, setPick] = useState("");
  useEffect(() => {
    if (q.data) setDraft({ research_question: q.data.research_question, hypothesis: q.data.hypothesis, conclusion: q.data.conclusion, limitations: q.data.limitations });
  }, [q.data]);
  const refresh = (d?: unknown) => { if (d) qc.setQueryData(["investigation", id], d); qc.invalidateQueries({ queryKey: ["investigations"] }); };
  const save = useMutation({ mutationFn: () => api.updateInvestigation(id, draft), onSuccess: refresh });
  const addNote = useMutation({ mutationFn: () => api.addNote(id, kind, text), onSuccess: (d) => { setText(""); refresh(d); } });
  const delNote = useMutation({ mutationFn: (n: string) => api.deleteNote(id, n), onSuccess: refresh });
  const link = useMutation({ mutationFn: () => api.linkExperiment(id, pick), onSuccess: (d) => { setPick(""); refresh(d); } });
  const unlink = useMutation({ mutationFn: (e: string) => api.unlinkExperiment(id, e), onSuccess: refresh });
  const report = useMutation({ mutationFn: () => api.createReport({ investigation_id: id }), onSuccess: (r) => nav(`/reports/${r.id}`) });
  const remove = useMutation({ mutationFn: () => api.deleteInvestigation(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ["investigations"] }); nav("/notebook"); } });
  if (!user) return <SignInNeeded />;
  if (q.error) return <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(q.error as Error).message}</p>;
  if (!q.data) return <p className="text-sm text-ink-soft">Loading…</p>;
  const d = q.data;
  const err = (save.error ?? addNote.error ?? link.error ?? report.error ?? unlink.error ?? delNote.error) as Error | null;
  const linked = new Set(d.experiments.map((e) => e.id));
  const btn = "rounded border border-rule px-3 py-1.5 text-sm hover:bg-panel disabled:opacity-50";
  return (
    <div className="space-y-8">
      <header>
        <p className="text-sm"><Link className="text-lens underline" to="/notebook">← Notebook</Link></p>
        <h1 className="mt-1 text-3xl font-semibold">{d.title}</h1>
      </header>
      {err && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{err.message}</p>}

      <section aria-labelledby="frame" className="space-y-3">
        <h2 id="frame" className="text-xl font-semibold">Question, hypothesis, conclusion</h2>
        <label className="block text-sm">Research question<textarea className={field} rows={2} value={draft.research_question} onChange={(e) => setDraft({ ...draft, research_question: e.target.value })} /></label>
        <label className="block text-sm">Hypothesis (state it before looking at results)<textarea className={field} rows={2} value={draft.hypothesis} onChange={(e) => setDraft({ ...draft, hypothesis: e.target.value })} /></label>
        <label className="block text-sm">Limitations<textarea className={field} rows={2} value={draft.limitations} onChange={(e) => setDraft({ ...draft, limitations: e.target.value })} /></label>
        <label className="block text-sm">Conclusion <span className="text-ink-faint">(needs limitations; a black-box experiment cannot show internal mechanisms)</span>
          <textarea className={field} rows={3} value={draft.conclusion} onChange={(e) => setDraft({ ...draft, conclusion: e.target.value })} /></label>
        <button className={btn} disabled={save.isPending} onClick={() => save.mutate()}>{save.isSuccess ? "Saved" : "Save"}</button>
      </section>

      <section aria-labelledby="exps" className="space-y-3">
        <h2 id="exps" className="text-xl font-semibold">Experiments</h2>
        {d.hidden_experiments > 0 && <p className="text-xs text-ink-faint">{d.hidden_experiments} linked experiment(s) are no longer visible to you.</p>}
        <ul className="divide-y divide-rule border-y border-rule">
          {d.experiments.map((e) => (
            <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="flex flex-wrap items-center gap-2"><Link className="text-lens underline" to={`/experiments/${e.id}`}>{e.name}</Link><Status value={e.status} />{e.is_demo_data && <DemoTag />}
                <span className="text-xs text-ink-faint">{e.counts.passed}/{e.counts.succeeded} correct</span></span>
              <button className="text-signal underline" onClick={() => unlink.mutate(e.id)}>Unlink</button>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">Add an experiment
            <select className="ml-2 rounded border border-rule bg-white px-2 py-1" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">choose…</option>
              {exps.data?.filter((e) => !linked.has(e.id)).map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select></label>
          <button className={btn} disabled={!pick || link.isPending} onClick={() => link.mutate()}>Link</button>
        </div>
      </section>

      <section aria-labelledby="notes" className="space-y-3">
        <h2 id="notes" className="text-xl font-semibold">Observations and notes</h2>
        <ul className="divide-y divide-rule border-y border-rule">
          {d.notes.map((n) => (
            <li key={n.id} className="flex flex-wrap items-start justify-between gap-2 py-2 text-sm">
              <span><span className="mr-2 rounded bg-bench px-2 py-0.5 text-xs text-ink-soft">{n.kind}</span>{n.text}</span>
              <button className="text-signal underline" onClick={() => delNote.mutate(n.id)}>Delete</button>
            </li>
          ))}
        </ul>
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); addNote.mutate(); }}>
          <label className="text-sm">Kind
            <select className="ml-2 rounded border border-rule bg-white px-2 py-1" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="observation">observation</option><option value="hypothesis">hypothesis</option><option value="note">note</option></select></label>
          <label className="min-w-[14rem] flex-1 text-sm">Text<input required maxLength={2000} className={field} value={text} onChange={(e) => setText(e.target.value)} /></label>
          <button className={btn} disabled={addNote.isPending}>Add</button>
        </form>
      </section>

      <div className="flex flex-wrap gap-2 border-t border-rule pt-4">
        <button className={btn} disabled={report.isPending} onClick={() => report.mutate()}>Generate investigation report</button>
        <button className={btn} onClick={() => { if (window.confirm("Delete this investigation?")) remove.mutate(); }}>Delete investigation</button>
      </div>
    </div>
  );
}
