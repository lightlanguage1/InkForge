import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

interface ThemeCtx {
  isDayMode: boolean;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeCtx>({ isDayMode: false, toggleTheme: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isDayMode, setIsDayMode] = useState(() => localStorage.getItem("theme") === "day");

  useEffect(() => {
    document.documentElement.classList.toggle("day", isDayMode);
  }, [isDayMode]);

  function toggleTheme() {
    setIsDayMode((prev) => {
      const next = !prev;
      localStorage.setItem("theme", next ? "day" : "night");
      return next;
    });
  }

  return (
    <ThemeContext.Provider value={{ isDayMode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
