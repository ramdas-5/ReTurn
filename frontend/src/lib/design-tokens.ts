/**
 * Concrete values for libraries that write SVG presentation attributes
 * (Recharts, Leaflet) and cannot resolve CSS custom properties.
 *
 * Every entry is one of the six DESIGN.md palette tokens, or an alpha variant of
 * one of them. This is the only permitted home for raw palette values in
 * TypeScript.
 */
export const palette = {
  base: "#000000",
  surface: "#FFFFFF",
  ink: "#202020",
  ink2: "#242723",
  ink3: "#4A4144",
  accent: "#7C1D25",
  onBase: "rgba(255, 255, 255, 0.72)",
} as const;

/** Ordered series palette; colour alone must never carry meaning. */
export const chartSeries = [
  palette.accent,
  palette.ink,
  palette.ink2,
  palette.ink3,
  palette.base,
  "rgba(124, 29, 37, 0.55)",
] as const;

export const chartAxis = {
  grid: "rgba(32, 32, 32, 0.16)",
  tick: palette.ink3,
  tickStrong: palette.ink,
  cursor: "rgba(32, 32, 32, 0.04)",
} as const;
