/**
 * Hawkins climate-stripes colour ramp: cool blue -> warm red through
 * off-white. Accepts a z-score-like value (typically -3 .. +3) and
 * returns a CSS rgb() string.
 */
export function stripeColor(z: number | null | undefined): string {
  if (z == null || Number.isNaN(z)) return "#e8e3d3";
  const v = Math.max(-3, Math.min(3, z));
  // Two-sided ramp centred on warm cream.
  // Cool: #1b3a66 -> #9cb9d2 -> #efe6d2 -> #d08663 -> #7a1c1c (warm)
  const stops = v < 0
    ? [[-3, [61, 97, 137]], [-1.5, [168, 196, 232]], [0, [240, 227, 211]]]
    : [[0, [240, 227, 211]], [1.5, [232, 176, 140]], [3, [77, 38, 35]]];
  let a = stops[0], b = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) {
    if (v >= (stops[i][0] as number) && v <= (stops[i + 1][0] as number)) {
      a = stops[i];
      b = stops[i + 1];
      break;
    }
  }
  const t = ((v as number) - (a[0] as number)) / ((b[0] as number) - (a[0] as number) || 1);
  const ca = a[1] as number[];
  const cb = b[1] as number[];
  const r = Math.round(ca[0] + (cb[0] - ca[0]) * t);
  const g = Math.round(ca[1] + (cb[1] - ca[1]) * t);
  const bl = Math.round(ca[2] + (cb[2] - ca[2]) * t);
  return `rgb(${r},${g},${bl})`;
}
