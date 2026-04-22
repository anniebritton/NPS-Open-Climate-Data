export function fmtSlope(slope: number | null | undefined, decimals = 3): string {
  if (slope == null || Number.isNaN(slope)) return "—";
  const sign = slope > 0 ? "+" : "";
  return sign + slope.toFixed(decimals);
}

export function fmtPVal(p: number | null | undefined): string {
  if (p == null || Number.isNaN(p)) return "—";
  if (p < 0.001) return "p < 0.001";
  return "p = " + p.toFixed(3);
}

export function fmtTotal(slope: number | null | undefined, n: number | null | undefined): string {
  if (slope == null || n == null) return "—";
  const total = slope * (n - 1);
  const sign = total > 0 ? "+" : "";
  return sign + total.toFixed(2);
}

export function kebabToTitle(s: string): string {
  return s.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Display-time Celsius → Fahrenheit. Pipeline data stays in SI; only the
// rendered site converts, so CSV downloads and the methodology page remain
// scientific.
export function cToF(c: number | null | undefined): number | null {
  if (c == null || Number.isNaN(c)) return null;
  return c * 9 / 5 + 32;
}

// Temperature differences (slopes, deltas) scale by 9/5 only — no offset.
export function cDeltaToF(c: number | null | undefined): number | null {
  if (c == null || Number.isNaN(c)) return null;
  return c * 9 / 5;
}
