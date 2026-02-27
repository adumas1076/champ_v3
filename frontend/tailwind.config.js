/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        champ: {
          bg: "#0a0a0a",
          card: "#141414",
          border: "#262626",
          accent: "#3b82f6",
          green: "#22c55e",
          red: "#ef4444",
          yellow: "#eab308",
          muted: "#737373",
        },
      },
    },
  },
  plugins: [],
};
