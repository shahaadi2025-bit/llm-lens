import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { EmptyState } from "../components/EmptyState";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";

export function Account() {
  const { user, loading, signIn, signUp, signOut } = useAuth();
  const qc = useQueryClient();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const auth = useMutation({ mutationFn: () => (mode === "in" ? signIn(email, password) : signUp(email, password, name)) });
  const configs = useQuery({ queryKey: ["configs"], queryFn: api.configs, enabled: !!user });
  const del = useMutation({ mutationFn: api.deleteConfig, onSuccess: () => qc.invalidateQueries({ queryKey: ["configs"] }) });
  const field = "mt-1 w-full rounded border border-rule bg-white px-3 py-2 text-sm";

  if (loading) return <p className="text-sm text-ink-soft">Loading…</p>;
  if (user) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-semibold">Account</h1>
        <p className="text-sm">Signed in as <strong>{user.display_name}</strong> ({user.email}). Your experiments are private until you make them public.</p>
        <button onClick={signOut} className="rounded border border-rule px-3 py-1.5 text-sm hover:bg-panel">Sign out</button>
        <section aria-labelledby="cfgs">
          <h2 id="cfgs" className="mb-2 text-xl font-semibold">Saved configurations</h2>
          {configs.data?.length === 0 && <EmptyState title="None saved">Save one from the New experiment form.</EmptyState>}
          <ul className="divide-y divide-rule border-y border-rule">
            {configs.data?.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{c.name} <span className="text-ink-faint">· {c.task_type} · seed {c.seed} · {c.repetitions}×</span></span>
                <button className="text-signal underline" onClick={() => del.mutate(c.id)}>Delete</button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    );
  }
  return (
    <div className="max-w-md space-y-4">
      <h1 className="text-3xl font-semibold">{mode === "in" ? "Sign in" : "Create an account"}</h1>
      <p className="text-sm text-ink-soft">Accounts keep your experiments private and let you save configurations. Browsing and limited experiments work without one.</p>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); auth.mutate(); }}>
        {mode === "up" && <label className="block text-sm">Display name (optional)<input className={field} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>}
        <label className="block text-sm">Email<input type="email" required autoComplete="email" className={field} value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="block text-sm">Password{mode === "up" && <span className="text-ink-faint"> (at least 10 characters)</span>}
          <input type="password" required minLength={mode === "up" ? 10 : 1} autoComplete={mode === "in" ? "current-password" : "new-password"} className={field} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {auth.error && <p role="alert" className="rounded bg-signal-wash p-3 text-sm text-signal">{(auth.error as Error).message}</p>}
        <button disabled={auth.isPending} className="rounded bg-lens px-4 py-2 text-sm font-medium text-white hover:bg-lens-deep disabled:opacity-50">{auth.isPending ? "…" : mode === "in" ? "Sign in" : "Create account"}</button>
      </form>
      <button className="text-sm text-lens underline" onClick={() => { setMode(mode === "in" ? "up" : "in"); auth.reset(); }}>
        {mode === "in" ? "No account? Create one" : "Have an account? Sign in"}</button>
    </div>
  );
}
