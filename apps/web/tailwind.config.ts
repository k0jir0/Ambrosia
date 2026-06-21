import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        fog: "#f5f7f8",
        paper: "#fbfcfd",
        line: "#dbe3e7",
        pine: "#0f5f55",
        teal: "#138c7e",
        amber: "#b7791f",
        coral: "#c84c3d",
        violet: "#5d5a9c"
      },
      boxShadow: {
        panel: "0 18px 48px rgba(23, 32, 38, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;