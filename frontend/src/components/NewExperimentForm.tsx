import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

export function NewExperimentForm() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const types = useQuery({ queryKey: ["types"], queryFn: api.experimentTypes });
  const [taskType, setTaskType] = useState("");
  const [name, setName] = useState("");
  const [seed, setSeed] = useState(0);
  const [reps, setReps] = useState(1);
  const [model, setModel] = useState("");
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const selected = types.data?.find((t) => t.task_type === (taskType || types.data?.[0]?.task_type));

  const create = useMutation({
    mutationFn: async () => {
      const exp = await api.createExperiment({ name, task_type: selected!.task_type, seed, repetitions: reps, model_slug: model || undefined });
      await api.runExperiment(exp.id);
      return exp;
    },
    onSuccess: (exp) => { qc.invalidateQueries({ queryKey: ["experiments"] }); nav(`/experiments/${exp.id}`); },
  });

  if (!selected) return null;
  const field = "mt-1 w-full rounded border border-rule bg-white px-3 py-2 text-sm";
  return (
    <form className="space-y-4 rounded border border-rule bg-panel p-4 sm:p-6"
      onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
      <h2 className="text-xl font-semibold">New experiment</h2>
      <label className="block text-sm">Type
        <select className={field} value={selected.task_type} onChange={(e) => setTaskType(e.target.value)}>
          {types.data!.map((t) => <option key={t.task_type} value={t.task_type}>{t.title}</option>)}
        </select>
      </label>
      <div className="rounded bg-bench p-3 text-sm">
        <p className="font-medium">Research question</p>
        <p className="mt-1 text-ink-soft">{selected.research_question}</p>
        <p className="mt-2 text-ink-soft">{selected.description}</p>
      </div>
      {models.data && models.data.length > 1 && (
        <label className="block text-sm">Model
          <select className={field} value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">Server default</option>
            {models.data.map((m) => <option key={m.id} value={m.slug}>{m.display_name}</option>)}
          </select>
        </label>
      )}
      <label className="block text-sm">Name
        <input required maxLength={200} className={field} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">Seed
          <input type="number" min={0} className={field} value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
        </label>
        <label className="block text-sm">Repetitions
          <input type="number" min={1} max={20} className={field} value={reps} onChange={(e) => setReps(Number(e.target.value))} />
        </label>
      </div>
      {create.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(create.error as Error).message}</p>}
      <button disabled={create.isPending} className="rounded bg-lens px-4 py-2 text-sm font-medium text-white hover:bg-lens-deep disabled:opacity-50">
        {create.isPending ? "Starting…" : "Create and run"}
      </button>
    </form>
  );
}
