import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "../services/api";
import type { User } from "../types/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name: string) => Promise<void>;
  signOut: () => void;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  const load = useCallback(async () => {
    if (!getToken()) { setUser(null); setLoading(false); return; }
    try { setUser(await api.me()); } catch { setUser(null); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {  // a 401 anywhere in the app clears the session
    const h = () => { setUser(null); qc.clear(); };
    window.addEventListener("lens-auth-changed", h);
    return () => window.removeEventListener("lens-auth-changed", h);
  }, [qc]);

  const value = useMemo<AuthState>(() => {
    // Identity changed: cached responses may contain another identity's private data, so drop them all.
    const adopt = (r: { token: string; user: User }) => { setToken(r.token); setUser(r.user); qc.clear(); };
    return {
      user, loading,
      signIn: async (e, p) => adopt(await api.login(e, p)),
      signUp: async (e, p, n) => adopt(await api.register(e, p, n)),
      signOut: () => { setToken(null); setUser(null); qc.clear(); },
    };
  }, [user, loading, qc]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
