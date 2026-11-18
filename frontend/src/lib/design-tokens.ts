/**
 * Concrete values for libraries that write SVG presentation attributes
 * (Recharts, Leaflet) and cannot resolve CSS custom properties.
 *
 * Every entry is one of the DESIGN.md palette tokens (plus the captured At
 * brand sage), or an alpha variant of one of them. This is the only permitted
 * home for raw palette values in TypeScript.
 */
export const palette = {
  base: "#000000",
  surface: "#FFFFFF",
  strong: "#F5F5F5",
  raised: "#615E50",
  ink: "#201F1A",
  ink2: "#413F32",
  ink3: "#6D6C64",
  accent: "#C7D2AC",
  onBase: "rgba(250, 250, 250, 0.72)",
} as const;

/** Ordered series palette; colour alone must never carry meaning. */
export const chartSeries = [
  palette.ink,
  palette.accent,
  palette.ink3,
  palette.raised,
  palette.base,
  "rgba(199, 210, 172, 0.55)",
] as const;

export const chartAxis = {
  grid: "rgba(32, 31, 26, 0.12)",
  tick: palette.ink3,
  tickStrong: palette.ink,
  cursor: "rgba(32, 31, 26, 0.04)",
} as const;
