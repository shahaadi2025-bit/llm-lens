import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { GroupStat } from "../types/api";
import { pct } from "../utils/format";

/** Accuracy per prompt form with Wilson 95% intervals drawn as error bars. Never shows a bare point estimate. */
export function AccuracyByFormChart({ groups }: { groups: GroupStat[] }) {
  const data = groups.map((g) => ({
    name: g.group, accuracy: g.accuracy * 100, n: g.n, low: g.ci_low * 100, high: g.ci_high * 100,
    err: [(g.accuracy - g.ci_low) * 100, (g.ci_high - g.accuracy) * 100],
  }));
  return (
    <figure>
      <div className="h-72 w-full" role="img" aria-label="Accuracy by prompt form with 95% confidence intervals">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#CBD3DA" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-25} textAnchor="end" height={60} />
            <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
            <Tooltip formatter={(_v, _n, item) => {
              const p = item.payload;
              return [`${pct(p.accuracy / 100)}, 95% CI [${p.low.toFixed(0)}%, ${p.high.toFixed(0)}%], n=${p.n}`, "accuracy"];
            }} />
            <Bar dataKey="accuracy" fill="#0B5C7A" isAnimationActive={false}>
              <ErrorBar dataKey="err" stroke="#14222D" width={4} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-ink-faint">Bars: accuracy. Whiskers: Wilson 95% interval. Each form has n shown on hover.</figcaption>
    </figure>
  );
}
