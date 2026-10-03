import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Dimension } from "../types/api";

/** Measured dimensions only, each with its Wilson interval. Unmeasured ones are listed by the page, never drawn as 0. */
export function FingerprintChart({ dims }: { dims: Dimension[] }) {
  const data = dims.filter((d) => d.measured).map((d) => ({
    name: `${d.code} ${d.name}`, value: d.value! * 100, low: d.ci_low! * 100, high: d.ci_high! * 100, n: d.n,
    err: [(d.value! - d.ci_low!) * 100, (d.ci_high! - d.value!) * 100],
  }));
  if (data.length === 0) return null;
  return (
    <figure>
      <div className="w-full" style={{ height: 70 + data.length * 56 }} role="img" aria-label="Behavioral fingerprint with 95% intervals">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#CBD3DA" horizontal={false} />
            <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(_v, _n, item) => {
              const p = item.payload;
              return [`${p.value.toFixed(1)}%, 95% CI [${p.low.toFixed(0)}%, ${p.high.toFixed(0)}%], n=${p.n}`, "accuracy"];
            }} />
            <Bar dataKey="value" fill="#0B5C7A" isAnimationActive={false} barSize={18}>
              <ErrorBar dataKey="err" direction="x" stroke="#14222D" width={4} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="text-xs text-ink-faint">Bars: pooled accuracy. Whiskers: Wilson 95% interval. No overall score is computed on purpose.</figcaption>
    </figure>
  );
}
