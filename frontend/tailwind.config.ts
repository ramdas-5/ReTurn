import type { Config } from "tailwindcss";

/**
 * Tokens from DESIGN.md (the design-system contract for this repository).
 * Semantic aliases in `globals.css` resolve to the exact captured values:
 * At (traced.life), Saans at 16/24, the 12–48 type scale, the 4.03–16.13
 * spacing scale, 8/16/full radii and 150/250ms motion.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "var(--ink)",
          2: "var(--ink-2)",
          deep: "var(--color-text-secondary)",
        },
        canvas: "var(--canvas)",
        surface: {
          DEFAULT: "var(--surface)",
          muted: "var(--surface-muted)",
          label: "var(--color-surface-muted)",
          raised: "var(--color-surface-raised)",
          strong: "var(--color-surface-strong)",
          tint: "var(--surface-tint)",
          hover: "var(--surface-hover)",
        },
        inverse: "var(--color-surface-base)",
        line: {
          DEFAULT: "var(--line)",
          strong: "var(--line-strong)",
        },
        muted: "var(--muted)",
        primary: {
          DEFAULT: "var(--color-primary)",
          70: "var(--color-primary-70)",
          50: "var(--color-primary-50)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          ink: "var(--accent-ink)",
          strong: "var(--accent-strong)",
          soft: "var(--accent-soft)",
          border: "var(--accent-border)",
        },
        lime: "var(--color-primary)",
        amber: {
          DEFAULT: "var(--amber)",
          soft: "var(--amber-soft)",
          border: "var(--amber-border)",
          ink: "var(--amber-ink)",
        },
        red: {
          DEFAULT: "var(--red)",
          soft: "var(--red-soft)",
          border: "var(--red-border)",
          ink: "var(--red-ink)",
        },
        danger: {
          DEFAULT: "var(--red)",
          soft: "var(--red-soft)",
          border: "var(--red-border)",
          ink: "var(--red-ink)",
        },
        blue: {
          DEFAULT: "var(--blue)",
          soft: "var(--blue-soft)",
          border: "var(--blue-border)",
          ink: "var(--blue-ink)",
        },
        lane: {
          DEFAULT: "var(--blue)",
          soft: "var(--blue-soft)",
          border: "var(--blue-border)",
          ink: "var(--blue-ink)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        sans: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      // DESIGN.md typography scale, used verbatim.
      fontSize: {
        xs: ["12px", { lineHeight: "16px" }],
        sm: ["14px", { lineHeight: "20px" }],
        base: ["16px", { lineHeight: "24px" }],
        md: ["16px", { lineHeight: "24px" }],
        lg: ["28px", { lineHeight: "34px" }],
        xl: ["40px", { lineHeight: "46px" }],
        "2xl": ["48px", { lineHeight: "54px" }],
      },
      // DESIGN.md spacing scale. Use `p-s3`, `gap-s2`, … or the CSS variables.
      spacing: {
        s1: "4.03px",
        s2: "5.04px",
        s3: "6.05px",
        s4: "7.06px",
        s5: "8.06px",
        s6: "12.1px",
        s7: "12.6px",
        s8: "16.13px",
      },
      borderRadius: {
        control: "var(--radius-control)",
        card: "var(--radius-card)",
        pill: "var(--radius-pill)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        floating: "var(--shadow-floating)",
      },
      // DESIGN.md motion tokens, used verbatim.
      transitionDuration: {
        instant: "150ms",
        fast: "250ms",
      },
      transitionTimingFunction: {
        standard: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      maxWidth: {
        container: "1440px",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "draw-route": {
          from: { strokeDashoffset: "600" },
          to: { strokeDashoffset: "0" },
        },
      },
      animation: {
        "fade-up": "fade-up 250ms cubic-bezier(0.4, 0, 0.2, 1) both",
        "draw-route": "draw-route 250ms cubic-bezier(0.4, 0, 0.2, 1) both",
      },
    },
  },
  plugins: [],
};

export default config;
