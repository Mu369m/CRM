"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  const applyTheme = (newTheme: Theme) => {
    const root = document.documentElement;
    root.classList.toggle("dark", newTheme === "dark");
    root.classList.toggle("light", newTheme === "light");
    root.style.colorScheme = newTheme;
    localStorage.setItem("app-theme", newTheme);
  };

  useEffect(() => {
    const stored = localStorage.getItem("app-theme");
    const preferredTheme: Theme = stored === "light" || stored === "dark" ? stored : "dark";
    setTheme(preferredTheme);
    applyTheme(preferredTheme);
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
