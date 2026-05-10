/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-elev": "var(--bg-elev)",
        "bg-quiet": "var(--bg-quiet)",
        ink: "var(--ink)",
        "ink-dim": "var(--ink-dim)",
        "ink-faint": "var(--ink-faint)",
        rule: "var(--rule)",
        accent: {
          DEFAULT: "var(--accent)",
          dim: "var(--accent-dim)",
        },
        critical: "var(--critical)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
        type: ["var(--font-type)", "Courier Prime", "monospace"],
      },
      maxWidth: {
        prose: "680px",
        content: "1080px",
      },
      letterSpacing: {
        tracked: "0.08em",
      },
    },
  },
  plugins: [],
};
