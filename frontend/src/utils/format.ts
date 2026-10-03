export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`;
export const interval = (lo: number | null, hi: number | null, asPct = true) =>
  lo === null || hi === null ? "n/a" : asPct ? `[${pct(lo)}, ${pct(hi)}]` : `[${lo.toFixed(2)}, ${hi.toFixed(2)}]`;
