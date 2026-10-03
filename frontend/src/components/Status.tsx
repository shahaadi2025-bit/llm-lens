const STYLES: Record<string, string> = {
  pending: "bg-bench text-ink-soft", running: "bg-lens-wash text-lens-deep", completed: "bg-[#DDEBDD] text-ok",
  failed: "bg-signal-wash text-signal", cancelled: "bg-bench text-ink-faint",
};

export function Status({ value }: { value: string }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${STYLES[value] ?? STYLES.pending}`}>{value}</span>;
}

export function DemoTag() {
  return <span className="rounded bg-demo-wash px-2 py-0.5 text-xs font-medium text-demo">DEMO / MOCK</span>;
}
