/**
 * Hawkins climate-stripes color ramp: traditional blue -> white -> red
 * (ColorBrewer RdBu diverging). Accepts a z-score-like value
 * (typically -3 .. +3) and returns a CSS rgb() string.
 */
export function stripeColor(z: number | null | undefined): string {
  if (z == null || Number.isNaN(z)) return "#f7f7f7";
  const v = Math.max(-3, Math.min(3, z));
  // RdBu 7-class: deep blue -> mid blue -> off-white -> red -> deep red
  const stops = v < 0
    ? [[-3, [5, 48, 97]], [-1.5, [67, 147, 195]], [0, [247, 247, 247]]]
    : [[0, [247, 247, 247]], [1.5, [214, 96, 77]], [3, [103, 0, 31]]];
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
