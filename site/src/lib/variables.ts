/** Human-readable metadata for canonical climate variables. */

export interface VarMeta {
  label: string;
  unit: string;
  slopeUnit: string;
  description: string;
  kind: "temperature" | "precip" | "snow" | "other";
  decimals: number;
}

export const VARS: Record<string, VarMeta> = {
  tmean_c: {
    label: "Mean temperature",
    unit: "°F",
    slopeUnit: "°F / yr",
    description: "Annual mean of daily mean near-surface temperature.",
    kind: "temperature",
    decimals: 3,
  },
  tmax_c: {
    label: "Maximum temperature",
    unit: "°F",
    slopeUnit: "°F / yr",
    description: "Annual mean of daily maximum near-surface temperature.",
    kind: "temperature",
    decimals: 3,
  },
  tmin_c: {
    label: "Minimum temperature",
    unit: "°F",
    slopeUnit: "°F / yr",
    description: "Annual mean of daily minimum near-surface temperature.",
    kind: "temperature",
    decimals: 3,
  },
  prcp_mm: {
    label: "Precipitation",
    unit: "mm / yr",
    slopeUnit: "mm / yr²",
    description: "Annual total precipitation.",
    kind: "precip",
    decimals: 2,
  },
  snowfall_mm: {
    label: "Snowfall (water-equivalent)",
    unit: "mm / yr",
    slopeUnit: "mm / yr²",
    description: "Annual total water-equivalent snowfall.",
    kind: "snow",
    decimals: 2,
  },
  swe_mm: {
    label: "Snow-water equivalent",
    unit: "mm",
    slopeUnit: "mm / yr",
    description: "Mean daily snow-water equivalent.",
    kind: "snow",
    decimals: 2,
  },
  srad_wm2: {
    label: "Shortwave radiation",
    unit: "W/m²",
    slopeUnit: "W/m² / yr",
    description: "Mean daily downwelling shortwave radiation.",
    kind: "other",
    decimals: 2,
  },
  vp_pa: {
    label: "Vapour pressure",
    unit: "Pa",
    slopeUnit: "Pa / yr",
    description: "Mean daily near-surface water-vapour pressure.",
    kind: "other",
    decimals: 1,
  },
  pet_mm: {
    label: "Potential evapotranspiration",
    unit: "mm / yr",
    slopeUnit: "mm / yr²",
    description: "Annual total potential evapotranspiration (ERA5-Land).",
    kind: "other",
    decimals: 2,
  },
};

export function metaFor(key: string): VarMeta {
  return VARS[key] ?? {
    label: key,
    unit: "",
    slopeUnit: "/ yr",
    description: "",
    kind: "other",
    decimals: 3,
  };
}
