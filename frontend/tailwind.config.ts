import type { Config } from "tailwindcss";

/**
 * Tokens from DESIGN.md (the design-system contract for this repository).
 * Semantic aliases in `globals.css` resolve to the exact captured values.
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "var(--ink)",
          2: "var(--ink-2)",
          deep: "var(--surface-base)",
        },
        canvas: "var(--surface-base)",
        surface: {
          DEFAULT: "var(--surface)",
          muted: "var(--color-surface-muted)",
          tint: "var(--surface-tint)",
          hover: "var(--surface-hover)",
        },
        line: {
          DEFAULT: "var(--line)",
          strong: "var(--line-strong)",
        },
        muted: "var(--muted)",
        accent: {
          DEFAULT: "var(--accent)",
          strong: "var(--accent-strong)",
          soft: "var(--accent-soft)",
          border: "var(--accent-border)",
        },
        lime: "var(--accent-on-base)",
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
        display: ["var(--font-display)"],
        sans: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      // DESIGN.md typography scale, used verbatim.
      fontSize: {
        "2xs": ["13px", { lineHeight: "20px" }],
        xs: ["13px", { lineHeight: "20px" }],
        sm: ["13.33px", { lineHeight: "20px" }],
        md: ["14px", { lineHeight: "20px" }],
        base: ["20px", { lineHeight: "20px" }],
        lg: ["15px", { lineHeight: "22px" }],
        xl: ["17px", { lineHeight: "24px" }],
        "2xl": ["18px", { lineHeight: "26px" }],
        "3xl": ["20px", { lineHeight: "28px" }],
        "4xl": ["22.5px", { lineHeight: "30px" }],
        // Display sizes beyond the captured scale, for the landing hero only.
        "5xl": ["28px", { lineHeight: "34px" }],
        "6xl": ["34px", { lineHeight: "40px" }],
      },
      // DESIGN.md spacing scale. Use `p-s3`, `gap-s2`, … or the CSS variables.
      spacing: {
        s1: "5px",
        s2: "6px",
        s3: "12px",
        s4: "14px",
        s5: "16px",
        s6: "17px",
        s7: "18px",
        s8: "20px",
      },
      borderRadius: {
        control: "var(--radius-control)",
        card: "var(--radius-card)",
        modal: "var(--radius-modal)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        floating: "var(--shadow-floating)",
      },
      // DESIGN.md motion tokens, used verbatim.
      transitionDuration: {
        instant: "300ms",
        fast: "500ms",
        normal: "800ms",
      },
      transitionTimingFunction: {
        standard: "cubic-bezier(0.2, 0, 0, 1)",
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
        "fade-up": "fade-up 300ms cubic-bezier(0.2, 0, 0, 1) both",
        "draw-route": "draw-route 800ms cubic-bezier(0.2, 0, 0, 1) both",
      },
    },
  },
  plugins: [],
};

export default config;
