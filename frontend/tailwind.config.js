/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["DM Sans", "system-ui", "-apple-system", "PingFang SC", "Microsoft YaHei", "sans-serif"],
        display: ["Cormorant Garamond", "Georgia", "PingFang SC", "serif"],
        mono:    ["JetBrains Mono", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        /* Literary Night palette — nested for reliable Tailwind class generation */
        ink: {
          base:    "#0e0c09",
          surface: "#161410",
          raised:  "#1c1a16",
        },
        parchment: {
          DEFAULT: "#f0ece2",
          2:       "#7a7468",
          3:       "#3c3830",
        },
        gold: {
          DEFAULT: "#c8975a",
          light:   "#e5ad6a",
          dark:    "#9e7240",
        },
        /* Legacy tokens kept for backward compat */
        brand: {
          50: "#eef2ff", 100: "#e0e7ff", 200: "#c7d2fe",
          300: "#a5b4fc", 400: "#818cf8", 500: "#6366f1",
          600: "#4f46e5", 700: "#4338ca", 800: "#3730a3",
          900: "#312e81",
        },
        surface: {
          50: "#fafafa", 100: "#f4f4f5", 200: "#e4e4e7", 300: "#d4d4d8",
          400: "#a1a1aa", 500: "#71717a", 600: "#52525b",
          700: "#3f3f46", 800: "#27272a", 900: "#18181b",
        },
      },
      animation: {
        "fade-in":         "fadeIn 0.25s ease-out",
        "slide-up":        "slideUp 0.28s cubic-bezier(0.16,1,0.3,1)",
        "slide-in-left":   "slideInLeft 0.22s cubic-bezier(0.16,1,0.3,1)",
        "slide-in-right":  "slideInRight 0.22s cubic-bezier(0.16,1,0.3,1)",
      },
      keyframes: {
        fadeIn:       { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp:      { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        slideInLeft:  { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "translateX(0)" } },
        slideInRight: { "0%": { transform: "translateX(100%)" }, "100%": { transform: "translateX(0)" } },
      },
    },
  },
  plugins: [],
};
