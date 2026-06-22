import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#edf7f4",
        fog: "#101820",
        paper: "#16232d",
        line: "#2b3f4c",
        pine: "#0f5f55",
        teal: "#38c7b6",
        amber: "#f2b84b",
        coral: "#ff7366",
        violet: "#a9a4ff"
      },
      boxShadow: {
        panel: "0 18px 48px rgba(0, 0, 0, 0.28)"
      }
    }
  },
  plugins: []
};

export default config;
