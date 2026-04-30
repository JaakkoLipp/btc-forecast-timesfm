/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#050816",
        panel: "#0B1020",
        mutedPanel: "#111827",
        line: "#1F2937",
        text: "#E5E7EB",
        muted: "#94A3B8",
        accent: "#22D3EE",
        violetAccent: "#8B5CF6",
        positive: "#22C55E",
        negative: "#F97316"
      },
      boxShadow: {
        glow: "0 0 24px rgba(34, 211, 238, 0.12)"
      }
    }
  },
  plugins: []
};

