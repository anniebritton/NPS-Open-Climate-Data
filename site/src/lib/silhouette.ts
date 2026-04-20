/**
 * Build a normalized SVG path from a GeoJSON polygon/multipolygon. Input
 * coordinates are [lon, lat] (degrees). Output is a path string in a
 * 0..100 x 0..46 viewBox, with y flipped so north is up.
 */
type Ring = number[][];
type Geom = { type: string; coordinates: any };

export function silhouetteFromGeoJSON(geom: Geom): string {
  const rings: Ring[] = [];
  if (geom.type === "Polygon") {
    rings.push(...(geom.coordinates as Ring[]));
  } else if (geom.type === "MultiPolygon") {
    for (const poly of geom.coordinates as Ring[][]) rings.push(...poly);
  } else {
    return "";
  }
  // bbox
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const r of rings) {
    for (const [x, y] of r) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  // Preserve aspect: scale by the larger dimension to fit within 100x46 with
  // margin, so tiny parks still show up as a recognisable dot and big parks
  // fill the box.
  const targetW = 88, targetH = 34;
  const scale = Math.min(targetW / spanX, targetH / spanY);
  const drawW = spanX * scale;
  const drawH = spanY * scale;
  const offX = (100 - drawW) / 2;
  const offY = (46 - drawH) / 2;

  const parts: string[] = [];
  for (const r of rings) {
    r.forEach(([x, y], i) => {
      const px = offX + (x - minX) * scale;
      const py = offY + (maxY - y) * scale; // flip y
      parts.push(`${i === 0 ? "M" : "L"}${px.toFixed(2)},${py.toFixed(2)}`);
    });
    parts.push("Z");
  }
  return parts.join(" ");
}
