const STYLE: Record<string, string> = {
  potential_anomaly: "bg-signal-wash text-signal", reproduced: "bg-lens-wash text-lens-deep",
  not_reproduced: "bg-bench text-ink-soft", dismissed: "bg-bench text-ink-faint",
};
/** Amber 'POTENTIAL ANOMALY' on purpose: a flag is a question, never a verdict of model failure. */
export function FailureStatus({ value }: { value: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${STYLE[value] ?? ""}`}>{value.replace(/_/g, " ").toUpperCase()}</span>;
}
