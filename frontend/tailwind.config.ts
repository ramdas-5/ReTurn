import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "var(--ink)",
          2: "var(--ink-2)",
        },
        canvas: "var(--canvas)",
        surface: {
          DEFAULT: "var(--surface)",
          muted: "var(--surface-muted)",
        },
        line: "var(--line)",
        muted: "var(--muted)",
        accent: {
          DEFAULT: "var(--accent)",
          strong: "var(--accent-strong)",
          soft: "var(--accent-soft)",
        },
        lime: "var(--lime)",
        amber: {
          DEFAULT: "var(--amber)",
          soft: "var(--amber-soft)",
        },
        danger: {
          DEFAULT: "var(--red)",
          soft: "var(--red-soft)",
        },
        lane: {
          DEFAULT: "var(--blue)",
          soft: "var(--blue-soft)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        control: "10px",
        card: "16px",
        modal: "22px",
      },
      boxShadow: {
        card: "0 6px 24px rgba(15, 40, 32, 0.045)",
        floating: "0 14px 42px rgba(9, 37, 31, 0.13)",
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
        "fade-up": "fade-up 320ms ease-out both",
        "draw-route": "draw-route 900ms ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
