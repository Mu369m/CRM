"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`inline-flex items-center justify-center rounded-md border p-2 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/70 ${
        theme === "dark"
          ? "border-slate-700 bg-slate-800/75 text-slate-100 hover:border-slate-600 hover:bg-slate-700/80"
          : "border-slate-300 bg-slate-100 text-slate-800 hover:border-slate-400 hover:bg-slate-200"
      }`}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      type="button"
    >
      {theme === "dark" ? (
        <Sun size={18} className="text-yellow-400" />
      ) : (
        <Moon size={18} className="text-slate-600" />
      )}
    </button>
  );
}
