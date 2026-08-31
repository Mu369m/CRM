"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/context/ThemeContext";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={`
        inline-flex items-center justify-center 
        rounded-lg border 
        p-2.5 transition-all duration-200 
        focus:outline-none focus:ring-2 focus:ring-offset-2
        ${
          theme === "dark"
            ? "border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 focus:ring-blue-400 focus:ring-offset-gray-900"
            : "border-gray-300 bg-white text-gray-700 shadow-sm hover:bg-gray-50 focus:ring-blue-500 focus:ring-offset-white"
        }
      `}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      type="button"
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      {theme === "dark" ? (
        <Sun size={20} className="text-amber-400" />
      ) : (
        <Moon size={20} className="text-blue-600" />
      )}
    </button>
  );
}
