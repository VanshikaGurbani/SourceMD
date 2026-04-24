/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        trust: {
          high: "#10b981",
          mid: "#f59e0b",
          low: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};
