const LEVELS = [
  { name: "Observation", text: "What was measured, with sample size and interval. Nothing more." },
  { name: "Correlation", text: "A variable changed and the metric moved with it, under controlled conditions." },
  { name: "Hypothesis", text: "A candidate explanation. Stated as testable, never as fact." },
  { name: "Supported conclusion", text: "A hypothesis that survived reproduced follow-up experiments. Internal mechanisms are still not claimed." },
];

/** The platform's central rule, shown rather than described. */
export function EvidenceLadder() {
  return (
    <ol className="divide-y divide-rule border-y border-rule">
      {LEVELS.map((l, i) => (
        <li key={l.name} className="grid gap-1 py-4 sm:grid-cols-[13rem_1fr] sm:gap-6" style={{ paddingLeft: `${i * 0.75}rem` }}>
          <span className="font-display text-lg font-semibold text-lens-deep">{l.name}</span>
          <span className="text-sm leading-relaxed text-ink-soft">{l.text}</span>
        </li>
      ))}
    </ol>
  );
}
