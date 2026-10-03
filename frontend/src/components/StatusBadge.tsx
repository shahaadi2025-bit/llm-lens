import { useHealth } from "../hooks/useHealth";

export function StatusBadge() {
  const { data, isError, isLoading } = useHealth();
  const state = isLoading ? "checking" : isError ? "offline" : data?.status === "ok" ? "online" : "degraded";
  const dot = { checking: "bg-ink-faint", offline: "bg-signal", degraded: "bg-signal", online: "bg-ok" }[state];
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-soft" aria-live="polite">
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
      API {state}
    </span>
  );
}
